"""Seiten „Video & Audio“ (brauchen [gui] und ffmpeg; ohne ffmpeg übersprungen)."""

import threading
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

from miksan_converter import medien  # noqa: E402
from miksan_converter.gui import app, werkzeuge  # noqa: E402
from miksan_converter.gui.seiten.einstellungen import NichtVerfuegbarSeite  # noqa: E402


@pytest.fixture
def fenster(qtbot, tmp_path: Path):
    settings = QSettings(str(tmp_path / "e.ini"), QSettings.Format.IniFormat)
    fenster = app.Hauptfenster(settings)
    qtbot.addWidget(fenster)
    fenster.show()
    return fenster


def _warten(qtbot, seite) -> None:
    qtbot.waitUntil(
        lambda: seite.letztes_ergebnis is not None and not seite.laeuft(), timeout=60_000
    )


def test_ohne_ffmpeg_ausgegraut(qtbot, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(medien, "ffmpeg_finden", lambda: None)
    fenster = app.Hauptfenster(QSettings(str(tmp_path / "x.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(fenster)
    seite = fenster.seite_zeigen("video_umwandeln")
    assert isinstance(seite, NichtVerfuegbarSeite)
    assert "[medien]" in seite.hinweis.text()
    assert fenster.seite("umwandeln").werkzeug.verfuegbar()
    texte = [fenster.navigation.item(i).text() for i in range(fenster.navigation.count())]
    assert "VIDEO & AUDIO" in texte


def test_mov_zu_mp4_in_der_app(qtbot, fenster, clips, tmp_path: Path):
    seite = fenster.werkzeug_oeffnen("video_umwandeln", [str(clips["clip_mov"])])
    zeile = seite.liste.zeile(str(clips["clip_mov"]))
    qtbot.waitUntil(lambda: "320 × 240" in zeile.angaben.text(), timeout=20_000)
    assert "0:02" in zeile.angaben.text()
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "aus"))
    seite.starten()
    _warten(qtbot, seite)
    assert seite.status.text() == "Fertig: 1 ok, 0 Fehler"
    assert medien.untersuchen(tmp_path / "aus" / "clip.mp4").video == "h264"


def test_ton_herausziehen_und_audio(qtbot, fenster, clips, tmp_path: Path):
    seite = fenster.werkzeug_oeffnen("video_ton", [str(clips["clip_mkv"])])
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "ton"))
    seite.starten()
    _warten(qtbot, seite)
    assert medien.untersuchen(tmp_path / "ton" / "clip.mp3").audio == "mp3"
    audio = fenster.werkzeug_oeffnen("audio_umwandeln", [str(clips["ton_mp3"])])
    audio.ziel.setCurrentIndex(audio.ziel.findData("flac"))
    audio.ablauf.ausgabe_ordner.setText(str(tmp_path / "flac"))
    audio.starten()
    _warten(qtbot, audio)
    info = medien.untersuchen(tmp_path / "flac" / "ton.flac")
    assert info.audio == "flac" and info.metadaten.get("title") == "Testlied"


def test_abbrechen_stoppt_sofort(qtbot, fenster, clips, tmp_path: Path, monkeypatch):
    gestartet = threading.Event()
    original = medien.ausfuehren

    def langsam(*args, abbrechen=None, **kwargs):
        gestartet.set()
        abbrechen.wait(10)  # wie ein langer ffmpeg-Lauf
        return original(*args, abbrechen=abbrechen, **kwargs)

    monkeypatch.setattr(medien, "ausfuehren", langsam)
    seite = fenster.werkzeug_oeffnen("video_umwandeln", [str(clips["clip_mov"])])
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "abbruch"))
    seite.starten()
    assert gestartet.wait(10)
    seite.abbrechen()
    _warten(qtbot, seite)
    assert seite.letztes_ergebnis.uebersprungen and not seite.letztes_ergebnis.fehler
    assert not (tmp_path / "abbruch").exists() or not list((tmp_path / "abbruch").iterdir())


def test_kuerzen_braucht_zeit(fenster, clips, monkeypatch):
    seite = fenster.werkzeug_oeffnen("video_kuerzen", [str(clips["clip_mov"])])
    meldungen = []
    monkeypatch.setattr(seite, "_melden", lambda titel, text: meldungen.append(text))
    seite.starten()
    assert not seite.laeuft() and "Start" in meldungen[0]


def test_registrierung_video_audio():
    namen = {w.name for w in werkzeuge.WERKZEUGE if w.bereich == "Video & Audio"}
    assert {"video_umwandeln", "video_verkleinern", "video_gif", "audio_umwandeln"} <= namen
    passende = {w.name for w, _ in werkzeuge.passende_werkzeuge(["film.mov"])}
    assert "video_umwandeln" in passende and "audio_umwandeln" not in passende

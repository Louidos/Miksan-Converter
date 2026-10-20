"""Rauchtest für das Fenster (braucht das Extra [gui] und pytest-qt)."""

import os
import threading
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("PySide6")

from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402

from miksan_converter.gui import app, logik  # noqa: E402


@pytest.fixture
def fenster(qtbot, tmp_path: Path):
    settings = QSettings(str(tmp_path / "einstellungen.ini"), QSettings.Format.IniFormat)
    fenster = app.Hauptfenster(settings)
    qtbot.addWidget(fenster)
    fenster.show()
    return fenster


@pytest.fixture
def bilder(tmp_path: Path) -> Path:
    ordner = tmp_path / "bilder"
    ordner.mkdir()
    for i in range(3):
        Image.new("RGBA", (60, 40), (50 * i, 100, 0, 255)).save(ordner / f"bild{i}.png")
    return ordner


def _ablegen(ziel, pfade: list[Path]) -> None:
    daten = QMimeData()
    daten.setUrls([QUrl.fromLocalFile(str(pfad)) for pfad in pfade])
    ereignis = QDropEvent(
        QPointF(5, 5),
        Qt.DropAction.CopyAction,
        daten,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ziel.dropEvent(ereignis)


def _warten(qtbot, fenster) -> None:
    qtbot.waitUntil(
        lambda: fenster.letztes_ergebnis is not None and not fenster.laeuft(), timeout=30_000
    )


def test_fenster_wandelt_um(qtbot, fenster, bilder: Path, tmp_path: Path):
    assert not fenster.knopf_start.isEnabled()
    _ablegen(fenster.liste, [bilder / "bild0.png", bilder / "bild1.png"])
    assert fenster.liste.count() == 2
    fenster.format_waehlen("jpeg")
    fenster.ausgabe_ordner.setText(str(tmp_path / "aus"))
    fenster.max_seite.setValue(30)

    qtbot.mouseClick(fenster.knopf_start, Qt.MouseButton.LeftButton)
    _warten(qtbot, fenster)

    assert sorted(p.name for p in (tmp_path / "aus").iterdir()) == ["bild0.jpg", "bild1.jpg"]
    with Image.open(tmp_path / "aus" / "bild0.jpg") as bild:
        assert bild.format == "JPEG" and bild.size == (30, 20)
    assert fenster.status.text() == "Fertig: 2 ok, 0 Fehler"
    assert fenster.knopf_oeffnen.isEnabled()
    assert fenster.knopf_start.isEnabled()


def test_ordner_ablegen_und_fehler_anzeigen(qtbot, fenster, bilder: Path):
    (bilder / "kaputt.png").write_bytes(b"\x89PNG\r\n\x1a\nkaputt")
    _ablegen(fenster, [bilder])  # auch auf das ganze Fenster
    _ablegen(fenster.liste, [bilder])  # doppelt wird ignoriert
    assert fenster.pfade() == [str(bilder)]
    fenster.format_waehlen("webp")

    fenster.starten()
    _warten(qtbot, fenster)

    assert len(list(bilder.glob("*.webp"))) == 3
    assert fenster.status.text() == "Fertig: 3 ok, 1 Fehler"
    assert fenster.meldungen.isVisible()
    assert "kaputt.png" in fenster.meldungen.item(0).text()


def test_abbrechen(qtbot, fenster, bilder: Path, tmp_path: Path, monkeypatch):
    weiter = threading.Event()
    original = logik.umwandeln

    def langsam(*args, **kwargs):
        weiter.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(logik, "umwandeln", langsam)
    monkeypatch.setattr(os, "cpu_count", lambda: 1)  # eine Datei nach der anderen
    fenster.pfade_hinzufuegen([bilder])
    fenster.format_waehlen("png")
    fenster.ausgabe_ordner.setText(str(tmp_path / "aus"))
    fenster.starten()
    assert fenster.laeuft() and fenster.knopf_abbrechen.isEnabled()
    assert not fenster.knopf_start.isEnabled()
    assert not fenster.optionen.isEnabled()

    qtbot.mouseClick(fenster.knopf_abbrechen, Qt.MouseButton.LeftButton)
    weiter.set()
    _warten(qtbot, fenster)

    ergebnis = fenster.letztes_ergebnis
    assert len(ergebnis.ok) + len(ergebnis.uebersprungen) == 3
    assert ergebnis.uebersprungen  # mindestens eine Datei wurde nicht mehr gestartet
    assert "abgebrochen" in fenster.status.text()
    assert fenster.optionen.isEnabled()


def test_einstellungen_werden_gemerkt(qtbot, tmp_path: Path):
    pfad = str(tmp_path / "einstellungen.ini")
    erstes = app.Hauptfenster(QSettings(pfad, QSettings.Format.IniFormat))
    qtbot.addWidget(erstes)
    erstes.aktion_knoepfe[logik.BEARBEITEN].setChecked(True)
    erstes.format_waehlen("webp")
    erstes.qualitaet.setValue(70)
    erstes.rekursiv.setChecked(True)
    erstes.farbe_setzen("#112233")
    erstes.einstellungen_speichern()

    zweites = app.Hauptfenster(QSettings(pfad, QSettings.Format.IniFormat))
    qtbot.addWidget(zweites)
    einstellungen = zweites.einstellungen()
    assert einstellungen.aktion == logik.BEARBEITEN
    assert einstellungen.ziel_format == "webp"
    assert einstellungen.qualitaet == 70
    assert einstellungen.rekursiv
    assert einstellungen.hintergrundfarbe == "#112233"


def test_zielformat_je_aktion(fenster):
    fenster.format_waehlen("avif")
    fenster.aktion_knoepfe[logik.BEARBEITEN].setChecked(True)
    assert fenster.format_auswahl.itemData(0) == logik.WIE_ORIGINAL
    assert fenster.format_auswahl.currentData() == logik.WIE_ORIGINAL
    fenster.aktion_knoepfe[logik.UMWANDELN].setChecked(True)
    assert fenster.format_auswahl.findData(logik.WIE_ORIGINAL) == -1
    assert fenster.format_auswahl.currentData() == "avif"


def test_ohne_ki_ist_hintergrund_ausgegraut(qtbot, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(logik, "extra_installiert", lambda extra: False)
    fenster = app.Hauptfenster(QSettings(str(tmp_path / "e.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(fenster)
    knopf = fenster.aktion_knoepfe[logik.HINTERGRUND]
    assert not knopf.isEnabled()
    assert "[ki]" in knopf.toolTip()
    assert "[ki]" in fenster.aktion_hinweis.text()


def test_fehlerhafte_eingabe_zeigt_meldung(fenster, bilder: Path, monkeypatch):
    meldungen = []
    monkeypatch.setattr(fenster, "_melden", lambda titel, text: meldungen.append(text))
    fenster.pfade_hinzufuegen([bilder])
    fenster.zielgroesse.setText("riesig")
    fenster.starten()
    assert not fenster.laeuft()
    assert "ungültig" in meldungen[0]


def test_hintergrund_fragt_vor_dem_download(fenster, bilder: Path, monkeypatch, tmp_path):
    monkeypatch.setattr(logik, "extra_installiert", lambda extra: True)
    monkeypatch.setenv("MIKSAN_MODELL_ORDNER", str(tmp_path / "modelle"))
    gefragt = []

    def ablehnen(modell):
        gefragt.append(modell)
        return False

    monkeypatch.setattr(fenster, "_modell_download_bestaetigen", ablehnen)
    fenster.aktion_knoepfe[logik.HINTERGRUND].setEnabled(True)
    fenster.aktion_knoepfe[logik.HINTERGRUND].setChecked(True)
    fenster.pfade_hinzufuegen([bilder])
    fenster.starten()
    assert gefragt == ["klein"]
    assert not fenster.laeuft()


def test_programm_icon():
    assert not app.programm_icon().isNull()


def test_selbsttest_fenster(qtbot):
    from miksan_converter.gui import selbsttest

    zeilen: list[str] = []
    assert selbsttest._fenster_pruefen(zeilen)
    assert zeilen == ["ok      Fenster: Fertig: 1 ok, 0 Fehler"]


def test_selbsttest_bericht(qtbot, tmp_path: Path, monkeypatch):
    from miksan_converter import gui
    from miksan_converter.gui import selbsttest

    monkeypatch.setattr(selbsttest, "MODULE", ("PIL", "gibt_es_nicht_123"))
    bericht = tmp_path / "bericht.txt"
    monkeypatch.setattr("sys.argv", ["miksan-gui", "--selbsttest", str(bericht)])
    assert gui.main() == 1
    text = bericht.read_text(encoding="utf-8")
    assert "ok      PIL" in text
    assert "FEHLER  gibt_es_nicht_123" in text
    assert "Ergebnis: FEHLER" in text

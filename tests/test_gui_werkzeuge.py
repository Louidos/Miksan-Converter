"""Seiten der weiteren Bild-Werkzeuge (brauchen [gui])."""

import shutil
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("PySide6")

from PySide6.QtCore import QPoint, QSettings, Qt  # noqa: E402

from miksan_converter.gui import app  # noqa: E402


@pytest.fixture
def fenster(qtbot, tmp_path: Path):
    settings = QSettings(str(tmp_path / "e.ini"), QSettings.Format.IniFormat)
    fenster = app.Hauptfenster(settings)
    qtbot.addWidget(fenster)
    fenster.show()
    return fenster


@pytest.fixture
def bilder(testbilder, tmp_path: Path) -> Path:
    ordner = tmp_path / "bilder"
    ordner.mkdir()
    for name in ("png", "jpeg", "webp"):
        shutil.copy(testbilder[name], ordner / testbilder[name].name)
    return ordner


def _warten(qtbot, seite) -> None:
    qtbot.waitUntil(
        lambda: seite.letztes_ergebnis is not None and not seite.laeuft(), timeout=30_000
    )


def test_alle_werkzeuge_in_seitenleiste(fenster):
    texte = {fenster.navigation.item(i).text() for i in range(fenster.navigation.count())}
    assert {"Zuschneiden", "Wasserzeichen", "Stapel-Umbenennen", "Animation", "Icon-Set"} <= texte


def test_wasserzeichen_mit_vorschau(qtbot, fenster, tmp_path: Path):
    Image.new("RGB", (300, 200), (0, 0, 0)).save(tmp_path / "schwarz.png")
    seite = fenster.werkzeug_oeffnen("wasserzeichen", [str(tmp_path / "schwarz.png")])
    seite.text.setText("Miksan")
    seite.deckkraft.setValue(100)
    qtbot.waitUntil(
        lambda: (
            seite.vorschau.letzte is not None
            and seite.vorschau.letzte.nachher.getextrema()[0][1] > 200
        ),
        timeout=10_000,
    )
    seite.position.setCurrentIndex(seite.position.findData("gekachelt"))
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "aus"))
    seite.starten()
    _warten(qtbot, seite)
    with Image.open(tmp_path / "aus" / "schwarz.png") as bild:
        assert bild.convert("L").getextrema()[1] > 200


def test_umbenennen_zeigt_neue_namen_und_konflikte(qtbot, fenster, bilder: Path, monkeypatch):
    seite = fenster.werkzeug_oeffnen("umbenennen", [str(bilder)])
    seite.muster.setText("bild-{nr}")
    namen = [
        seite.tabelle.topLevelItem(i).text(1) for i in range(seite.tabelle.topLevelItemCount())
    ]
    assert namen == ["bild-01.jpg", "bild-02.png", "bild-03.webp"]
    assert seite.knopf_start.isEnabled()

    (bilder / "doppelt.png").write_bytes(b"x")
    seite.pfade_setzen([str(bilder / "quelle.png")])
    seite.muster.setText("doppelt")
    assert "gibt es schon" in seite.konflikt.text()
    assert not seite.knopf_start.isEnabled()
    vorher = sorted(p.name for p in bilder.iterdir())
    meldungen = []
    monkeypatch.setattr(seite, "_melden", lambda titel, text: meldungen.append(text))
    seite.starten()  # z. B. per Tastenkürzel: bricht ab, nichts wird angefasst
    assert sorted(p.name for p in bilder.iterdir()) == vorher
    assert "gibt es schon" in meldungen[0]

    seite.muster.setText("neu-{name}")
    seite.starten()
    _warten(qtbot, seite)
    assert (bilder / "neu-quelle.png").exists() and not (bilder / "quelle.png").exists()
    assert seite.pfade() == [str(bilder / "neu-quelle.png")]


def test_animation_erstellen_und_zerlegen(qtbot, fenster, tmp_path: Path):
    pfade = []
    for i, farbe in enumerate(((255, 0, 0), (0, 255, 0), (0, 0, 255))):
        Image.new("RGB", (32, 24), farbe).save(tmp_path / f"f{i}.png")
        pfade.append(str(tmp_path / f"f{i}.png"))
    seite = fenster.werkzeug_oeffnen("animation", pfade)
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "aus"))
    seite.dauer.setValue(150)
    seite.starten()
    _warten(qtbot, seite)
    with Image.open(tmp_path / "aus" / "animation.gif") as bild:
        assert bild.n_frames == 3

    seite.pfade_setzen([str(tmp_path / "aus" / "animation.gif")])
    seite.modus.setCurrentIndex(seite.modus.findData("zerlegen"))
    assert seite.einzelformat.isVisibleTo(seite) and not seite.dauer.isVisibleTo(seite)
    seite.letztes_ergebnis = None
    seite.starten()
    _warten(qtbot, seite)
    assert len(list((tmp_path / "aus" / "animation-bilder").glob("*.png"))) == 3


def test_iconset_seite(qtbot, fenster, bilder: Path, tmp_path: Path):
    seite = fenster.werkzeug_oeffnen("iconset", [str(bilder / "quelle.png")])
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "aus"))
    seite.starten()
    _warten(qtbot, seite)
    ordner = tmp_path / "aus" / "quelle-icons"
    assert (ordner / "favicon.ico").exists() and (ordner / "icon-192x192.png").exists()


def test_zuschneiden_mit_maus(qtbot, fenster, tmp_path: Path):
    Image.new("RGB", (400, 200), (255, 0, 0)).save(tmp_path / "quer.png")
    seite = fenster.werkzeug_oeffnen("zuschneiden", [str(tmp_path / "quer.png")])
    seite.verhaeltnis.setCurrentIndex(seite.verhaeltnis.findData("1:1"))
    ansicht = seite.ansicht
    ansicht.resize(400, 300)
    qtbot.waitUntil(lambda: ansicht.bild is not None, timeout=10_000)
    assert ansicht.relativ == pytest.approx((0.25, 0.0, 0.5, 1.0))
    rechteck = ansicht.bild_rechteck()
    start = QPoint(int(rechteck.left() + 5), int(rechteck.top() + 5))
    ende = QPoint(int(rechteck.left() + rechteck.width() / 4), int(rechteck.bottom() - 5))
    qtbot.mousePress(ansicht, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(ansicht, ende)
    qtbot.mouseRelease(ansicht, Qt.MouseButton.LeftButton, pos=ende)
    x, y, b, h = ansicht.relativ
    assert x < 0.05 and b * 400 == pytest.approx(h * 200, rel=0.02)  # 1:1 in Pixeln
    seite.vorlage.setCurrentIndex(seite.vorlage.findData("profilbild"))
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "aus"))
    seite.starten()
    _warten(qtbot, seite)
    with Image.open(tmp_path / "aus" / "quer.png") as bild:
        assert bild.size == (400, 400)

"""Windows-Komfort: nur ein Fenster, Dateien von aussen, Fertigmeldung, Taskleiste, Startzeit."""

import importlib.util
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

from miksan_converter.gui import app, einzelfenster  # noqa: E402
from miksan_converter.gui.taskleiste import Taskleiste  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def fenster(qtbot, tmp_path: Path):
    fenster = app.Hauptfenster(QSettings(str(tmp_path / "e.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(fenster)
    fenster.show()
    return fenster


def test_zweiter_start_gibt_dateien_weiter(qtbot, fenster, tmp_path: Path):
    name = f"miksan-test-{uuid.uuid4().hex[:8]}"
    instanz = einzelfenster.Einzelinstanz(name)
    assert instanz.starten()
    nach_vorne = []
    einzelfenster.verbinden(fenster, instanz, lambda: nach_vorne.append(True))
    Image.new("RGB", (10, 10)).save(tmp_path / "a.png")
    fenster.seite_zeigen("einstellungen")

    # wie ein zweiter Programmstart: eigener Prozess
    skript = (
        "import sys; from PySide6.QtCore import QCoreApplication; app = QCoreApplication([]); "
        "from miksan_converter.gui import einzelfenster; "
        "sys.exit(0 if einzelfenster.an_laufendes_senden([sys.argv[1]], sys.argv[2]) else 1)"
    )
    zweiter = subprocess.Popen([sys.executable, "-c", skript, str(tmp_path / "a.png"), name])
    qtbot.waitUntil(lambda: bool(nach_vorne), timeout=20_000)
    assert zweiter.wait(20) == 0
    assert fenster.aktuelle_seite() is fenster.startseite
    assert fenster.startseite.abgelegte == [str(tmp_path / "a.png")]
    assert "umwandeln" in fenster.startseite.knoepfe
    instanz.schliessen()
    assert not einzelfenster.an_laufendes_senden([], name)  # niemand mehr da
    instanz.deleteLater()
    qtbot.wait(50)


def test_verwaister_server_wird_aufgeraeumt(qtbot):
    name = f"miksan-test-{uuid.uuid4().hex[:8]}"
    instanz = einzelfenster.Einzelinstanz(name)
    assert instanz.aufraeumen_und_starten()
    instanz.schliessen()
    instanz.deleteLater()
    qtbot.wait(50)


def test_fertigmeldung_mit_ordner_oeffnen(qtbot, fenster, tmp_path: Path):
    Image.new("RGB", (10, 10)).save(tmp_path / "a.png")
    seite = fenster.werkzeug_oeffnen("umwandeln", [str(tmp_path / "a.png")])
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "aus"))
    assert not seite.ablauf.banner.isVisible()
    seite.starten()
    qtbot.waitUntil(lambda: seite.letztes_ergebnis is not None and not seite.laeuft())
    assert seite.ablauf.banner.isVisible()
    assert "Fertig: 1 ok" in seite.ablauf.banner_text.text()
    assert seite.ablauf.banner_oeffnen.isVisible()


def test_taskleiste_ohne_windows_still():
    leiste = Taskleiste()
    if sys.platform != "win32":
        assert not leiste.aktiv
    leiste.zustand(0, 0)
    leiste.wert(0, 1, 2)


def test_start_laedt_keine_schweren_module(tmp_path: Path):
    """Schneller Start: KI, PDF und ffmpeg werden erst beim Öffnen des Werkzeugs geladen."""
    bericht = tmp_path / "startzeit.txt"
    ergebnis = subprocess.run(
        [
            sys.executable,
            "-c",
            "from miksan_converter.gui import main; import sys; "
            f"sys.argv=['x', '--startzeit', r'{bericht}']; sys.exit(main())",
        ],  # fmt: skip
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "QT_QPA_PLATFORM": "offscreen"},
        timeout=60,
    )
    assert ergebnis.returncode == 0, ergebnis.stderr
    assert "schwere Module geladen: keine" in bericht.read_text(encoding="utf-8")


def test_kontextmenue_endungen():
    spec = importlib.util.spec_from_file_location("bauen", REPO / "packaging/windows/bauen.py")
    bauen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bauen)
    endungen = bauen.kontextmenue_endungen()
    for endung in (".png", ".jpg", ".heic", ".pdf", ".mp4", ".mov", ".mp3", ".flac"):
        assert endung in endungen

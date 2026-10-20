import subprocess
import sys

import pytest

from miksan_converter import __version__
from miksan_converter.cli import main


def test_ohne_befehl_zeigt_hilfe(capsys):
    assert main([]) == 2
    assert "convert" in capsys.readouterr().out


def test_modul_aufruf_version():
    ergebnis = subprocess.run(
        [sys.executable, "-m", "miksan_converter", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ergebnis.returncode == 0
    assert __version__ in ergebnis.stdout


def test_gui_ohne_extra(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "PySide6", None)  # Import schlägt fehl
    assert main(["gui"]) == 3
    assert "[gui]" in capsys.readouterr().err


def test_miksan_gui_ohne_extra(monkeypatch, capsys):
    from miksan_converter import gui

    monkeypatch.setitem(sys.modules, "PySide6", None)
    monkeypatch.setattr(sys, "argv", ["miksan-gui"])
    assert gui.main() == 3
    assert "pip install miksan-converter[gui]" in capsys.readouterr().err


def test_gui_startet_fenster(monkeypatch):
    pytest.importorskip("PySide6")
    from miksan_converter.gui import app

    gestartet = []
    monkeypatch.setattr(app, "starten", lambda argv: gestartet.append(argv) or 0)
    assert main(["gui"]) == 0
    assert gestartet == [[]]

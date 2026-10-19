import subprocess
import sys

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

"""Grafische Oberfläche (Extra [gui], PySide6).

Start mit ``miksan-gui`` oder ``miksan gui``. Qt wird erst beim Start geladen, damit die
Kommandozeile auch ohne das Extra funktioniert.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from ..fehler import ExtraFehlt


def oberflaeche_starten(argv: Sequence[str] | None = None) -> int:
    """Öffnet das Fenster und kehrt erst nach dem Schliessen zurück (Rückgabecode)."""
    try:
        import PySide6  # noqa: F401
    except ImportError as fehler:
        raise ExtraFehlt("gui", "Die grafische Oberfläche") from fehler
    from .app import starten

    return starten(list(argv or []))


def main() -> int:
    """Einstiegspunkt für ``miksan-gui``; Dateien und Ordner als Argumente werden übernommen.

    Versteckt: ``miksan-gui --selbsttest [BERICHT]`` prüft Extras und Fenster ohne Bildschirm.
    """
    argv = sys.argv[1:]
    try:
        if argv[:1] == ["--selbsttest"]:
            from .selbsttest import selbsttest

            return selbsttest(Path(argv[1]) if len(argv) > 1 else None)
        return oberflaeche_starten(argv)
    except ExtraFehlt as fehler:
        if sys.stderr is not None:  # ohne Konsole gibt es kein stderr
            print(f"Fehler: {fehler}", file=sys.stderr)
        return fehler.rueckgabecode

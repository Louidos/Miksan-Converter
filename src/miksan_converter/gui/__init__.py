"""Grafische Oberfläche (Extra [gui], PySide6).

Start mit ``miksan-gui`` oder ``miksan gui``. Qt wird erst beim Start geladen, damit die
Kommandozeile auch ohne das Extra funktioniert.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

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
    """Einstiegspunkt für ``miksan-gui``; Dateien und Ordner als Argumente werden übernommen."""
    try:
        return oberflaeche_starten(sys.argv[1:])
    except ExtraFehlt as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        return fehler.rueckgabecode

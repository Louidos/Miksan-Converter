"""Gemeinsame Einstellungen für die eingepackten Programme (PyInstaller).

numba (über rembg -> pymatting) speichert übersetzte Funktionen in einem Cache. Im
Programmordner darf es nicht schreiben, deshalb kommt der Cache in den Benutzerordner.
"""

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    if sys.platform == "win32":
        _basis = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        _basis = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    os.environ.setdefault("NUMBA_CACHE_DIR", str(_basis / "miksan-converter" / "cache" / "numba"))

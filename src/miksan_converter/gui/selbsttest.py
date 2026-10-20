"""Selbsttest (versteckte Option ``--selbsttest``), z. B. für den Rauchtest des Installers.

Lädt alle Extras, öffnet das Fenster ohne Bildschirm und wandelt darüber ein Testbild um.
Rückgabecode 0 = alles in Ordnung.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

MODULE = ("PIL", "pillow_heif", "resvg_py", "rawpy", "onnxruntime", "rembg", "PySide6.QtWidgets")


def _module_pruefen(zeilen: list[str]) -> bool:
    alles_ok = True
    for modul in MODULE:
        try:
            importlib.import_module(modul)
        except Exception as fehler:  # auch DLL-Fehler u. ä. melden, nicht abstürzen
            alles_ok = False
            zeilen.append(f"FEHLER  {modul}: {fehler!r}")
        else:
            zeilen.append(f"ok      {modul}")
    return alles_ok


def _fenster_pruefen(zeilen: list[str]) -> bool:
    from PIL import Image
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from .app import Hauptfenster

    app = QApplication.instance() or QApplication(sys.argv[:1])
    with tempfile.TemporaryDirectory(prefix="miksan-selbsttest-") as ordner:
        ordner = Path(ordner)
        Image.new("RGBA", (64, 48), (200, 40, 40, 160)).save(ordner / "test.png")
        settings = QSettings(str(ordner / "einstellungen.ini"), QSettings.Format.IniFormat)
        fenster = Hauptfenster(settings)
        fenster.show()
        fenster.pfade_hinzufuegen([ordner / "test.png"])
        fenster.format_waehlen("heif")
        fenster.ausgabe_ordner.setText(str(ordner / "aus"))
        fenster.starten()
        ende = time.monotonic() + 60
        while fenster.letztes_ergebnis is None and time.monotonic() < ende:
            app.processEvents()
            time.sleep(0.02)
        ergebnis = fenster.letztes_ergebnis
        fenster.close()
        ok = ergebnis is not None and len(ergebnis.ok) == 1 and not ergebnis.fehler
        ziel = ordner / "aus" / "test.heic"
        ok = ok and ziel.is_file()
        zeilen.append(f"{'ok' if ok else 'FEHLER':<8}Fenster: {fenster.status.text()}")
    return ok


def selbsttest(bericht: Path | None = None) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from .. import __version__

    zeilen = [f"Miksan-Converter {__version__} – Selbsttest", f"Python {sys.version.split()[0]}"]
    ok = _module_pruefen(zeilen)
    try:
        ok = _fenster_pruefen(zeilen) and ok
    except Exception:
        ok = False
        zeilen.append("FEHLER  Fenster:\n" + traceback.format_exc())
    zeilen.append("Ergebnis: ok" if ok else "Ergebnis: FEHLER")
    text = "\n".join(zeilen) + "\n"
    if bericht is not None:
        bericht.write_text(text, encoding="utf-8")
    if sys.stdout is not None:  # ohne Konsole (Miksan-Converter.exe) gibt es kein stdout
        sys.stdout.write(text)
    return 0 if ok else 1

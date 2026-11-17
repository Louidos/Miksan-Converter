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

MODULE = (
    "PIL",
    "pillow_heif",
    "resvg_py",
    "rawpy",
    "onnxruntime",
    "rembg",
    "PySide6.QtWidgets",
    "PySide6.QtSvg",
    "pypdf",
    "pypdfium2",
    "imageio_ffmpeg",
)


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


def _design_pruefen(zeilen: list[str]) -> bool:
    """Stylesheet und alle Icons müssen im (eingepackten) Programm vorhanden sein."""
    from PySide6.QtWidgets import QApplication

    from . import design

    app = QApplication.instance() or QApplication(sys.argv[:1])
    design.anwenden(app)
    namen = design.icon_namen()
    fehlend = [name for name in namen if design.icon(name).pixmap(24, 24).isNull()]
    ok = bool(app.styleSheet()) and len(namen) >= 20 and not fehlend
    ok = ok and design.programm_icon_pfad().is_file()
    text = f"Design: Stylesheet, {len(namen)} Icons"
    if fehlend:
        text += f", fehlerhaft: {', '.join(fehlend)}"
    zeilen.append(f"{'ok' if ok else 'FEHLER':<8}{text}")
    return ok


def _ffmpeg_pruefen(zeilen: list[str]) -> bool:
    """Im Windows-Installer muss ffmpeg mitgeliefert sein und starten."""
    if not getattr(sys, "frozen", False):
        return True
    from .. import medien

    try:
        version = medien.version()
    except Exception as fehler:  # nicht gefunden oder startet nicht
        version, ok = repr(fehler), False
    else:
        ok = version.startswith("ffmpeg version")
    zeilen.append(f"{'ok' if ok else 'FEHLER':<8}ffmpeg: {version}")
    return ok


def _modell_pruefen(zeilen: list[str]) -> bool:
    """Im Windows-Installer muss das kleine Modell mitgeliefert sein (offline nutzbar)."""
    if not getattr(sys, "frozen", False):
        return True
    from ..hintergrund import mitgelieferte_modelle

    ordner = mitgelieferte_modelle()
    ok = ordner is not None and (ordner / "u2netp.onnx").is_file()
    zeilen.append(f"{'ok' if ok else 'FEHLER':<8}Mitgeliefertes Modell: {ordner}")
    return ok


def _fenster_pruefen(zeilen: list[str]) -> bool:
    from PIL import Image
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from .fenster import Hauptfenster

    app = QApplication.instance() or QApplication(sys.argv[:1])
    with tempfile.TemporaryDirectory(prefix="miksan-selbsttest-") as ordner:
        ordner = Path(ordner)
        Image.new("RGBA", (64, 48), (200, 40, 40, 160)).save(ordner / "test.png")
        settings = QSettings(str(ordner / "einstellungen.ini"), QSettings.Format.IniFormat)
        fenster = Hauptfenster(settings)
        fenster.show()
        seite = fenster.werkzeug_oeffnen("umwandeln", [str(ordner / "test.png")])
        seite.format_waehlen("heif")
        seite.ablauf.ausgabe_ordner.setText(str(ordner / "aus"))
        seite.starten()
        ende = time.monotonic() + 60
        while seite.letztes_ergebnis is None and time.monotonic() < ende:
            app.processEvents()
            time.sleep(0.02)
        ergebnis = seite.letztes_ergebnis
        fenster.close()
        ok = ergebnis is not None and len(ergebnis.ok) == 1 and not ergebnis.fehler
        ziel = ordner / "aus" / "test.heic"
        ok = ok and ziel.is_file()
        zeilen.append(f"{'ok' if ok else 'FEHLER':<8}Fenster: {seite.status.text()}")
    return ok


def selbsttest(bericht: Path | None = None) -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from .. import __version__

    zeilen = [f"Miksan-Converter {__version__} – Selbsttest", f"Python {sys.version.split()[0]}"]
    ok = _module_pruefen(zeilen)
    ok = _modell_pruefen(zeilen) and ok
    ok = _ffmpeg_pruefen(zeilen) and ok
    try:
        ok = _design_pruefen(zeilen) and ok
    except Exception:
        ok = False
        zeilen.append("FEHLER  Design:\n" + traceback.format_exc())
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

# PyInstaller-Spec für Miksan-Converter (onedir).
#
# Erzeugt einen Ordner dist/Miksan-Converter/ mit zwei Programmen:
#   Miksan-Converter.exe  Oberfläche, ohne Konsolenfenster
#   miksan.exe            Kommandozeile
# Beide teilen sich dieselben Bibliotheken (_internal/). Qt-DLLs bleiben eigene Dateien
# (LGPL). KI-Modelle werden NICHT eingepackt, sie werden beim ersten Gebrauch geladen.
#
# Aufruf über packaging/windows/bauen.py (oder: pyinstaller packaging/windows/miksan.spec).

import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

HIER = Path(SPECPATH)  # noqa: F821 – von PyInstaller gesetzt
REPO = HIER.parent.parent
ICON = str(HIER / "miksan.ico")
# von bauen.py geschrieben (Dateieigenschaften der .exe unter Windows)
VERSION_INFO = REPO / "build" / "version_info.txt"
VERSION = str(VERSION_INFO) if sys.platform == "win32" and VERSION_INFO.is_file() else None

# Pakete, die PyInstaller nicht vollständig von selbst findet
versteckt = []
for paket in ("miksan_converter", "pillow_heif", "pymatting"):
    versteckt += collect_submodules(paket)
# rembg ohne eigene Kommandozeile (bräuchte click und weitere Pakete)
versteckt += collect_submodules(
    "rembg", filter=lambda name: not name.startswith(("rembg.cli", "rembg.commands"))
)
versteckt += ["resvg_py", "rawpy", "rawpy._rawpy", "onnxruntime"]

daten = collect_data_files("miksan_converter", includes=["**/*.png"])
daten += collect_data_files("rembg")
# Pakete, die zur Laufzeit ihre eigene Version über importlib.metadata abfragen
for paket in ("rembg", "pymatting", "pooch", "onnxruntime", "pillow_heif", "numba", "llvmlite"):
    daten += copy_metadata(paket)

binaer = []
for paket in ("pillow_heif", "rawpy", "resvg_py", "onnxruntime"):
    binaer += collect_dynamic_libs(paket)

# Nicht gebraucht: macht den Installer nur grösser
weglassen = [
    "tkinter",
    "matplotlib",
    "IPython",
    "pytest",
    "PySide6.QtNetwork",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtWebEngineCore",
    "PySide6.Qt3DCore",
    "PySide6.QtMultimedia",
]


def analyse(skript):
    return Analysis(  # noqa: F821
        [str(HIER / skript)],
        pathex=[str(REPO / "src"), str(HIER)],
        binaries=binaer,
        datas=daten,
        hiddenimports=versteckt,
        excludes=weglassen,
        # numba braucht für pymatting die Quelltexte (Cache-Suche über den Dateipfad)
        module_collection_mode={"pymatting": "py"},
        noarchive=False,
    )


gui = analyse("start_gui.py")
cli = analyse("start_cli.py")

exe_gui = EXE(  # noqa: F821
    PYZ(gui.pure),  # noqa: F821
    gui.scripts,
    [],
    exclude_binaries=True,
    name="Miksan-Converter",
    console=False,
    icon=ICON,
    version=VERSION,
    upx=False,
)
exe_cli = EXE(  # noqa: F821
    PYZ(cli.pure),  # noqa: F821
    cli.scripts,
    [],
    exclude_binaries=True,
    name="miksan",
    console=True,
    icon=ICON,
    version=VERSION,
    upx=False,
)

COLLECT(  # noqa: F821
    exe_gui,
    gui.binaries,
    gui.datas,
    exe_cli,
    cli.binaries,
    cli.datas,
    strip=False,
    upx=False,
    name="Miksan-Converter",
)

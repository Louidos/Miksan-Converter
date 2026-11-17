# PyInstaller-Spec für Miksan-Converter (onedir).
#
# Erzeugt einen Ordner dist/Miksan-Converter/ mit zwei Programmen:
#   Miksan-Converter.exe  Oberfläche, ohne Konsolenfenster
#   miksan.exe            Kommandozeile
# Beide teilen sich dieselben Bibliotheken (_internal/). Qt-DLLs bleiben eigene Dateien
# (LGPL). Das kleine KI-Modell (u2netp, Apache-2.0) wird mit Lizenz nach miksan_modelle/
# eingepackt, wenn bauen.py es nach build/modelle/ geladen hat; die grösseren Modelle werden
# bei Bedarf im Programm heruntergeladen.
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
for paket in ("miksan_converter", "pillow_heif", "pymatting", "pypdf", "pypdfium2", "imageio_ffmpeg"):
    versteckt += collect_submodules(paket)
# rembg ohne eigene Kommandozeile (bräuchte click und weitere Pakete)
versteckt += collect_submodules(
    "rembg", filter=lambda name: not name.startswith(("rembg.cli", "rembg.commands"))
)
versteckt += ["resvg_py", "rawpy", "rawpy._rawpy", "onnxruntime", "PySide6.QtSvg"]
versteckt += collect_submodules("pypdfium2_raw") + collect_submodules("pypdfium2_cfg")

# Programm-Icon und Linien-Icons (SVG) der Oberfläche
daten = collect_data_files("miksan_converter", includes=["**/*.png", "**/*.svg"])
daten += collect_data_files("rembg")
daten += collect_data_files("pypdfium2") + collect_data_files("pypdfium2_raw")
# ffmpeg-Programm aus imageio-ffmpeg (Extra [medien]); wird getrennt gestartet (GPL-3.0)
daten += collect_data_files("imageio_ffmpeg", includes=["binaries/*"])
# Mitgeliefertes Modell "klein" samt Lizenztexten (von bauen.py vorbereitet)
MODELLE = REPO / "build" / "modelle"
if (MODELLE / "u2netp.onnx").is_file():
    daten += [(str(datei), "miksan_modelle") for datei in MODELLE.iterdir() if datei.is_file()]
# Pakete, die zur Laufzeit ihre eigene Version über importlib.metadata abfragen
for paket in (
    "rembg",
    "pymatting",
    "pooch",
    "onnxruntime",
    "pillow_heif",
    "numba",
    "llvmlite",
    "pypdf",
    "pypdfium2",
    "imageio_ffmpeg",
):
    daten += copy_metadata(paket)

binaer = []
for paket in ("pillow_heif", "rawpy", "resvg_py", "onnxruntime", "pypdfium2_raw"):
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

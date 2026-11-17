"""Baut den Windows-Installer: erst PyInstaller (onedir), dann Inno Setup.

Aufruf im Repo-Ordner (Windows):

    uv sync --locked --extra gui --extra svg --extra raw --extra ki --group installer
    uv run python packaging/windows/bauen.py

Ergebnis: ``dist/MiksanConverter-Setup-X.Y.Z.exe``. Die Version kommt aus ``pyproject.toml``.
Mit ``--nur-programm`` wird nur der Programmordner ``build/programm/Miksan-Converter/`` gebaut
(geht auch unter Linux/macOS, z. B. zum Prüfen der versteckten Importe).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tomllib
import urllib.request
from pathlib import Path

HIER = Path(__file__).resolve().parent
REPO = HIER.parent.parent
BUILD = REPO / "build"
DIST = REPO / "dist"
PROGRAMM = BUILD / "programm" / "Miksan-Converter"
MODELLE = BUILD / "modelle"  # wird von miksan.spec als miksan_modelle/ eingepackt

# Standardmodell "klein" (u2netp, Apache-2.0) – damit Hintergrund entfernen offline geht
MODELL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
MODELL_MD5 = "8e83ca70e441ab06c318d82300c84806"

_ISCC_ORTE = (
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6",
)


def version_lesen() -> str:
    with open(REPO / "pyproject.toml", "rb") as datei:
        version = tomllib.load(datei)["project"]["version"]
    init = (REPO / "src" / "miksan_converter" / "__init__.py").read_text(encoding="utf-8")
    treffer = re.search(r'__version__ = "([^"]+)"', init)
    if not treffer or treffer.group(1) != version:
        sys.exit(
            f"Version passt nicht: pyproject.toml {version}, "
            f"__init__.py {treffer.group(1) if treffer else '?'}"
        )
    return version


def version_info_schreiben(version: str) -> Path:
    """Dateieigenschaften der .exe (Rechtsklick -> Eigenschaften -> Details)."""
    zahlen = [int(z) for z in re.findall(r"\d+", version)[:3]]
    zahlen += [0] * (4 - len(zahlen))
    tupel = tuple(zahlen)
    felder = {
        "CompanyName": "Louidos",
        "FileDescription": "Miksan-Converter – Bilder umwandeln und bearbeiten",
        "FileVersion": version,
        "InternalName": "Miksan-Converter",
        "LegalCopyright": "MIT-Lizenz",
        "ProductName": "Miksan-Converter",
        "ProductVersion": version,
    }
    eintraege = ",\n          ".join(f"StringStruct({k!r}, {v!r})" for k, v in felder.items())
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={tupel}, prodvers={tupel}, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([
      StringTable('040704b0', [
          {eintraege}
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [0x0407, 1200])])
  ]
)
"""
    BUILD.mkdir(exist_ok=True)
    pfad = BUILD / "version_info.txt"
    pfad.write_text(text, encoding="utf-8")
    return pfad


def modell_holen() -> Path:
    """Lädt das kleine Modell einmal nach build/modelle/ und prüft die Prüfsumme."""
    ziel = MODELLE / "u2netp.onnx"

    def stimmt() -> bool:
        return ziel.is_file() and hashlib.md5(ziel.read_bytes()).hexdigest() == MODELL_MD5

    if not stimmt():
        MODELLE.mkdir(parents=True, exist_ok=True)
        print(f"Lade {MODELL_URL}", flush=True)
        urllib.request.urlretrieve(MODELL_URL, ziel)
        if not stimmt():
            ziel.unlink(missing_ok=True)
            sys.exit("Prüfsumme des Modells u2netp.onnx stimmt nicht.")
    for name in ("U-2-Net-LICENSE.txt", "MODELLE.txt"):
        shutil.copyfile(HIER / "lizenzen" / name, MODELLE / name)
    return ziel


def kontextmenue_endungen() -> list[str]:
    """Alle Endungen, für die der Explorer „Mit Miksan-Converter öffnen“ zeigt."""
    sys.path.insert(0, str(REPO / "src"))
    from miksan_converter.formats import bekannte_bild_endungen
    from miksan_converter.gui.werkzeuge import AUDIO_ENDUNGEN, PDF_ENDUNGEN, VIDEO_ENDUNGEN

    alle = bekannte_bild_endungen() | PDF_ENDUNGEN | VIDEO_ENDUNGEN | AUDIO_ENDUNGEN
    return sorted(endung.lower() for endung in alle if re.fullmatch(r"\.[a-z0-9]+", endung.lower()))


def kontextmenue_schreiben() -> Path:
    """Registry-Einträge für Inno Setup (Rechtsklick-Menü), nur mit der Aufgabe kontextmenue.

    SystemFileAssociations ändert keine Standardprogramme; HKA = HKCU bzw. HKLM je nach
    Installationsart. Beim Deinstallieren werden die Schlüssel entfernt.
    """
    befehl = '"""{app}\\{#AppExe}"" ""%1"""'
    zeilen = ["; Von bauen.py erzeugt – nicht von Hand ändern", "[Registry]"]
    schluessel = [
        f"Software\\Classes\\SystemFileAssociations\\{e}" for e in kontextmenue_endungen()
    ]
    schluessel.append("Software\\Classes\\Directory")
    for basis in schluessel:
        verb = f"{basis}\\shell\\MiksanConverter"
        gemeinsam = "Flags: uninsdeletekey; Tasks: kontextmenue"
        zeilen.append(
            f'Root: HKA; Subkey: "{verb}"; ValueType: string; ValueName: ""; '
            f'ValueData: "{{cm:KontextEintrag}}"; {gemeinsam}'
        )
        zeilen.append(
            f'Root: HKA; Subkey: "{verb}"; ValueType: string; ValueName: "Icon"; '
            f'ValueData: """{{app}}\\{{#AppExe}}"",0"; {gemeinsam}'
        )
        zeilen.append(
            f'Root: HKA; Subkey: "{verb}\\command"; ValueType: string; ValueName: ""; '
            f"ValueData: {befehl}; {gemeinsam}"
        )
    BUILD.mkdir(exist_ok=True)
    pfad = BUILD / "kontextmenue.iss"
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8-sig")
    return pfad


def pyinstaller() -> None:
    befehl = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(HIER / "miksan.spec"),
        "--noconfirm",
        "--clean",
        "--distpath",
        str(PROGRAMM.parent),
        "--workpath",
        str(BUILD / "pyinstaller"),
    ]
    print("+", " ".join(befehl), flush=True)
    subprocess.run(befehl, check=True, cwd=REPO)


def iscc_finden(angegeben: str | None) -> Path:
    if angegeben:
        return Path(angegeben)
    for kandidat in (os.environ.get("ISCC"), shutil.which("iscc")):
        if kandidat:
            return Path(kandidat)
    for ort in _ISCC_ORTE:
        if (ort / "ISCC.exe").is_file():
            return ort / "ISCC.exe"
    sys.exit(
        "Inno Setup (ISCC.exe) nicht gefunden. Installieren mit `choco install innosetup` oder "
        "von https://jrsoftware.org/isdl.php, oder den Pfad mit --iscc angeben."
    )


def inno_setup(iscc: Path, version: str) -> Path:
    DIST.mkdir(exist_ok=True)
    befehl = [
        str(iscc),
        f"/DAppVersion={version}",
        f"/DQuelle={PROGRAMM}",
        f"/DRepo={REPO}",
        f"/DKontext={kontextmenue_schreiben()}",
        f"/O{DIST}",
        str(HIER / "installer.iss"),
    ]
    print("+", " ".join(befehl), flush=True)
    subprocess.run(befehl, check=True, cwd=HIER)
    return DIST / f"MiksanConverter-Setup-{version}.exe"


def main() -> int:
    parser = argparse.ArgumentParser(description="Windows-Installer bauen")
    parser.add_argument(
        "--nur-programm", action="store_true", help="nur PyInstaller, kein Installer"
    )
    parser.add_argument("--iscc", help="Pfad zu ISCC.exe (Inno Setup)")
    parser.add_argument(
        "--ohne-modell", action="store_true", help="das kleine KI-Modell nicht mitliefern"
    )
    args = parser.parse_args()

    version = version_lesen()
    print(f"Miksan-Converter {version}")
    version_info_schreiben(version)
    if args.ohne_modell:
        shutil.rmtree(MODELLE, ignore_errors=True)
    else:
        print(f"Mitgeliefertes Modell: {modell_holen()}")
    iscc = None if args.nur_programm else iscc_finden(args.iscc)
    pyinstaller()
    print(f"Programmordner: {PROGRAMM}")
    if iscc is None:
        return 0
    installer = inno_setup(iscc, version)
    groesse = installer.stat().st_size / 1024**2
    print(f"Installer: {installer} ({groesse:.0f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

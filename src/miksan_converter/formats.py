"""Verzeichnis aller unterstützten Bildformate und Erkennung am Dateiinhalt."""

from __future__ import annotations

import importlib.util
import zlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .fehler import BedienFehler


@dataclass(frozen=True)
class Format:
    name: str
    beschreibung: str
    endungen: tuple[str, ...]
    pil_name: str | None
    lesen: bool = True
    schreiben: bool = True
    alpha: bool = False
    modi: tuple[str, ...] = ("RGB",)
    icc: bool = False
    exif: bool = False
    animation: bool = False
    mehrseitig: bool = False
    verlustbehaftet: bool = False
    extra: str | None = None
    einschraenkung: str = ""

    @property
    def endung(self) -> str:
        return self.endungen[0]


_MODI_ALLE = ("1", "L", "LA", "P", "RGB", "RGBA", "CMYK", "I;16", "I", "F")

FORMATE: tuple[Format, ...] = (
    Format(
        "png",
        "Portable Network Graphics",
        (".png", ".apng"),
        "PNG",
        alpha=True,
        modi=("1", "L", "LA", "P", "RGB", "RGBA", "I;16", "I"),
        icc=True,
        exif=True,
        animation=True,
        einschraenkung="Animation als APNG",
    ),
    Format(
        "jpeg",
        "JPEG",
        (".jpg", ".jpeg", ".jpe", ".jfif"),
        "JPEG",
        modi=("L", "RGB", "CMYK"),
        icc=True,
        exif=True,
        verlustbehaftet=True,
        einschraenkung="keine Transparenz (wird auf --background gelegt)",
    ),
    Format(
        "webp",
        "WebP",
        (".webp",),
        "WEBP",
        alpha=True,
        modi=("RGB", "RGBA"),
        icc=True,
        exif=True,
        animation=True,
        verlustbehaftet=True,
        einschraenkung="verlustfrei, wenn die Quelle verlustfrei ist",
    ),
    Format(
        "gif",
        "Graphics Interchange Format",
        (".gif",),
        "GIF",
        alpha=True,
        modi=("1", "L", "P", "RGB", "RGBA"),
        animation=True,
        einschraenkung="max. 256 Farben, Transparenz nur an/aus",
    ),
    Format(
        "bmp",
        "Windows Bitmap",
        (".bmp", ".dib"),
        "BMP",
        modi=("1", "L", "P", "RGB"),
        einschraenkung="keine Transparenz",
    ),
    Format(
        "tiff",
        "Tagged Image File Format",
        (".tif", ".tiff"),
        "TIFF",
        alpha=True,
        modi=_MODI_ALLE,
        icc=True,
        exif=True,
        mehrseitig=True,
        einschraenkung="mehrseitig; verlustfrei komprimiert (Deflate)",
    ),
    Format(
        "ico",
        "Windows-Symbol",
        (".ico",),
        "ICO",
        alpha=True,
        modi=("RGBA",),
        einschraenkung="max. 256x256, mehrere Grössen, wird quadratisch aufgefüllt",
    ),
    Format(
        "tga",
        "Truevision TGA",
        (".tga", ".icb", ".vda", ".vst"),
        "TGA",
        alpha=True,
        modi=("L", "LA", "P", "RGB", "RGBA"),
    ),
    Format(
        "ppm",
        "Netpbm (PPM/PGM/PBM)",
        (".ppm", ".pgm", ".pbm", ".pnm"),
        "PPM",
        modi=("1", "L", "RGB", "I;16"),
        einschraenkung="keine Transparenz",
    ),
    Format(
        "pdf",
        "Portable Document Format",
        (".pdf",),
        "PDF",
        lesen=False,
        modi=("1", "L", "RGB", "CMYK"),
        mehrseitig=True,
        einschraenkung="nur Schreiben; keine Transparenz",
    ),
    Format(
        "avif",
        "AV1 Image File Format",
        (".avif", ".avifs"),
        "AVIF",
        alpha=True,
        modi=("RGB", "RGBA"),
        icc=True,
        exif=True,
        animation=True,
        verlustbehaftet=True,
    ),
    Format(
        "heif",
        "HEIC/HEIF (z. B. iPhone-Fotos)",
        (".heic", ".heif", ".hif"),
        "HEIF",
        alpha=True,
        modi=("RGB", "RGBA"),
        icc=True,
        exif=True,
        verlustbehaftet=True,
        einschraenkung="über pillow-heif",
    ),
    Format(
        "jpeg2000",
        "JPEG 2000",
        (".jp2", ".j2k", ".j2c", ".jpx", ".jpf"),
        "JPEG2000",
        alpha=True,
        modi=("L", "LA", "RGB", "RGBA"),
        einschraenkung="verlustfrei gespeichert",
    ),
    Format(
        "qoi",
        "Quite OK Image",
        (".qoi",),
        "QOI",
        alpha=True,
        modi=("RGB", "RGBA"),
    ),
    Format(
        "svg",
        "Scalable Vector Graphics",
        (".svg", ".svgz"),
        None,
        schreiben=False,
        extra="svg",
        einschraenkung="nur Lesen, wird in ein Rasterbild umgewandelt",
    ),
    Format(
        "raw",
        "Kamera-RAW (DNG, CR2, CR3, NEF, ARW, RAF, ORF, RW2, PEF …)",
        (
            ".dng",
            ".cr2",
            ".cr3",
            ".crw",
            ".nef",
            ".nrw",
            ".arw",
            ".srf",
            ".sr2",
            ".raf",
            ".orf",
            ".rw2",
            ".raw",
            ".pef",
            ".srw",
            ".x3f",
            ".erf",
            ".3fr",
            ".iiq",
            ".mrw",
            ".kdc",
            ".dcr",
            ".mos",
            ".rwl",
        ),
        None,
        schreiben=False,
        extra="raw",
        einschraenkung="nur Lesen, Entwicklung mit Kamera-Weissabgleich",
    ),
)

_KURZNAMEN = {
    "jpg": "jpeg",
    "tif": "tiff",
    "heic": "heif",
    "jp2": "jpeg2000",
    "pgm": "ppm",
    "pbm": "ppm",
    "pnm": "ppm",
}

# Pillow-Formatnamen, die einem unserer Formate entsprechen
_PIL_ALIASE = {"MPO": "jpeg", "APNG": "png"}

# Paketname des Extras -> Python-Modul, an dem es erkannt wird
_EXTRA_MODULE = {"svg": "resvg_py", "raw": "rawpy", "ki": "rembg", "gui": "PySide6"}


def alle_formate() -> tuple[Format, ...]:
    return FORMATE


def extra_installiert(extra: str) -> bool:
    return importlib.util.find_spec(_EXTRA_MODULE[extra]) is not None


_NACH_NAME = {fmt.name: fmt for fmt in FORMATE}


def format_nach_name(name: str) -> Format:
    return _NACH_NAME[name]


def format_aus_name(name: str) -> Format:
    """Findet ein Zielformat über seinen Namen oder eine Endung (z. B. ``jpg``, ``.png``)."""
    schluessel = name.lower().lstrip(".")
    schluessel = _KURZNAMEN.get(schluessel, schluessel)
    for fmt in FORMATE:
        if fmt.name == schluessel or f".{schluessel}" in fmt.endungen:
            if not fmt.schreiben:
                raise BedienFehler(
                    f"Das Format '{name}' kann nur gelesen, nicht geschrieben werden."
                )
            return fmt
    namen = ", ".join(f.name for f in FORMATE if f.schreiben)
    raise BedienFehler(f"Unbekanntes Format '{name}'. Unterstützt werden: {namen}")


def format_aus_endung(pfad: Path) -> Format | None:
    endung = pfad.suffix.lower()
    if not endung:
        return None
    for fmt in FORMATE:
        if endung in fmt.endungen:
            return fmt
    return None


def format_aus_pil(pil_name: str | None) -> Format | None:
    """Ordnet den von Pillow erkannten Formatnamen einem unserer Formate zu."""
    if pil_name is None:
        return None
    if pil_name in _PIL_ALIASE:
        return format_nach_name(_PIL_ALIASE[pil_name])
    for fmt in FORMATE:
        if fmt.pil_name == pil_name:
            return fmt
    return None


def pil_kann_schreiben(fmt: Format) -> bool:
    from . import convert  # noqa: F401 – registriert HEIF bei Pillow

    Image.init()
    return fmt.pil_name in Image.SAVE


def bekannte_bild_endungen() -> set[str]:
    return {endung for fmt in FORMATE if fmt.lesen for endung in fmt.endungen}


# --- Erkennung am Dateiinhalt -------------------------------------------------

_RAW_SIGNATUREN = (
    b"FUJIFILMCCD-RAW",  # RAF
    b"IIRO",  # ORF
    b"IIRS",  # ORF
    b"MMOR",  # ORF
    b"IIU\x00",  # RW2
    b"FOVb",  # X3F
    b"\x00MRM",  # MRW
)

_TIFF_KOPF = (b"II*\x00", b"MM\x00*")
_TAG_MAKE = 271
_TAG_SUBIFDS = 330
_TAG_DNG_VERSION = 50706


def ist_svg(kopf: bytes) -> bool:
    if kopf[:2] == b"\x1f\x8b":  # SVGZ
        try:
            kopf = zlib.decompressobj(31).decompress(kopf, 4096)
        except zlib.error:
            return False
    text = kopf[:4096].lstrip(b"\xef\xbb\xbf").lstrip().lower()
    if not (text.startswith(b"<?xml") or text.startswith(b"<svg") or text.startswith(b"<!")):
        return False
    return b"<svg" in text


def ist_raw_signatur(kopf: bytes) -> bool:
    if kopf.startswith(_RAW_SIGNATUREN):
        return True
    if kopf[:4] in _TIFF_KOPF and kopf[8:11] == b"CR\x02":  # Canon CR2
        return True
    return kopf[4:8] == b"ftyp" and kopf[8:12] == b"crx "  # Canon CR3


def ist_raw_tiff(bild: Image.Image) -> bool:
    """Erkennt TIFF-basierte RAW-Dateien (DNG, NEF, ARW, PEF …) an ihren Tags."""
    tags = getattr(bild, "tag_v2", None)
    if tags is None:
        return False
    if _TAG_DNG_VERSION in tags:
        return True
    return _TAG_MAKE in tags and _TAG_SUBIFDS in tags


def kopf_lesen(pfad: Path, anzahl: int = 4096) -> bytes:
    with open(pfad, "rb") as datei:
        return datei.read(anzahl)


# --- Formatliste --------------------------------------------------------------


def _ja_nein(wert: bool) -> str:
    return "ja" if wert else "nein"


def tabellen_zeilen() -> list[tuple[str, ...]]:
    zeilen = [("Format", "Endungen", "Lesen", "Schreiben", "Extra", "Einschränkungen")]
    for fmt in FORMATE:
        extra = f"[{fmt.extra}]" if fmt.extra else "–"
        zeilen.append(
            (
                fmt.name,
                " ".join(fmt.endungen),
                _ja_nein(fmt.lesen),
                _ja_nein(fmt.schreiben),
                extra,
                fmt.einschraenkung or "–",
            )
        )
    return zeilen


def markdown_tabelle() -> str:
    zeilen = tabellen_zeilen()
    ausgabe = ["| " + " | ".join(zeilen[0]) + " |", "|" + "---|" * len(zeilen[0])]
    for zeile in zeilen[1:]:
        felder = list(zeile)
        felder[1] = " ".join(f"`{e}`" for e in zeile[1].split())
        ausgabe.append("| " + " | ".join(felder) + " |")
    return "\n".join(ausgabe)

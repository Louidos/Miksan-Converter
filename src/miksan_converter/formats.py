"""Verzeichnis aller unterstützten Bildformate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .fehler import BedienFehler


@dataclass(frozen=True)
class Format:
    name: str
    beschreibung: str
    endungen: tuple[str, ...]
    pil_name: str
    lesen: bool = True
    schreiben: bool = True
    alpha: bool = False

    @property
    def endung(self) -> str:
        return self.endungen[0]


FORMATE: tuple[Format, ...] = (
    Format("png", "Portable Network Graphics", (".png",), "PNG", alpha=True),
    Format("jpeg", "JPEG", (".jpg", ".jpeg", ".jpe", ".jfif"), "JPEG"),
    Format("webp", "WebP", (".webp",), "WEBP", alpha=True),
    Format("gif", "Graphics Interchange Format", (".gif",), "GIF", alpha=True),
    Format("bmp", "Windows Bitmap", (".bmp", ".dib"), "BMP"),
    Format("tiff", "Tagged Image File Format", (".tif", ".tiff"), "TIFF", alpha=True),
)

_KURZNAMEN = {"jpg": "jpeg", "tif": "tiff"}


def alle_formate() -> tuple[Format, ...]:
    return FORMATE


def format_aus_name(name: str) -> Format:
    """Findet ein Format über seinen Namen oder eine Endung (z. B. ``jpg``, ``.png``)."""
    schluessel = name.lower().lstrip(".")
    schluessel = _KURZNAMEN.get(schluessel, schluessel)
    for fmt in FORMATE:
        if fmt.name == schluessel or f".{schluessel}" in fmt.endungen:
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
    for fmt in FORMATE:
        if fmt.pil_name == pil_name:
            return fmt
    return None


def pil_kann_schreiben(fmt: Format) -> bool:
    Image.init()
    return fmt.pil_name in Image.SAVE

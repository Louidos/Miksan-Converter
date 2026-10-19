"""Erzeugt kleine Testbilder für alle Formate.

Aufruf: ``python scripts/testbilder_erzeugen.py [ZIELORDNER]``
(Standard: ``tests/fixtures/erzeugt``). Die Tests rufen ``erzeugen()`` selbst auf, damit keine
Binärdateien eingecheckt werden müssen.
"""

from __future__ import annotations

import sys
from functools import cache
from pathlib import Path

import pillow_heif
from PIL import Image, ImageCms

pillow_heif.register_heif_opener()

BREITE, HOEHE = 32, 24
FARBE = (30, 120, 200)
TRANSPARENT_BIS_X = 8

# Formatname -> (Dateiname, Pillow-Format, mit Transparenz)
QUELLEN = {
    "png": ("quelle.png", "PNG", True),
    "jpeg": ("quelle.jpg", "JPEG", False),
    "webp": ("quelle.webp", "WEBP", True),
    "gif": ("quelle.gif", "GIF", True),
    "bmp": ("quelle.bmp", "BMP", False),
    "tiff": ("quelle.tif", "TIFF", True),
    "ico": ("quelle.ico", "ICO", True),
    "tga": ("quelle.tga", "TGA", True),
    "ppm": ("quelle.ppm", "PPM", False),
    "avif": ("quelle.avif", "AVIF", True),
    "heif": ("quelle.heic", "HEIF", True),
    "jpeg2000": ("quelle.jp2", "JPEG2000", True),
    "qoi": ("quelle.qoi", "QOI", True),
}

SVG = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="32" height="24" viewBox="0 0 32 24">
  <rect x="8" y="0" width="24" height="24" fill="rgb(30,120,200)"/>
</svg>
"""


@cache
def srgb_profil() -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def grundbild(transparent: bool) -> Image.Image:
    """32x24 Pixel in FARBE; bei Transparenz sind die ersten 8 Spalten durchsichtig."""
    bild = Image.new("RGBA", (BREITE, HOEHE), (*FARBE, 255))
    if transparent:
        bild.paste((0, 0, 0, 0), (0, 0, TRANSPARENT_BIS_X, HOEHE))
        return bild
    return bild.convert("RGB")


def _quelle_speichern(pfad: Path, pil_format: str, transparent: bool) -> None:
    bild = grundbild(transparent)
    optionen: dict = {}
    if pil_format == "ICO":
        optionen["sizes"] = [(32, 32)]
        leinwand = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        leinwand.paste(bild, (0, 4))
        bild = leinwand
    elif pil_format in ("AVIF", "HEIF", "WEBP", "JPEG"):
        optionen["quality"] = 95
    if pil_format == "WEBP":
        optionen["lossless"] = True
    bild.save(pfad, pil_format, **optionen)


def erzeugen(ordner: Path) -> dict[str, Path]:
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)
    dateien: dict[str, Path] = {}

    for name, (dateiname, pil_format, transparent) in QUELLEN.items():
        pfad = ordner / dateiname
        _quelle_speichern(pfad, pil_format, transparent)
        dateien[name] = pfad

    svg = ordner / "quelle.svg"
    svg.write_text(SVG, encoding="utf-8")
    dateien["svg"] = svg

    # Animation mit drei Einzelbildern
    frames = [
        Image.new("RGB", (20, 10), farbe) for farbe in ((255, 0, 0), (0, 255, 0), (0, 0, 255))
    ]
    for name, pil_format in (("animiert_gif", "GIF"), ("animiert_webp", "WEBP")):
        pfad = ordner / f"animiert.{pil_format.lower()}"
        frames[0].save(
            pfad, pil_format, save_all=True, append_images=frames[1:], duration=120, loop=0
        )
        dateien[name] = pfad

    # Mehrseitiges TIFF
    seiten = ordner / "mehrseitig.tif"
    frames[0].save(seiten, "TIFF", save_all=True, append_images=frames[1:])
    dateien["mehrseitig"] = seiten

    # Handyfoto im HEIC-Format: quer gespeichert, EXIF-Ausrichtung 6 (90° drehen), sRGB-Profil
    handy = Image.new("RGB", (40, 20), (220, 0, 0))
    handy.paste((0, 0, 220), (20, 0, 40, 20))
    exif = Image.Exif()
    exif[0x0112] = 6
    exif[0x010F] = "Testkamera"
    heic = ordner / "handy.heic"
    handy.save(heic, "HEIF", exif=exif.tobytes(), icc_profile=srgb_profil(), quality=95)
    dateien["handy_heic"] = heic

    # JPEG mit EXIF-Ausrichtung, Kamera und GPS
    exif = Image.Exif()
    exif[0x0112] = 6
    exif[0x010F] = "Testkamera"
    exif.get_ifd(0x8825).update({1: "N", 2: (47.0, 22.0, 0.0), 3: "E", 4: (8.0, 32.0, 0.0)})
    jpg = ordner / "exif.jpg"
    handy.save(jpg, "JPEG", exif=exif.tobytes(), icc_profile=srgb_profil(), quality=95)
    dateien["exif_jpg"] = jpg

    # Transparentes PNG (halb transparent, halb deckend)
    transparent = ordner / "transparent.png"
    grundbild(True).save(transparent)
    dateien["transparent_png"] = transparent

    # 16-Bit-Graustufen
    tief = ordner / "16bit.png"
    Image.new("I;16", (8, 8), 32768).save(tief)
    dateien["png16"] = tief

    # CMYK-JPEG
    cmyk = ordner / "cmyk.jpg"
    Image.new("CMYK", (8, 8), (0, 255, 255, 0)).save(cmyk, quality=95)
    dateien["cmyk_jpg"] = cmyk

    # Symbol mit mehreren Grössen
    ico = ordner / "mehrfach.ico"
    Image.new("RGBA", (48, 48), (*FARBE, 255)).save(ico, sizes=[(16, 16), (32, 32), (48, 48)])
    dateien["ico_mehrfach"] = ico

    # Beschädigte Dateien: abgeschnitten
    for name, quelle in (("kaputt_png", "png"), ("kaputt_jpg", "jpeg")):
        gross = ordner / f"gross_{name}.{quelle}"
        Image.effect_noise((64, 64), 50).convert("RGB").save(gross, QUELLEN[quelle][1])
        kaputt = ordner / f"kaputt.{QUELLEN[quelle][0].split('.')[-1]}"
        kaputt.write_bytes(gross.read_bytes()[: gross.stat().st_size // 2])
        gross.unlink()
        dateien[name] = kaputt

    return dateien


if __name__ == "__main__":
    ziel = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/fixtures/erzeugt")
    for name, pfad in erzeugen(ziel).items():
        print(f"{name:15} {pfad}")

"""Wasserzeichen: Text oder Logo, an einer von neun Positionen oder gekachelt."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..convert import Ergebnis, farbe_parsen, laden
from ..fehler import BedienFehler
from ._gemeinsam import je_bild

POSITIONEN = (
    "oben-links",
    "oben",
    "oben-rechts",
    "links",
    "mitte",
    "rechts",
    "unten-links",
    "unten",
    "unten-rechts",
    "gekachelt",
)
STANDARD_POSITION = "unten-rechts"


def _text_bild(text: str, breite: int, farbe: tuple[int, int, int]) -> Image.Image:
    """Text als RGBA-Bild, etwa ``breite`` Pixel breit, mit dunklem Rand für Lesbarkeit."""
    probe = ImageFont.load_default(100)
    links, oben, rechts, unten = probe.getbbox(text, stroke_width=4)
    groesse = max(6, round(100 * breite / max(1, rechts - links)))
    schrift = ImageFont.load_default(groesse)
    rand = max(1, groesse // 25)
    links, oben, rechts, unten = schrift.getbbox(text, stroke_width=rand)
    bild = Image.new("RGBA", (rechts - links + 2, unten - oben + 2), (0, 0, 0, 0))
    ImageDraw.Draw(bild).text(
        (1 - links, 1 - oben),
        text,
        font=schrift,
        fill=(*farbe, 255),
        stroke_width=rand,
        stroke_fill=(0, 0, 0, 160),
    )
    return bild


def _deckkraft(bild: Image.Image, deckkraft: int) -> Image.Image:
    bild = bild.convert("RGBA")
    alpha = bild.getchannel("A").point(lambda wert: wert * deckkraft // 100)
    bild.putalpha(alpha)
    return bild


def zeichen_erstellen(
    breite_bild: int,
    *,
    text: str | None = None,
    logo: Image.Image | None = None,
    groesse: float = 20,
    deckkraft: int = 50,
    farbe: tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """Das Wasserzeichen allein (RGBA), ``groesse`` in Prozent der Bildbreite."""
    if not 1 <= groesse <= 100:
        raise BedienFehler("Die Grösse muss zwischen 1 und 100 % der Bildbreite liegen.")
    if not 0 <= deckkraft <= 100:
        raise BedienFehler("Die Deckkraft muss zwischen 0 und 100 % liegen.")
    breite = max(4, round(breite_bild * groesse / 100))
    if logo is not None:
        logo = logo.convert("RGBA")
        hoehe = max(1, round(logo.height * breite / logo.width))
        zeichen = logo.resize((breite, hoehe), Image.Resampling.LANCZOS)
    elif text and text.strip():
        zeichen = _text_bild(text.strip(), breite, farbe)
    else:
        raise BedienFehler("Bitte einen Text oder ein Logo für das Wasserzeichen angeben.")
    return _deckkraft(zeichen, deckkraft)


def _ort(position: str, bild: tuple[int, int], zeichen: tuple[int, int], rand: int):
    spalte = 0 if position.endswith("links") else 2 if position.endswith("rechts") else 1
    zeile = 0 if position.startswith("oben") else 2 if position.startswith("unten") else 1
    x = (rand, (bild[0] - zeichen[0]) // 2, bild[0] - zeichen[0] - rand)[spalte]
    y = (rand, (bild[1] - zeichen[1]) // 2, bild[1] - zeichen[1] - rand)[zeile]
    return x, y


def anwenden(
    bild: Image.Image,
    *,
    text: str | None = None,
    logo: Image.Image | None = None,
    position: str = STANDARD_POSITION,
    groesse: float = 20,
    deckkraft: int = 50,
    farbe: tuple[int, int, int] = (255, 255, 255),
) -> Image.Image:
    """Legt das Wasserzeichen auf ein Bild; der Modus des Bildes bleibt erhalten."""
    if position not in POSITIONEN:
        raise BedienFehler(f"Position '{position}' gibt es nicht. Möglich: {', '.join(POSITIONEN)}")
    modus = bild.mode
    ergebnis = bild.convert("RGBA")
    zeichen = zeichen_erstellen(
        ergebnis.width, text=text, logo=logo, groesse=groesse, deckkraft=deckkraft, farbe=farbe
    )
    ebene = Image.new("RGBA", ergebnis.size, (0, 0, 0, 0))
    if position == "gekachelt":
        gedreht = zeichen.rotate(30, expand=True, resample=Image.Resampling.BICUBIC)
        rb, rh = gedreht.size
        # auf einer grösseren Ebene kacheln (nur positive Koordinaten), dann zuschneiden
        gross = Image.new("RGBA", (ergebnis.width + 2 * rb, ergebnis.height + 2 * rh))
        schritt_x, schritt_y = max(1, round(rb * 1.6)), max(1, round(rh * 2.0))
        for zeile, y in enumerate(range(rh // 2, gross.height - rh, schritt_y)):
            for x in range((schritt_x // 2) * (zeile % 2), gross.width - rb, schritt_x):
                gross.alpha_composite(gedreht, (x, y))
        ebene = gross.crop((rb, rh, rb + ergebnis.width, rh + ergebnis.height))
    else:
        rand = max(1, round(ergebnis.width * 0.02))
        x, y = _ort(position, ergebnis.size, zeichen.size, rand)
        ebene.alpha_composite(zeichen, (max(x, 0), max(y, 0)))
    ergebnis = Image.alpha_composite(ergebnis, ebene)
    if modus in ("RGBA", "LA", "PA") or (modus == "P" and "transparency" in bild.info):
        return ergebnis
    return ergebnis.convert("RGB")


def wasserzeichen(
    eingabe: str | Path,
    ausgabe: str | Path | None = None,
    *,
    text: str | None = None,
    logo: str | Path | None = None,
    position: str = STANDARD_POSITION,
    groesse: float = 20,
    deckkraft: int = 50,
    farbe: str = "#ffffff",
    to: str | None = None,
    overwrite: bool = False,
) -> Ergebnis:
    """Speichert ``eingabe`` mit Wasserzeichen; ohne Ausgabe ``<name>-wasserzeichen``."""
    logo_bild = laden(Path(logo)).frames[0] if logo else None
    rgb = farbe_parsen(farbe)
    if position not in POSITIONEN:
        raise BedienFehler(f"Position '{position}' gibt es nicht. Möglich: {', '.join(POSITIONEN)}")
    zeichen_erstellen(100, text=text, logo=logo_bild, groesse=groesse, deckkraft=deckkraft)
    return je_bild(
        eingabe,
        ausgabe,
        "wasserzeichen",
        lambda frame: anwenden(
            frame,
            text=text,
            logo=logo_bild,
            position=position,
            groesse=groesse,
            deckkraft=deckkraft,
            farbe=rgb,
        ),
        to=to,
        overwrite=overwrite,
    )

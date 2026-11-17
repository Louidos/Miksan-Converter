"""Icon-Set: aus einem Bild ``favicon.ico`` (16–256 px) und PNG-Icons in üblichen Grössen."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from ..convert import _datei_schreiben, laden

ICO_GROESSEN = (16, 24, 32, 48, 64, 128, 256)
PNG_GROESSEN = (16, 32, 48, 180, 192, 512)


def quadratisch(bild: Image.Image) -> Image.Image:
    """Macht ein Bild quadratisch (zentriert, Rest transparent)."""
    bild = bild.convert("RGBA")
    seite = max(bild.size)
    leinwand = Image.new("RGBA", (seite, seite), (0, 0, 0, 0))
    leinwand.paste(bild, ((seite - bild.width) // 2, (seite - bild.height) // 2))
    return leinwand


def png_name(groesse: int) -> str:
    return f"icon-{groesse}x{groesse}.png"


def erstellen(
    eingabe: str | Path, ausgabe_ordner: str | Path | None = None, *, overwrite: bool = False
) -> list[Path]:
    """Schreibt ``favicon.ico`` und ``icon-16x16.png`` … ``icon-512x512.png``.

    Ohne Ordner entsteht ``<name>-icons/`` neben dem Bild. Kleine Bilder werden hochgerechnet.
    """
    eingabe = Path(eingabe)
    ordner = Path(ausgabe_ordner) if ausgabe_ordner else eingabe.parent / f"{eingabe.stem}-icons"
    ordner.mkdir(parents=True, exist_ok=True)
    quadrat = quadratisch(laden(eingabe).frames[0])

    def skaliert(groesse: int) -> Image.Image:
        return quadrat.resize((groesse, groesse), Image.Resampling.LANCZOS)

    ergebnisse = []
    ico = ordner / "favicon.ico"
    ico_bilder = [skaliert(g) for g in ICO_GROESSEN]
    _datei_schreiben(
        ico,
        lambda datei: ico_bilder[-1].save(
            datei,
            format="ICO",
            sizes=[(g, g) for g in ICO_GROESSEN],
            append_images=ico_bilder[:-1],
        ),
        overwrite,
    )
    ergebnisse.append(ico)
    for groesse in PNG_GROESSEN:
        ziel = ordner / png_name(groesse)
        bild = skaliert(groesse)
        _datei_schreiben(
            ziel, lambda datei, b=bild: b.save(datei, format="PNG", optimize=True), overwrite
        )
        ergebnisse.append(ziel)
    return ergebnisse

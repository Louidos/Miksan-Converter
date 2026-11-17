"""Hilfen der Bild-Werkzeuge: Bild laden, je Einzelbild bearbeiten, sicher speichern."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PIL import Image

from ..convert import Ergebnis, farbe_parsen, laden, quellformat_erkennen, speichern, ziel_pruefen
from ..formats import Format, format_aus_name


def ziel_format(eingabe: Path, ausgabe: Path | None, to: str | None) -> Format:
    if to:
        return format_aus_name(to)
    if ausgabe is not None and ausgabe.suffix:
        return format_aus_name(ausgabe.suffix)
    fmt = quellformat_erkennen(eingabe)
    return fmt if fmt is not None and fmt.schreiben else format_aus_name("png")


def standard_ziel(eingabe: Path, zusatz: str, fmt: Format) -> Path:
    return eingabe.with_name(f"{eingabe.stem}-{zusatz}{fmt.endung}")


def je_bild(
    eingabe: str | Path,
    ausgabe: str | Path | None,
    zusatz: str,
    funktion: Callable[[Image.Image], Image.Image],
    *,
    to: str | None = None,
    overwrite: bool = False,
    hintergrund: str = "#ffffff",
) -> Ergebnis:
    """Lädt ein Bild (alle Einzelbilder), wendet ``funktion`` an und speichert es neu."""
    eingabe = Path(eingabe)
    ausgabe = Path(ausgabe) if ausgabe is not None else None
    fmt = ziel_format(eingabe, ausgabe, to)
    ziel = ausgabe or standard_ziel(eingabe, zusatz, fmt)
    ziel_pruefen(eingabe, ziel, overwrite)
    bild = laden(eingabe, ziel=fmt)
    bild.frames = [funktion(frame) for frame in bild.frames]
    hinweise = speichern(
        bild, ziel, fmt, overwrite=overwrite, hintergrund=farbe_parsen(hintergrund)
    )
    return Ergebnis(eingabe, ziel, bild.quelle, fmt, hinweise)

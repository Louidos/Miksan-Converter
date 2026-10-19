"""Bilder laden, umwandeln und speichern."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from .fehler import BedienFehler, MiksanFehler
from .formats import Format, format_aus_endung, format_aus_name, format_aus_pil


@dataclass
class Ergebnis:
    eingabe: Path
    ausgabe: Path
    eingabe_format: str
    ausgabe_format: Format


def ziel_bestimmen(eingabe: Path, ausgabe: Path | None, to: str | None) -> tuple[Path, Format]:
    """Ermittelt Zieldatei und Zielformat aus Ausgabepfad und/oder ``--to``."""
    ziel_format = format_aus_name(to) if to else None
    if ausgabe is None:
        if ziel_format is None:
            raise BedienFehler("Bitte eine Ausgabedatei oder ein Zielformat mit --to angeben.")
        return eingabe.with_suffix(ziel_format.endung), ziel_format

    endungs_format = format_aus_endung(ausgabe)
    if ziel_format is None:
        if endungs_format is None:
            raise BedienFehler(
                f"Zielformat von '{ausgabe}' ist unbekannt. Bitte eine bekannte Endung "
                "verwenden oder das Format mit --to angeben."
            )
        ziel_format = endungs_format
    elif endungs_format is not None and endungs_format != ziel_format:
        raise BedienFehler(
            f"Die Endung von '{ausgabe}' passt nicht zu --to {to}. "
            "Bitte nur eines angeben oder beides passend wählen."
        )
    return ausgabe, ziel_format


def bild_oeffnen(pfad: Path) -> Image.Image:
    """Öffnet ein Bild und erkennt das Format am Inhalt, nicht an der Endung."""
    if not pfad.exists():
        raise MiksanFehler(f"Datei nicht gefunden: {pfad}")
    if pfad.is_dir():
        raise MiksanFehler(f"'{pfad}' ist ein Ordner, keine Bilddatei.")
    try:
        bild = Image.open(pfad)
        bild.load()
    except UnidentifiedImageError as fehler:
        raise MiksanFehler(f"'{pfad}' ist kein unterstütztes Bild.") from fehler
    except OSError as fehler:
        raise MiksanFehler(f"'{pfad}' ist beschädigt oder unvollständig.") from fehler
    return bild


def _fuer_ziel_vorbereiten(bild: Image.Image, ziel: Format) -> Image.Image:
    hat_alpha = bild.mode in ("RGBA", "LA", "PA") or "transparency" in bild.info
    if hat_alpha and not ziel.alpha:
        rgba = bild.convert("RGBA")
        flach = Image.new("RGB", rgba.size, (255, 255, 255))
        flach.paste(rgba, mask=rgba.getchannel("A"))
        return flach
    if ziel.name == "jpeg" and bild.mode not in ("L", "RGB", "CMYK"):
        return bild.convert("RGB")
    return bild


def umwandeln(
    eingabe: Path,
    ausgabe: Path | None = None,
    *,
    to: str | None = None,
    overwrite: bool = False,
) -> Ergebnis:
    """Wandelt ``eingabe`` in das Zielformat um und schreibt eine neue Datei."""
    eingabe = Path(eingabe)
    ziel_pfad, ziel_format = ziel_bestimmen(eingabe, Path(ausgabe) if ausgabe else None, to)

    if ziel_pfad.exists() and ziel_pfad.resolve() == eingabe.resolve():
        raise BedienFehler(
            f"Ausgabe und Eingabe sind dieselbe Datei ({ziel_pfad}). "
            "Originaldateien werden nie verändert."
        )
    if ziel_pfad.exists() and not overwrite:
        raise MiksanFehler(
            f"'{ziel_pfad}' gibt es schon und bleibt unverändert. "
            "Mit --overwrite wird die Datei ersetzt."
        )

    bild = bild_oeffnen(eingabe)
    quelle = format_aus_pil(bild.format)
    quell_name = quelle.name if quelle else (bild.format or "unbekannt")
    vorbereitet = _fuer_ziel_vorbereiten(bild, ziel_format)

    try:
        vorbereitet.save(ziel_pfad, format=ziel_format.pil_name)
    except (OSError, ValueError) as fehler:
        raise MiksanFehler(f"'{ziel_pfad}' konnte nicht geschrieben werden: {fehler}") from fehler
    return Ergebnis(eingabe, ziel_pfad, quell_name, ziel_format)

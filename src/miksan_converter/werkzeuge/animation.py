"""Animationen: GIF/WebP aus mehreren Bildern erstellen und in Einzelbilder zerlegen."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageOps

from ..convert import _datei_schreiben, laden
from ..fehler import BedienFehler, MiksanFehler
from ..formats import format_aus_name

ZIELE = ("gif", "webp")
STANDARD_DAUER = 500  # Millisekunden pro Bild


def erstellen(
    bilder: Sequence[str | Path],
    ausgabe: str | Path,
    *,
    dauer: int | Sequence[int] = STANDARD_DAUER,
    schleife: int = 0,
    overwrite: bool = False,
) -> Path:
    """Erstellt eine Animation; das Format kommt aus der Endung (``.gif`` oder ``.webp``).

    Alle Bilder werden auf die Grösse des ersten eingepasst (zentriert, Rest transparent).
    ``schleife`` = 0 wiederholt endlos, sonst so oft wie angegeben.
    """
    ausgabe = Path(ausgabe)
    fmt = ausgabe.suffix.lower().lstrip(".")
    if fmt not in ZIELE:
        raise BedienFehler("Animationen gehen als .gif oder .webp.")
    if len(bilder) < 2:
        raise BedienFehler("Für eine Animation braucht es mindestens zwei Bilder.")
    dauern = [dauer] * len(bilder) if isinstance(dauer, int) else list(dauer)
    if len(dauern) != len(bilder) or any(d < 10 for d in dauern):
        raise BedienFehler("Die Dauer pro Bild muss mindestens 10 ms sein.")
    if schleife < 0:
        raise BedienFehler("Die Anzahl Wiederholungen darf nicht negativ sein.")
    frames = []
    groesse = None
    for pfad in bilder:
        bild = laden(Path(pfad)).frames[0].convert("RGBA")
        if groesse is None:
            groesse = bild.size
        elif bild.size != groesse:
            eingepasst = ImageOps.contain(bild, groesse, Image.Resampling.LANCZOS)
            leinwand = Image.new("RGBA", groesse, (0, 0, 0, 0))
            leinwand.paste(
                eingepasst,
                ((groesse[0] - eingepasst.width) // 2, (groesse[1] - eingepasst.height) // 2),
            )
            bild = leinwand
        frames.append(bild)
    optionen = {"save_all": True, "append_images": frames[1:], "duration": dauern, "loop": schleife}
    if fmt == "gif":
        optionen["disposal"] = 2
        optionen["optimize"] = True
    else:
        optionen.update(lossless=False, quality=90, method=4)
    ausgabe.parent.mkdir(parents=True, exist_ok=True)
    _datei_schreiben(
        ausgabe, lambda datei: frames[0].save(datei, format=fmt.upper(), **optionen), overwrite
    )
    return ausgabe


def zerlegen(
    eingabe: str | Path,
    ausgabe_ordner: str | Path | None = None,
    *,
    bildformat: str = "png",
    overwrite: bool = False,
) -> list[Path]:
    """Speichert jedes Einzelbild einer Animation (GIF, WebP, APNG …) als eigene Datei."""
    eingabe = Path(eingabe)
    ziel_format = format_aus_name(bildformat)
    bild = laden(eingabe, ziel=format_aus_name("gif"))
    if len(bild.frames) < 2:
        raise MiksanFehler(f"'{eingabe}' ist keine Animation (nur ein Bild).")
    ordner = Path(ausgabe_ordner) if ausgabe_ordner else eingabe.parent / f"{eingabe.stem}-bilder"
    ordner.mkdir(parents=True, exist_ok=True)
    stellen = max(3, len(str(len(bild.frames))))
    ergebnisse = []
    for nummer, frame in enumerate(bild.frames, start=1):
        ziel = ordner / f"{eingabe.stem}-bild-{nummer:0{stellen}d}{ziel_format.endung}"
        speicherbar = frame.convert("RGBA" if ziel_format.alpha else "RGB")
        _datei_schreiben(
            ziel,
            lambda datei, f=speicherbar: f.save(datei, format=ziel_format.pil_name),
            overwrite,
        )
        ergebnisse.append(ziel)
    return ergebnisse

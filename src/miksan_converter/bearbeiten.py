"""Bilder bearbeiten: zuschneiden, drehen, spiegeln, Grösse ändern.

Die Schritte laufen immer in derselben Reihenfolge:
Ausrichtung (beim Laden) -> Zuschnitt -> Drehen -> Spiegeln -> Grösse -> Speichern.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from PIL import Image

from .fehler import BedienFehler

REIHENFOLGE = ("Ausrichtung", "Zuschnitt", "Drehen", "Spiegeln", "Grösse", "Speichern")

_DREHEN = {
    90: Image.Transpose.ROTATE_270,  # Pillow dreht gegen den Uhrzeigersinn
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_90,
}
_SPIEGELN = {"h": Image.Transpose.FLIP_LEFT_RIGHT, "v": Image.Transpose.FLIP_TOP_BOTTOM}

_EINHEITEN = {
    "": 1,
    "b": 1,
    "k": 1000,
    "kb": 1000,
    "kib": 1024,
    "m": 1000**2,
    "mb": 1000**2,
    "mib": 1024**2,
}


@dataclass
class Bearbeitung:
    breite: int | None = None
    hoehe: int | None = None
    max_seite: int | None = None
    zuschneiden: tuple[int, int, int, int] | None = None
    drehen: int | None = None
    spiegeln: str | None = None
    qualitaet: int | None = None
    zielgroesse: int | None = None
    metadaten_entfernen: bool = False

    def __post_init__(self) -> None:
        for name in ("breite", "hoehe", "max_seite"):
            wert = getattr(self, name)
            if wert is not None and wert < 1:
                raise BedienFehler(f"--{name.replace('_seite', '')} muss mindestens 1 sein.")
        if self.qualitaet is not None and not 1 <= self.qualitaet <= 100:
            raise BedienFehler("--qualitaet muss zwischen 1 und 100 liegen.")
        if self.drehen is not None and self.drehen not in _DREHEN:
            raise BedienFehler("--drehen erlaubt nur 90, 180 oder 270.")
        if self.spiegeln is not None and self.spiegeln not in _SPIEGELN:
            raise BedienFehler("--spiegeln erlaubt nur h (waagrecht) oder v (senkrecht).")
        if self.zielgroesse is not None and self.zielgroesse < 1:
            raise BedienFehler("--zielgroesse muss grösser als 0 sein.")
        if self.qualitaet is not None and self.zielgroesse is not None:
            raise BedienFehler("Bitte nur --qualitaet oder --zielgroesse angeben, nicht beides.")

    def veraendert_pixel(self) -> bool:
        return any(
            wert is not None
            for wert in (
                self.breite,
                self.hoehe,
                self.max_seite,
                self.zuschneiden,
                self.drehen,
                self.spiegeln,
            )
        )


def zuschnitt_parsen(text: str) -> tuple[int, int, int, int]:
    """Liest ``x,y,b,h`` (linke obere Ecke, Breite, Höhe in Pixeln)."""
    teile = [t.strip() for t in text.split(",")]
    try:
        x, y, b, h = (int(t) for t in teile)
    except ValueError:
        raise BedienFehler(
            f"--zuschneiden '{text}' ist ungültig. Erwartet: x,y,b,h, z. B. 10,20,800,600."
        ) from None
    if x < 0 or y < 0 or b < 1 or h < 1:
        raise BedienFehler("--zuschneiden: x und y ab 0, Breite und Höhe ab 1.")
    return x, y, b, h


def groesse_parsen(text: str) -> int:
    """Liest eine Dateigrösse wie ``500KB``, ``1.5MB`` oder ``300000`` (KB = 1000 Byte)."""
    treffer = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z]*)\s*", text)
    einheit = treffer.group(2).lower() if treffer else ""
    if not treffer or einheit not in _EINHEITEN:
        raise BedienFehler(f"--zielgroesse '{text}' ist ungültig. Beispiele: 500KB, 1.5MB, 200000.")
    zahl = float(treffer.group(1).replace(",", "."))
    return int(zahl * _EINHEITEN[einheit])


def _fuer_bearbeitung(frame: Image.Image) -> Image.Image:
    """Palettenbilder vor dem Skalieren in Vollfarbe umwandeln (sonst grobe Kanten)."""
    if frame.mode == "P":
        transparent = "transparency" in frame.info or frame.palette.mode == "RGBA"
        return frame.convert("RGBA" if transparent else "RGB")
    if frame.mode == "1":
        return frame.convert("L")
    return frame


def neue_groesse(groesse: tuple[int, int], bearbeitung: Bearbeitung) -> tuple[int, int] | None:
    breite, hoehe = groesse
    neu_b, neu_h = breite, hoehe
    if bearbeitung.breite and bearbeitung.hoehe:
        neu_b, neu_h = bearbeitung.breite, bearbeitung.hoehe
    elif bearbeitung.breite:
        neu_b = bearbeitung.breite
        neu_h = max(1, round(hoehe * bearbeitung.breite / breite))
    elif bearbeitung.hoehe:
        neu_h = bearbeitung.hoehe
        neu_b = max(1, round(breite * bearbeitung.hoehe / hoehe))
    if bearbeitung.max_seite and max(neu_b, neu_h) > bearbeitung.max_seite:
        faktor = bearbeitung.max_seite / max(neu_b, neu_h)
        neu_b = max(1, round(neu_b * faktor))
        neu_h = max(1, round(neu_h * faktor))
    if (neu_b, neu_h) == (breite, hoehe):
        return None
    return neu_b, neu_h


def frame_bearbeiten(frame: Image.Image, bearbeitung: Bearbeitung) -> Image.Image:
    """Wendet Zuschnitt, Drehen, Spiegeln und Grösse auf ein Einzelbild an."""
    if bearbeitung.zuschneiden:
        x, y, b, h = bearbeitung.zuschneiden
        if x + b > frame.width or y + h > frame.height:
            raise BedienFehler(
                f"--zuschneiden {x},{y},{b},{h} liegt ausserhalb des Bildes "
                f"({frame.width}x{frame.height} Pixel)."
            )
        frame = frame.crop((x, y, x + b, y + h))
    if bearbeitung.drehen:
        frame = frame.transpose(_DREHEN[bearbeitung.drehen])
    if bearbeitung.spiegeln:
        frame = frame.transpose(_SPIEGELN[bearbeitung.spiegeln])
    groesse = neue_groesse(frame.size, bearbeitung)
    if groesse is not None:
        frame = _fuer_bearbeitung(frame).resize(groesse, Image.Resampling.LANCZOS)
    return frame


def frames_bearbeiten(frames: list[Image.Image], bearbeitung: Bearbeitung) -> list[Image.Image]:
    if not bearbeitung.veraendert_pixel():
        return frames
    return [frame_bearbeiten(frame, bearbeitung) for frame in frames]


def verkleinern(frames: list[Image.Image], faktor: float) -> list[Image.Image]:
    ergebnis = []
    for frame in frames:
        groesse = (max(1, round(frame.width * faktor)), max(1, round(frame.height * faktor)))
        ergebnis.append(_fuer_bearbeitung(frame).resize(groesse, Image.Resampling.LANCZOS))
    return ergebnis

"""Zuschneiden mit festem Seitenverhältnis und Zielmassen (Profilbilder, Social Media).

Der Bereich kann in Pixeln (``x, y, b, h``) oder relativ (Anteile 0–1, z. B. aus der Maus-
Auswahl in der Oberfläche) angegeben werden; ohne Bereich wird mittig zugeschnitten.
"""

from __future__ import annotations

import re
from pathlib import Path

from ..bearbeiten import Bearbeitung
from ..convert import Ergebnis, laden, umwandeln
from ..fehler import BedienFehler
from ._gemeinsam import standard_ziel, ziel_format

VERHAELTNISSE = {
    "frei": None,
    "1:1": (1, 1),
    "4:3": (4, 3),
    "3:4": (3, 4),
    "16:9": (16, 9),
    "9:16": (9, 16),
    "3:2": (3, 2),
}

# Vorlagen für feste Zielmasse
VORLAGEN = {
    "profilbild": ("Profilbild 400 × 400", (400, 400)),
    "instagram": ("Instagram quadratisch 1080 × 1080", (1080, 1080)),
    "instagram-hoch": ("Instagram hoch 1080 × 1350", (1080, 1350)),
    "story": ("Story 1080 × 1920", (1080, 1920)),
    "youtube": ("YouTube-Vorschaubild 1280 × 720", (1280, 720)),
    "link": ("Link-Vorschau (Facebook, LinkedIn) 1200 × 630", (1200, 630)),
    "x-kopf": ("X/Twitter-Titelbild 1500 × 500", (1500, 500)),
}


def verhaeltnis_parsen(text: str | None) -> tuple[int, int] | None:
    if text is None or text in ("", "frei"):
        return None
    if text in VERHAELTNISSE:
        return VERHAELTNISSE[text]
    treffer = re.fullmatch(r"\s*(\d+)\s*[:x×]\s*(\d+)\s*", text)
    if not treffer or "0" in (treffer.group(1), treffer.group(2)):
        raise BedienFehler(f"Seitenverhältnis '{text}' ist ungültig, z. B. 1:1 oder 16:9.")
    return int(treffer.group(1)), int(treffer.group(2))


def masse_parsen(text: str) -> tuple[int, int]:
    treffer = re.fullmatch(r"\s*(\d+)\s*[x×]\s*(\d+)\s*", text)
    if not treffer or int(treffer.group(1)) < 1 or int(treffer.group(2)) < 1:
        raise BedienFehler(f"Zielmasse '{text}' sind ungültig, z. B. 400x400.")
    return int(treffer.group(1)), int(treffer.group(2))


def bereich_mittig(
    groesse: tuple[int, int], verhaeltnis: tuple[int, int] | None
) -> tuple[int, int, int, int]:
    """Grösster mittiger Ausschnitt mit dem Verhältnis (ohne Verhältnis: ganzes Bild)."""
    breite, hoehe = groesse
    if verhaeltnis is None:
        return 0, 0, breite, hoehe
    vb, vh = verhaeltnis
    if breite * vh > hoehe * vb:  # zu breit
        neu_b = max(1, round(hoehe * vb / vh))
        return (breite - neu_b) // 2, 0, neu_b, hoehe
    neu_h = max(1, round(breite * vh / vb))
    return 0, (hoehe - neu_h) // 2, breite, neu_h


def relativ_zu_pixel(
    relativ: tuple[float, float, float, float], groesse: tuple[int, int]
) -> tuple[int, int, int, int]:
    """Anteile (x, y, b, h zwischen 0 und 1) in Pixel umrechnen, ans Bild angepasst."""
    breite, hoehe = groesse
    x = min(max(0, round(relativ[0] * breite)), breite - 1)
    y = min(max(0, round(relativ[1] * hoehe)), hoehe - 1)
    b = max(1, min(round(relativ[2] * breite), breite - x))
    h = max(1, min(round(relativ[3] * hoehe), hoehe - y))
    return x, y, b, h


def zuschneiden(
    eingabe: str | Path,
    ausgabe: str | Path | None = None,
    *,
    bereich: tuple[int, int, int, int] | None = None,
    relativ: tuple[float, float, float, float] | None = None,
    verhaeltnis: tuple[int, int] | None = None,
    ziel: tuple[int, int] | None = None,
    to: str | None = None,
    overwrite: bool = False,
) -> Ergebnis:
    """Schneidet zu und rechnet optional auf feste Zielmasse; ohne Ausgabe
    ``<name>-zugeschnitten``. Mit Zielmassen gilt deren Verhältnis."""
    eingabe = Path(eingabe)
    if ziel is not None:
        verhaeltnis = ziel
    groesse = laden(eingabe).frames[0].size
    if bereich is None:
        bereich = (
            relativ_zu_pixel(relativ, groesse)
            if relativ is not None
            else bereich_mittig(groesse, verhaeltnis)
        )
    bearbeitung = Bearbeitung(
        zuschneiden=bereich,
        breite=ziel[0] if ziel else None,
        hoehe=ziel[1] if ziel else None,
    )
    ausgabe = Path(ausgabe) if ausgabe else None
    fmt = ziel_format(eingabe, ausgabe, to)
    pfad = ausgabe or standard_ziel(eingabe, "zugeschnitten", fmt)
    return umwandeln(eingabe, pfad, to=fmt.name, overwrite=overwrite, bearbeitung=bearbeitung)

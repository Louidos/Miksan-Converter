"""Stapel-Umbenennen mit Platzhaltern. Konflikte werden vor dem Start gemeldet; es wird nie
etwas überschrieben.

Platzhalter: ``{name}`` (alter Name ohne Endung), ``{nr}`` (laufende Nummer, mit führenden
Nullen), ``{datum}`` (Aufnahmedatum aus EXIF, sonst Änderungsdatum, JJJJ-MM-TT), ``{breite}``,
``{hoehe}`` (Pixel). Die Endung bleibt erhalten.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
import string
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from ..fehler import BedienFehler, MiksanFehler

PLATZHALTER = ("name", "nr", "datum", "breite", "hoehe")
_VERBOTEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


@dataclass(frozen=True)
class Umbenennung:
    alt: Path
    neu: Path

    @property
    def unveraendert(self) -> bool:
        return self.alt == self.neu


def _angaben(pfad: Path) -> tuple[str, int | None, int | None]:
    """(Datum, Breite, Höhe) – Datum aus EXIF-Aufnahmedatum, sonst Änderungsdatum."""
    datum = dt.datetime.fromtimestamp(pfad.stat().st_mtime).strftime("%Y-%m-%d")
    breite = hoehe = None
    try:
        with Image.open(pfad) as bild:
            breite, hoehe = bild.size
            exif = bild.getexif()
            if exif.get(0x0112, 1) in (5, 6, 7, 8):
                breite, hoehe = hoehe, breite
            aufnahme = exif.get_ifd(0x8769).get(0x9003) or exif.get(0x0132)
            if aufnahme:
                datum = dt.datetime.strptime(str(aufnahme)[:10], "%Y:%m:%d").strftime("%Y-%m-%d")
    except Exception:  # kein Bild oder ohne EXIF: Dateidatum
        pass
    return datum, breite, hoehe


def muster_pruefen(muster: str) -> None:
    if not muster.strip():
        raise BedienFehler("Das Muster ist leer, z. B. „urlaub-{nr}“.")
    try:
        felder = [feld for _, feld, _, _ in string.Formatter().parse(muster) if feld is not None]
    except ValueError as fehler:
        raise BedienFehler(f"Das Muster '{muster}' ist ungültig: {fehler}") from fehler
    unbekannt = [feld for feld in felder if feld not in PLATZHALTER]
    if unbekannt:
        raise BedienFehler(
            f"Unbekannter Platzhalter {{{unbekannt[0]}}}. Möglich: "
            + ", ".join(f"{{{p}}}" for p in PLATZHALTER)
        )


def neue_namen(
    pfade: Sequence[str | Path],
    muster: str,
    *,
    start: int = 1,
    ziel_ordner: str | Path | None = None,
) -> list[Umbenennung]:
    """Berechnet alle neuen Namen (ohne etwas zu ändern)."""
    muster_pruefen(muster)
    pfade = [Path(p) for p in pfade]
    stellen = max(2, len(str(start + len(pfade) - 1)))
    ergebnis = []
    for index, pfad in enumerate(pfade):
        if not pfad.is_file():
            raise MiksanFehler(f"Datei nicht gefunden: {pfad}")
        datum, breite, hoehe = _angaben(pfad) if "{" in muster else ("", None, None)
        stamm = muster.format(
            name=pfad.stem,
            nr=str(start + index).zfill(stellen),
            datum=datum,
            breite=breite if breite is not None else "",
            hoehe=hoehe if hoehe is not None else "",
        ).strip()
        if not stamm or stamm in (".", "..") or _VERBOTEN.search(stamm):
            raise BedienFehler(f"Der neue Name '{stamm}' ist kein gültiger Dateiname.")
        ordner = Path(ziel_ordner) if ziel_ordner else pfad.parent
        ergebnis.append(Umbenennung(pfad, ordner / f"{stamm}{pfad.suffix}"))
    return ergebnis


def konflikte(umbenennungen: Sequence[Umbenennung]) -> list[str]:
    """Alle Gründe, warum nicht umbenannt werden darf (leer = alles in Ordnung)."""
    gruende = []
    gesehen: dict[str, Path] = {}
    quellen = {str(u.alt).lower() for u in umbenennungen}
    for u in umbenennungen:
        schluessel = str(u.neu).lower()  # Windows/macOS unterscheiden Gross/klein nicht
        if schluessel in gesehen:
            gruende.append(
                f"'{u.neu.name}' entstünde doppelt ({gesehen[schluessel].name}, {u.alt.name})."
            )
        gesehen[schluessel] = u.alt
        gleiche_datei = str(u.alt).lower() == schluessel
        if u.neu.exists() and not gleiche_datei:
            andere = "wird ebenfalls umbenannt" if schluessel in quellen else "gibt es schon"
            gruende.append(f"'{u.neu}' {andere} – es wird nichts überschrieben.")
    return gruende


def umbenennen(
    pfade: Sequence[str | Path],
    muster: str,
    *,
    start: int = 1,
    ziel_ordner: str | Path | None = None,
) -> list[Umbenennung]:
    """Benennt um (bzw. kopiert mit neuem Namen nach ``ziel_ordner``).

    Bei einem Konflikt wird vorher abgebrochen und keine Datei angefasst.
    """
    umbenennungen = neue_namen(pfade, muster, start=start, ziel_ordner=ziel_ordner)
    gruende = konflikte(umbenennungen)
    if gruende:
        raise BedienFehler("Nicht umbenannt, keine Datei wurde verändert:\n" + "\n".join(gruende))
    if ziel_ordner is not None:
        Path(ziel_ordner).mkdir(parents=True, exist_ok=True)
    for u in umbenennungen:
        if u.unveraendert:
            continue
        if ziel_ordner is not None:
            shutil.copy2(u.alt, u.neu)
        elif str(u.alt).lower() == str(u.neu).lower():  # nur Gross/klein: über einen Zwischennamen
            zwischen = u.alt.with_name(f".{uuid.uuid4().hex}{u.alt.suffix}")
            u.alt.rename(zwischen)
            zwischen.rename(u.neu)
        else:
            u.alt.rename(u.neu)
    return umbenennungen

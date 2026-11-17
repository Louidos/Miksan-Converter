"""Vorschau berechnen (ohne Qt): Ergebnis mit den aktuellen Einstellungen, nur im Speicher.

Gerechnet wird auf einer verkleinerten Kopie (längste Seite höchstens ``KANTE`` Pixel) mit
denselben Funktionen wie beim echten Lauf (``bearbeiten.frame_bearbeiten``,
``convert.kodieren``). Die Dateigrösse wird aus der echten Kodierung der Vorschau auf die
volle Grösse hochgerechnet und ist deshalb nur ungefähr („ca.“). Es wird nie eine Datei
geschrieben.
"""

from __future__ import annotations

import dataclasses
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from ..bearbeiten import Bearbeitung, _fuer_bearbeitung, frame_bearbeiten, neue_groesse
from ..convert import (
    _fuer_zielgroesse_kodieren,
    farbe_parsen,
    kodieren,
    laden,
    quellformat_erkennen,
)
from ..fehler import MiksanFehler
from ..formats import Format, format_aus_name
from . import logik
from .dateiinfo import groesse_text

KANTE = 1600


@dataclass
class Vorschau:
    vorher: Image.Image  # Original (gleich zugeschnitten/gedreht wie das Ergebnis), RGBA
    nachher: Image.Image  # Ergebnis nach dem Kodieren, wieder gelesen, RGBA
    masse_vorher: tuple[int, int]
    masse_nachher: tuple[int, int]
    groesse_vorher: int | None  # Byte der Originaldatei
    groesse_nachher: int | None  # geschätzte Byte der Zieldatei
    format: str = ""
    hinweis: str = ""

    def text(self) -> str:
        """Z. B. "4000 × 3000 → 1600 × 1200 · ca. 310 KB (vorher 4.2 MB)"."""
        (bv, hv), (bn, hn) = self.masse_vorher, self.masse_nachher
        teile = [f"{bv} × {hv} → {bn} × {hn}" if (bv, hv) != (bn, hn) else f"{bv} × {hv}"]
        if self.groesse_nachher is not None:
            text = f"{self.format.upper()} ca. {groesse_text(self.groesse_nachher)}"
            if self.groesse_vorher is not None:
                text += f" (vorher {groesse_text(self.groesse_vorher)})"
            teile.append(text)
        return " · ".join(teile)


def masse_nach(groesse: tuple[int, int], bearbeitung: Bearbeitung) -> tuple[int, int]:
    """Masse nach Zuschnitt, Drehen und Grösse – ohne ein Bild zu rechnen."""
    breite, hoehe = groesse
    if bearbeitung.zuschneiden:
        breite, hoehe = bearbeitung.zuschneiden[2:]
    if bearbeitung.drehen in (90, 270):
        breite, hoehe = hoehe, breite
    return neue_groesse((breite, hoehe), bearbeitung) or (breite, hoehe)


def _skaliert(bearbeitung: Bearbeitung, faktor: float) -> Bearbeitung:
    """Dieselbe Bearbeitung für die verkleinerte Kopie (Pixelangaben mal ``faktor``)."""

    def mal(wert: int | None) -> int | None:
        return None if wert is None else max(1, round(wert * faktor))

    zuschnitt = None
    if bearbeitung.zuschneiden:
        zuschnitt = tuple(max(0, round(z * faktor)) for z in bearbeitung.zuschneiden)
        zuschnitt = (*zuschnitt[:2], max(1, zuschnitt[2]), max(1, zuschnitt[3]))
    return dataclasses.replace(
        bearbeitung,
        breite=mal(bearbeitung.breite),
        hoehe=mal(bearbeitung.hoehe),
        max_seite=mal(bearbeitung.max_seite),
        zuschneiden=zuschnitt,
        zielgroesse=None,
    )


def _nur_geometrie(bearbeitung: Bearbeitung) -> Bearbeitung:
    return Bearbeitung(
        zuschneiden=bearbeitung.zuschneiden,
        drehen=bearbeitung.drehen,
        spiegeln=bearbeitung.spiegeln,
    )


def ziel_format_fuer(pfad: Path, einstellungen: logik.Einstellungen) -> Format:
    if einstellungen.ziel_format:
        return format_aus_name(einstellungen.ziel_format)
    if einstellungen.aktion == logik.HINTERGRUND:
        return format_aus_name("png")
    fmt = quellformat_erkennen(pfad)
    return fmt if fmt is not None and fmt.schreiben else format_aus_name("png")


def _lesen(daten: bytes, ersatz: Image.Image) -> Image.Image:
    try:
        with Image.open(io.BytesIO(daten)) as bild:
            bild.load()
            return bild.convert("RGBA")
    except Exception:  # z. B. PDF kann Pillow nur schreiben
        return ersatz.convert("RGBA")


def vorschau_berechnen(
    pfad: str | Path, einstellungen: logik.Einstellungen, *, kante: int = KANTE
) -> Vorschau:
    """Rechnet die Vorschau für eine Datei; wirft ``MiksanFehler`` mit verständlicher Meldung."""
    pfad = Path(pfad)
    bearbeitung = logik.bearbeitung_aus(einstellungen)
    hintergrund = farbe_parsen(einstellungen.hintergrundfarbe)
    ziel = ziel_format_fuer(pfad, einstellungen)
    quelle = laden(pfad)
    frame = quelle.frames[0]
    masse_vorher = frame.size
    masse_nachher = masse_nach(masse_vorher, bearbeitung)

    faktor = min(1.0, kante / max(masse_vorher))
    klein = frame
    if faktor < 1.0:
        groesse = (max(1, round(frame.width * faktor)), max(1, round(frame.height * faktor)))
        klein = _fuer_bearbeitung(frame).resize(groesse, Image.Resampling.LANCZOS)
    vorher = frame_bearbeiten(klein, _skaliert(_nur_geometrie(bearbeitung), faktor))
    ergebnis = frame_bearbeiten(klein, _skaliert(bearbeitung, faktor))

    bild = dataclasses.replace(quelle, frames=[ergebnis], dauern=[0], ico_bilder=[])
    pixel_voll = masse_nachher[0] * masse_nachher[1]
    pixel_klein = max(1, ergebnis.width * ergebnis.height)
    verhaeltnis = pixel_voll / pixel_klein
    hinweis = ""
    try:
        if bearbeitung.zielgroesse:
            ziel_klein = max(1, int(bearbeitung.zielgroesse / max(verhaeltnis, 1.0)))
            daten, _ = _fuer_zielgroesse_kodieren(
                bild, ziel, ziel_klein, hintergrund=hintergrund, metadaten=False
            )
            geschaetzt = min(bearbeitung.zielgroesse, round(len(daten) * verhaeltnis))
        else:
            daten = kodieren(
                bild,
                ziel,
                hintergrund=hintergrund,
                qualitaet=bearbeitung.qualitaet,
                metadaten=not bearbeitung.metadaten_entfernen,
            )
            geschaetzt = round(len(daten) * verhaeltnis)
    except MiksanFehler as fehler:
        daten, geschaetzt, hinweis = b"", None, str(fehler)

    try:
        groesse_vorher = pfad.stat().st_size
    except OSError:
        groesse_vorher = None
    return Vorschau(
        vorher=vorher.convert("RGBA"),
        nachher=_lesen(daten, ergebnis) if daten else ergebnis.convert("RGBA"),
        masse_vorher=masse_vorher,
        masse_nachher=masse_nachher,
        groesse_vorher=groesse_vorher,
        groesse_nachher=geschaetzt,
        format=ziel.name,
        hinweis=hinweis,
    )


# --- Hintergrund entfernen: Maske einmal rechnen, Hintergrund sofort wechseln -------------


class MaskenSpeicher:
    """Merkt sich Masken (je Datei, Modell, Änderungszeit) und Modell-Sitzungen.

    So muss beim Wechsel des Hintergrunds, der Farbe oder der Kante nicht neu gerechnet
    werden – nur beim Wechsel der Datei oder des Modells.
    """

    def __init__(self, grenze: int = 8) -> None:
        self.grenze = grenze
        self.masken: dict[tuple, Image.Image] = {}
        self.sitzungen: dict[str, object] = {}
        self.ersatz: dict[tuple, Image.Image] = {}
        self.berechnet = 0  # wie oft das Modell gerechnet hat (für Tests)

    def sitzung(self, modell: str):
        from ..hintergrund import sitzung_erstellen

        if modell not in self.sitzungen:
            self.sitzungen[modell] = sitzung_erstellen(modell)
        return self.sitzungen[modell]

    def maske(self, pfad: Path, modell: str, bild: Image.Image) -> Image.Image:
        from ..hintergrund import maske_berechnen

        schluessel = (str(pfad), pfad.stat().st_mtime_ns, modell, bild.size)
        if schluessel not in self.masken:
            if len(self.masken) >= self.grenze:
                self.masken.pop(next(iter(self.masken)))
            self.masken[schluessel] = maske_berechnen(bild, self.sitzung(modell))
            self.berechnet += 1
        return self.masken[schluessel]

    def ersatz_bild(self, pfad: str) -> Image.Image:
        from ..hintergrund import ersatz_laden

        datei = Path(pfad)
        schluessel = (str(datei), datei.stat().st_mtime_ns)
        if schluessel not in self.ersatz:
            self.ersatz = {schluessel: ersatz_laden(datei)}
        return self.ersatz[schluessel]


def vorschau_hintergrund(
    pfad: str | Path,
    einstellungen: logik.Einstellungen,
    speicher: MaskenSpeicher,
    *,
    kante: int = KANTE,
) -> Vorschau:
    """Vorschau „Hintergrund entfernen“: freigestellt bzw. auf dem neuen Hintergrund."""
    from ..hintergrund import (
        BILD,
        kante_weicher,
        modell_vorhanden,
        zusammensetzen,
    )

    pfad = Path(pfad)
    if not modell_vorhanden(einstellungen.modell):
        raise MiksanFehler(
            f"Das Modell '{einstellungen.modell}' ist noch nicht geladen – "
            "bitte zuerst „Herunterladen“ drücken."
        )
    ziel = ziel_format_fuer(pfad, einstellungen)
    quelle = laden(pfad)
    frame = quelle.frames[0]
    faktor = min(1.0, kante / max(frame.size))
    klein = frame
    if faktor < 1.0:
        groesse = (max(1, round(frame.width * faktor)), max(1, round(frame.height * faktor)))
        klein = _fuer_bearbeitung(frame).resize(groesse, Image.Resampling.LANCZOS)
    maske = speicher.maske(pfad, einstellungen.modell, klein)
    ersatz = None
    if einstellungen.neuer_hintergrund == BILD and einstellungen.ersatz_bild.strip():
        ersatz = speicher.ersatz_bild(einstellungen.ersatz_bild)
    ergebnis = zusammensetzen(
        klein,
        kante_weicher(maske, einstellungen.kante * faktor),
        neuer_hintergrund=einstellungen.neuer_hintergrund,
        farbe=farbe_parsen(einstellungen.ersatz_farbe),
        ersatz=ersatz,
        unschaerfe=max(1, round(einstellungen.unschaerfe * faktor)),
    )
    bild = dataclasses.replace(quelle, frames=[ergebnis], dauern=[0], ico_bilder=[])
    daten = kodieren(bild, ziel, hintergrund=farbe_parsen(einstellungen.hintergrundfarbe))
    verhaeltnis = (frame.width * frame.height) / max(1, ergebnis.width * ergebnis.height)
    try:
        groesse_vorher = pfad.stat().st_size
    except OSError:
        groesse_vorher = None
    return Vorschau(
        vorher=klein.convert("RGBA"),
        nachher=_lesen(daten, ergebnis),
        masse_vorher=frame.size,
        masse_nachher=frame.size,
        groesse_vorher=groesse_vorher,
        groesse_nachher=round(len(daten) * verhaeltnis),
        format=ziel.name,
    )


# --- Weitere Bild-Werkzeuge: beliebige Bildfunktion in der Vorschau -----------------------


def vorschau_mit_funktion(
    pfad: str | Path, funktion, *, ziel: str | None = None, kante: int = KANTE
) -> Vorschau:
    """Wendet ``funktion`` (Bild -> Bild) auf eine verkleinerte Kopie an (z. B. Wasserzeichen).

    Die Funktion muss mit relativen Grössen arbeiten, damit das Ergebnis maßstabsgetreu ist.
    """
    pfad = Path(pfad)
    quelle = laden(pfad)
    frame = quelle.frames[0]
    faktor = min(1.0, kante / max(frame.size))
    klein = frame
    if faktor < 1.0:
        groesse = (max(1, round(frame.width * faktor)), max(1, round(frame.height * faktor)))
        klein = _fuer_bearbeitung(frame).resize(groesse, Image.Resampling.LANCZOS)
    ergebnis = funktion(klein)
    original = logik.Einstellungen(aktion=logik.BEARBEITEN, ziel_format="")
    fmt = format_aus_name(ziel) if ziel else ziel_format_fuer(pfad, original)
    bild = dataclasses.replace(quelle, frames=[ergebnis], dauern=[0], ico_bilder=[])
    daten = kodieren(bild, fmt)
    verhaeltnis = (frame.width * frame.height) / max(1, klein.width * klein.height)
    nachher = (round(ergebnis.width / faktor), round(ergebnis.height / faktor))
    return Vorschau(
        vorher=klein.convert("RGBA"),
        nachher=_lesen(daten, ergebnis),
        masse_vorher=frame.size,
        masse_nachher=nachher,
        groesse_vorher=pfad.stat().st_size,
        groesse_nachher=round(len(daten) * verhaeltnis),
        format=fmt.name,
    )

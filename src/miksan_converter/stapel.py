"""Mehrere Dateien, Ordner und Muster auf einmal verarbeiten (parallel)."""

from __future__ import annotations

import glob
import os
import sys
import threading
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from .fehler import MiksanFehler
from .formats import Format, bekannte_bild_endungen

_MUSTER_ZEICHEN = set("*?[")


def ist_muster(text: str) -> bool:
    return any(zeichen in text for zeichen in _MUSTER_ZEICHEN)


@dataclass
class Datei:
    """Eine gefundene Eingabedatei und der Ordner, relativ zu dem die Struktur erhalten bleibt."""

    pfad: Path
    basis: Path

    @property
    def relativ(self) -> Path:
        try:
            return self.pfad.relative_to(self.basis)
        except ValueError:
            return Path(self.pfad.name)


@dataclass
class Auftrag:
    eingabe: Path
    ausgabe: Path


@dataclass
class StapelErgebnis:
    ok: list[Auftrag] = field(default_factory=list)
    fehler: list[tuple[Path, str]] = field(default_factory=list)
    hinweise: list[tuple[Path, str]] = field(default_factory=list)
    uebersprungen: list[Auftrag] = field(default_factory=list)

    @property
    def rueckgabecode(self) -> int:
        return 1 if self.fehler else 0


def _ordner_durchsuchen(ordner: Path, rekursiv: bool) -> list[Path]:
    endungen = bekannte_bild_endungen()
    kandidaten = ordner.rglob("*") if rekursiv else ordner.iterdir()
    dateien = []
    for pfad in kandidaten:
        relativ = pfad.relative_to(ordner)
        if any(teil.startswith(".") for teil in relativ.parts):
            continue  # versteckte Dateien und Ordner überspringen
        if pfad.is_file() and pfad.suffix.lower() in endungen:
            dateien.append(pfad)
    return sorted(dateien)


def _muster_basis(muster: str) -> Path:
    teile = Path(muster).parts
    basis = []
    for teil in teile:
        if ist_muster(teil):
            break
        basis.append(teil)
    return Path(*basis) if basis else Path(".")


def dateien_sammeln(
    eingaben: Iterable[str | Path], *, rekursiv: bool = False
) -> tuple[list[Datei], list[tuple[Path, str]]]:
    """Löst Ordner, Dateien und Muster (z. B. ``*.heic``) in einzelne Dateien auf.

    In Ordnern werden nur Dateien mit bekannter Bild-Endung genommen, ausdrücklich genannte
    Dateien immer (das Format wird am Inhalt erkannt).
    """
    dateien: list[Datei] = []
    fehler: list[tuple[Path, str]] = []
    gesehen: set[Path] = set()

    def hinzufuegen(pfad: Path, basis: Path) -> None:
        schluessel = pfad.resolve()
        if schluessel not in gesehen:
            gesehen.add(schluessel)
            dateien.append(Datei(pfad, basis))

    for eingabe in eingaben:
        text = str(eingabe)
        pfad = Path(text)
        if pfad.is_dir():
            for datei in _ordner_durchsuchen(pfad, rekursiv):
                hinzufuegen(datei, pfad)
        elif pfad.is_file():
            hinzufuegen(pfad, pfad.parent)
        elif ist_muster(text):
            treffer = sorted(glob.glob(text, recursive=rekursiv))
            treffer = [Path(t) for t in treffer if Path(t).is_file()]
            if not treffer:
                fehler.append((pfad, "keine Datei passt zu diesem Muster"))
            basis = _muster_basis(text)
            for datei in treffer:
                hinzufuegen(datei, basis)
        else:
            fehler.append((pfad, "Datei oder Ordner nicht gefunden"))
    return dateien, fehler


def auftraege_planen(
    dateien: list[Datei],
    ziel_fuer: Callable[[Datei], Path],
    ausgabe_ordner: Path | None,
) -> tuple[list[Auftrag], list[tuple[Path, str]]]:
    """Bestimmt für jede Datei die Zieldatei; doppelte Ziele werden als Fehler gemeldet."""
    auftraege: list[Auftrag] = []
    fehler: list[tuple[Path, str]] = []
    ziele: dict[Path, Path] = {}
    ausgabe_absolut = ausgabe_ordner.resolve() if ausgabe_ordner else None
    for datei in dateien:
        if ausgabe_absolut and ausgabe_absolut in datei.pfad.resolve().parents:
            continue  # Ergebnisse früherer Läufe im Ausgabeordner nicht erneut verarbeiten
        try:
            ziel = ziel_fuer(datei)
        except MiksanFehler as fehler_:
            fehler.append((datei.pfad, str(fehler_)))
            continue
        schluessel = ziel.resolve()
        if schluessel in ziele:
            fehler.append(
                (datei.pfad, f"Zieldatei '{ziel}' entsteht schon aus '{ziele[schluessel]}'")
            )
            continue
        ziele[schluessel] = datei.pfad
        auftraege.append(Auftrag(datei.pfad, ziel))
    return auftraege, fehler


def ziel_umwandeln(datei: Datei, ziel: Format, ausgabe_ordner: Path | None) -> Path:
    """Zieldatei beim Umwandeln: im Ausgabeordner (Struktur bleibt) oder neben dem Original."""
    if ausgabe_ordner is not None:
        return ausgabe_ordner / datei.relativ.with_suffix(ziel.endung)
    return datei.pfad.with_suffix(ziel.endung)


def ziel_bearbeiten(datei: Datei, ziel: Format, ausgabe_ordner: Path | None) -> Path:
    """Zieldatei beim Bearbeiten: ohne Ausgabeordner ``<name>-bearbeitet`` neben dem Original."""
    if ausgabe_ordner is not None:
        return ausgabe_ordner / datei.relativ.with_suffix(ziel.endung)
    return datei.pfad.with_name(f"{datei.pfad.stem}-bearbeitet{ziel.endung}")


def ausfuehren(
    auftraege: list[Auftrag],
    arbeit: Callable[[Auftrag], list[str]],
    *,
    jobs: int | None = None,
    fortschritt: TextIO | None = None,
    rueckmeldung: Callable[[int, int, Auftrag], None] | None = None,
    abbrechen: threading.Event | None = None,
) -> StapelErgebnis:
    """Führt ``arbeit`` für alle Aufträge parallel aus. Ein Fehler bricht den Lauf nicht ab.

    ``rueckmeldung(fertig, gesamt, auftrag)`` wird nach jedem Auftrag im aufrufenden Thread
    aufgerufen. Ist ``abbrechen`` gesetzt, werden noch nicht gestartete Aufträge übersprungen
    (``StapelErgebnis.uebersprungen``); laufende werden zu Ende geführt.
    """
    ergebnis = StapelErgebnis()
    if not auftraege:
        return ergebnis
    jobs = max(1, min(jobs or os.cpu_count() or 1, len(auftraege)))
    anzeigen = fortschritt is not None and fortschritt.isatty()
    gesamt = len(auftraege)

    def starten(auftrag: Auftrag) -> list[str] | None:
        if abbrechen is not None and abbrechen.is_set():
            return None  # None = übersprungen
        return arbeit(auftrag) or []

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        laufend = {pool.submit(starten, auftrag): auftrag for auftrag in auftraege}
        for fertig, zukunft in enumerate(as_completed(laufend), start=1):
            auftrag = laufend[zukunft]
            try:
                hinweise = zukunft.result()
            except MiksanFehler as fehler:
                ergebnis.fehler.append((auftrag.eingabe, str(fehler)))
            except Exception as fehler:  # unerwartet: trotzdem weitermachen
                ergebnis.fehler.append((auftrag.eingabe, f"unerwarteter Fehler: {fehler}"))
            else:
                if hinweise is None:
                    ergebnis.uebersprungen.append(auftrag)
                else:
                    ergebnis.ok.append(auftrag)
                    ergebnis.hinweise += [(auftrag.eingabe, h) for h in hinweise]
            if rueckmeldung is not None:
                rueckmeldung(fertig, gesamt, auftrag)
            if anzeigen:
                name = auftrag.eingabe.name
                if len(name) > 40:
                    name = name[:37] + "..."
                fortschritt.write(f"\r[{fertig}/{gesamt}] {name:<40}")
                fortschritt.flush()
    if anzeigen:
        fortschritt.write("\r" + " " * 60 + "\r")
        fortschritt.flush()
    return ergebnis


def zusammenfassung_ausgeben(
    ergebnis: StapelErgebnis,
    *,
    ausgabe: TextIO | None = None,
    fehlerausgabe: TextIO | None = None,
) -> None:
    ausgabe = ausgabe or sys.stdout
    fehlerausgabe = fehlerausgabe or sys.stderr
    for pfad, hinweis in ergebnis.hinweise:
        print(f"Hinweis ({pfad}): {hinweis}", file=fehlerausgabe)
    if ergebnis.fehler:
        print("Fehler:", file=fehlerausgabe)
        for pfad, meldung in ergebnis.fehler:
            zeile = meldung if str(pfad) in meldung else f"{pfad}: {meldung}"
            print(f"  {zeile}", file=fehlerausgabe)
    print(f"{len(ergebnis.ok)} ok, {len(ergebnis.fehler)} Fehler", file=ausgabe)

"""Alles für die Oberfläche, was ohne Fenster auskommt (kein Qt-Import, normal testbar).

Die Oberfläche plant und verarbeitet Aufträge mit denselben Funktionen wie die Kommandozeile:
``stapel.dateien_sammeln``, ``stapel.auftraege_planen``, ``stapel.ausfuehren`` sowie
``convert.umwandeln``, ``convert.bearbeiten`` und ``hintergrund.hintergrund_entfernen``.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from ..bearbeiten import Bearbeitung, groesse_parsen
from ..convert import bearbeiten, farbe_parsen, quellformat_erkennen, umwandeln
from ..fehler import BedienFehler
from ..formats import (
    Format,
    alle_formate,
    extra_installiert,
    format_aus_name,
    pil_kann_schreiben,
)
from ..hintergrund import (
    MODELLE,
    STANDARD_MODELL,
    hintergrund_entfernen,
    modell_name,
    modell_ordner,
    sitzung_erstellen,
    standard_ausgabe,
)
from ..stapel import (
    Auftrag,
    Datei,
    StapelErgebnis,
    auftraege_planen,
    ausfuehren,
    dateien_sammeln,
    ziel_bearbeiten,
    ziel_umwandeln,
)

UMWANDELN = "umwandeln"
BEARBEITEN = "bearbeiten"
HINTERGRUND = "hintergrund"
AKTIONEN = {
    UMWANDELN: "Umwandeln",
    BEARBEITEN: "Bearbeiten",
    HINTERGRUND: "Hintergrund entfernen",
}

# Auswahl "Zielformat" beim Bearbeiten: Format der Quelle behalten
WIE_ORIGINAL = ""

DREHEN = {"keine": None, "90° rechts": 90, "180°": 180, "90° links": 270}
SPIEGELN = {"keine": None, "waagrecht": "h", "senkrecht": "v"}


@dataclass
class Einstellungen:
    """Alles, was im Fenster eingestellt werden kann."""

    aktion: str = UMWANDELN
    ziel_format: str = "jpeg"
    ausgabe_ordner: Path | None = None
    rekursiv: bool = False
    ueberschreiben: bool = False
    max_seite: int | None = None
    qualitaet: int | None = None
    zielgroesse: str = ""
    drehen: int | None = None
    spiegeln: str | None = None
    metadaten_entfernen: bool = False
    hintergrundfarbe: str = "#ffffff"
    modell: str = STANDARD_MODELL


@dataclass(frozen=True)
class FormatEintrag:
    """Ein Eintrag der Auswahlliste "Zielformat"."""

    name: str
    text: str
    verfuegbar: bool = True
    hinweis: str = ""


@dataclass(frozen=True)
class AktionEintrag:
    name: str
    text: str
    verfuegbar: bool = True
    hinweis: str = ""


@dataclass
class Plan:
    auftraege: list[Auftrag] = field(default_factory=list)
    fehler: list[tuple[Path, str]] = field(default_factory=list)


def _extra_hinweis(extra: str, wofuer: str) -> str:
    return f'{wofuer} braucht das Extra [{extra}]: pip install "miksan-converter[{extra}]"'


def formate_fuer_auswahl(*, wie_original: bool = False) -> list[FormatEintrag]:
    """Alle schreibbaren Formate; nicht nutzbare sind mit Hinweis als nicht verfügbar markiert."""
    eintraege = []
    if wie_original:
        eintraege.append(FormatEintrag(WIE_ORIGINAL, "wie Original"))
    for fmt in alle_formate():
        if not fmt.schreiben:
            continue
        text = f"{fmt.name.upper()} – {fmt.beschreibung}"
        if fmt.extra and not extra_installiert(fmt.extra):
            hinweis = _extra_hinweis(fmt.extra, f"Das Format {fmt.name.upper()}")
            eintraege.append(FormatEintrag(fmt.name, text, False, hinweis))
        elif not pil_kann_schreiben(fmt):
            hinweis = f"Diese Pillow-Version kann {fmt.name.upper()} nicht schreiben."
            eintraege.append(FormatEintrag(fmt.name, text, False, hinweis))
        else:
            hinweis = fmt.einschraenkung.replace("--background", "Hintergrundfarbe")
            eintraege.append(FormatEintrag(fmt.name, text, True, hinweis))
    return eintraege


def aktionen_fuer_auswahl() -> list[AktionEintrag]:
    """Die drei Aktionen; "Hintergrund entfernen" ist ohne Extra [ki] nicht verfügbar."""
    eintraege = []
    for name, text in AKTIONEN.items():
        if name == HINTERGRUND and not extra_installiert("ki"):
            hinweis = _extra_hinweis("ki", "Hintergrund entfernen")
            eintraege.append(AktionEintrag(name, text, False, hinweis))
        else:
            eintraege.append(AktionEintrag(name, text))
    return eintraege


def modelle_fuer_auswahl() -> list[str]:
    return list(MODELLE)


def modell_vorhanden(modell: str) -> bool:
    """Liegt das Modell schon lokal? Sonst wird es beim ersten Gebrauch heruntergeladen."""
    return (modell_ordner() / f"{modell_name(modell)}.onnx").is_file()


def bearbeitung_aus(einstellungen: Einstellungen) -> Bearbeitung:
    """Macht aus den Feldern im Fenster eine ``Bearbeitung`` (dieselben Regeln wie die CLI)."""
    zielgroesse = einstellungen.zielgroesse.strip()
    return Bearbeitung(
        max_seite=einstellungen.max_seite or None,
        drehen=einstellungen.drehen,
        spiegeln=einstellungen.spiegeln,
        qualitaet=einstellungen.qualitaet or None,
        zielgroesse=groesse_parsen(zielgroesse) if zielgroesse else None,
        metadaten_entfernen=einstellungen.metadaten_entfernen,
    )


def einstellungen_pruefen(einstellungen: Einstellungen) -> None:
    """Prüft die Einstellungen vor dem Start; wirft ``BedienFehler`` mit verständlicher Meldung."""
    farbe_parsen(einstellungen.hintergrundfarbe)
    bearbeitung = bearbeitung_aus(einstellungen)
    if einstellungen.aktion not in AKTIONEN:
        raise BedienFehler(f"Unbekannte Aktion '{einstellungen.aktion}'.")
    if einstellungen.aktion == UMWANDELN and not einstellungen.ziel_format:
        raise BedienFehler("Bitte ein Zielformat wählen.")
    if einstellungen.aktion == BEARBEITEN and not (
        bearbeitung.veraendert_pixel()
        or bearbeitung.qualitaet
        or bearbeitung.zielgroesse
        or bearbeitung.metadaten_entfernen
    ):
        raise BedienFehler(
            "Keine Bearbeitung gewählt, z. B. maximale Grösse, Drehen oder Zielgrösse."
        )
    if einstellungen.ziel_format:
        format_aus_name(einstellungen.ziel_format)


def _ziel_format(einstellungen: Einstellungen) -> Format | None:
    if einstellungen.ziel_format:
        return format_aus_name(einstellungen.ziel_format)
    if einstellungen.aktion == HINTERGRUND:
        return format_aus_name("png")
    return None


def ziel_fuer(einstellungen: Einstellungen) -> Callable[[Datei], Path]:
    """Bestimmt die Zieldatei wie die Kommandozeile (``-o`` = Ausgabeordner)."""
    fest = _ziel_format(einstellungen)
    ordner = einstellungen.ausgabe_ordner

    def ziel(datei: Datei) -> Path:
        if einstellungen.aktion == UMWANDELN:
            return ziel_umwandeln(datei, fest, ordner)
        if einstellungen.aktion == BEARBEITEN:
            fmt = fest or quellformat_erkennen(datei.pfad)
            if fmt is None or not fmt.schreiben:
                fmt = format_aus_name("png")
            return ziel_bearbeiten(datei, fmt, ordner)
        if ordner is not None:
            return ziel_umwandeln(datei, fest, ordner)
        return standard_ausgabe(datei.pfad, fest, False)

    return ziel


def planen(pfade: Iterable[str | Path], einstellungen: Einstellungen) -> Plan:
    """Sammelt Dateien (auch aus Ordnern) und bestimmt für jede die Zieldatei."""
    einstellungen_pruefen(einstellungen)
    ordner = einstellungen.ausgabe_ordner
    if ordner is not None and ordner.exists() and not ordner.is_dir():
        raise BedienFehler(f"Der Ausgabeordner '{ordner}' ist eine Datei.")
    dateien, fehler = dateien_sammeln(pfade, rekursiv=einstellungen.rekursiv)
    auftraege, planfehler = auftraege_planen(dateien, ziel_fuer(einstellungen), ordner)
    return Plan(auftraege, fehler + planfehler)


def arbeit_fuer(einstellungen: Einstellungen) -> tuple[Callable[[Auftrag], list[str]], Callable]:
    """Liefert die Arbeit pro Auftrag und eine Vorbereitung (z. B. KI-Modell laden)."""
    bearbeitung = bearbeitung_aus(einstellungen)
    optionen = {
        "overwrite": einstellungen.ueberschreiben,
        "hintergrund": einstellungen.hintergrundfarbe,
    }
    to = einstellungen.ziel_format or None
    sitzung = []

    def vorbereiten() -> None:
        if einstellungen.aktion == HINTERGRUND:
            sitzung.append(sitzung_erstellen(einstellungen.modell))

    def arbeit(auftrag: Auftrag) -> list[str]:
        auftrag.ausgabe.parent.mkdir(parents=True, exist_ok=True)
        if einstellungen.aktion == UMWANDELN:
            funktion = umwandeln
        elif einstellungen.aktion == BEARBEITEN:
            funktion = bearbeiten
        else:
            return hintergrund_entfernen(
                auftrag.eingabe,
                auftrag.ausgabe,
                to=to,
                modell=einstellungen.modell,
                sitzung=sitzung[0],
                **optionen,
            ).hinweise
        return funktion(
            auftrag.eingabe, auftrag.ausgabe, to=to, bearbeitung=bearbeitung, **optionen
        ).hinweise

    return arbeit, vorbereiten


def plan_ausfuehren(
    plan: Plan,
    einstellungen: Einstellungen,
    *,
    rueckmeldung: Callable[[int, int, Auftrag], None] | None = None,
    abbrechen: threading.Event | None = None,
    jobs: int | None = None,
) -> StapelErgebnis:
    """Verarbeitet alle Aufträge des Plans; Planungsfehler stehen vorne in der Fehlerliste."""
    arbeit, vorbereiten = arbeit_fuer(einstellungen)
    if plan.auftraege:
        if einstellungen.ausgabe_ordner is not None:
            einstellungen.ausgabe_ordner.mkdir(parents=True, exist_ok=True)
        vorbereiten()
    ergebnis = ausfuehren(
        plan.auftraege, arbeit, jobs=jobs, rueckmeldung=rueckmeldung, abbrechen=abbrechen
    )
    ergebnis.fehler = plan.fehler + ergebnis.fehler
    return ergebnis


def zusammenfassung(ergebnis: StapelErgebnis) -> str:
    """Kurzer Satz für die Statuszeile, z. B. "3 ok, 1 Fehler, 2 Hinweise"."""
    teile = [f"{len(ergebnis.ok)} ok", f"{len(ergebnis.fehler)} Fehler"]
    if ergebnis.hinweise:
        teile.append(f"{len(ergebnis.hinweise)} Hinweise")
    if ergebnis.uebersprungen:
        teile.append(f"{len(ergebnis.uebersprungen)} abgebrochen")
    return ", ".join(teile)


def meldungen(ergebnis: StapelErgebnis) -> list[str]:
    """Fehler und Hinweise pro Datei als Zeilen für die Liste unter der Zusammenfassung."""
    zeilen = []
    for pfad, meldung in ergebnis.fehler:
        text = meldung if str(pfad) in meldung else f"{pfad}: {meldung}"
        zeilen.append(f"Fehler – {text}")
    for pfad, hinweis in ergebnis.hinweise:
        zeilen.append(f"Hinweis – {pfad}: {hinweis}")
    return zeilen


def ausgabe_ordner_von(ergebnis: StapelErgebnis, einstellungen: Einstellungen) -> Path | None:
    """Ordner, den "Ausgabeordner öffnen" zeigt: der gewählte oder der der ersten Ausgabe."""
    if einstellungen.ausgabe_ordner is not None:
        return einstellungen.ausgabe_ordner
    if ergebnis.ok:
        return ergebnis.ok[0].ausgabe.parent
    return None

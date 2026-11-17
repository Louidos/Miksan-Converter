"""Zentrale Werkzeug-Registrierung (ohne Qt): Seitenleiste und Startseite werden daraus gebaut.

Ein neues Werkzeug braucht nur einen Eintrag in ``WERKZEUGE`` (und seine Seite in
``gui/seiten/``); ein neuer Bereich einen Eintrag in ``BEREICHE``.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ..formats import bekannte_bild_endungen, extra_installiert

# Dateiarten, nach denen Werkzeuge ausgewählt werden
BILD = "bild"
PDF = "pdf"
VIDEO = "video"
AUDIO = "audio"
ORDNER = "ordner"

PDF_ENDUNGEN = frozenset({".pdf"})
VIDEO_ENDUNGEN = frozenset(
    {
        ".mp4",
        ".m4v",
        ".mov",
        ".mkv",
        ".webm",
        ".avi",
        ".wmv",
        ".flv",
        ".mpg",
        ".mpeg",
        ".3gp",
        ".ts",
    }
)
AUDIO_ENDUNGEN = frozenset(
    {".mp3", ".wav", ".flac", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wma", ".aiff", ".aif"}
)

# Reihenfolge der Bereiche in Seitenleiste und Startseite
BEREICHE = ["Bilder", "PDF", "Video & Audio"]


@dataclass(frozen=True)
class Werkzeug:
    name: str  # interner Schlüssel, auch für QSettings
    titel: str
    icon: str  # Name in gui/icons/
    bereich: str
    beschreibung: str  # ein Satz für die Karte auf der Startseite
    seite: str  # "modul:Klasse" in gui/seiten/, wird erst beim Öffnen geladen
    arten: frozenset[str] = frozenset({BILD, ORDNER})
    extra: str | None = None  # benötigtes Extra, z. B. "ki"
    extra_zweck: str = ""

    def verfuegbar(self) -> bool:
        return self.extra is None or extra_installiert(self.extra)

    def hinweis(self) -> str:
        """Warum das Werkzeug nicht verfügbar ist (leer, wenn es verfügbar ist)."""
        if self.verfuegbar():
            return ""
        zweck = self.extra_zweck or self.titel
        befehl = f'pip install "miksan-converter[{self.extra}]"'
        return f"{zweck} braucht das Extra [{self.extra}]: {befehl}"

    def passt(self, pfad: str | Path) -> bool:
        return datei_art(pfad) in self.arten


WERKZEUGE: list[Werkzeug] = [
    Werkzeug(
        "umwandeln",
        "Umwandeln",
        "umwandeln",
        "Bilder",
        "Bilder in ein anderes Format umwandeln, z. B. HEIC → JPEG oder PNG → WebP.",
        "umwandeln:UmwandelnSeite",
    ),
    Werkzeug(
        "bearbeiten",
        "Verkleinern & Bearbeiten",
        "verkleinern",
        "Bilder",
        "Grösse ändern, komprimieren, drehen, spiegeln und Metadaten entfernen.",
        "bearbeiten:BearbeitenSeite",
    ),
    Werkzeug(
        "hintergrund",
        "Hintergrund entfernen",
        "hintergrund",
        "Bilder",
        "Den Hintergrund mit einem lokalen KI-Modell freistellen.",
        "hintergrund:HintergrundSeite",
        extra="ki",
        extra_zweck="Hintergrund entfernen",
    ),
]

# Feste Seiten ausserhalb der Werkzeuge
START = "start"
EINSTELLUNGEN = "einstellungen"
INFO = "info"


def werkzeug(name: str) -> Werkzeug:
    for eintrag in WERKZEUGE:
        if eintrag.name == name:
            return eintrag
    raise KeyError(name)


def nach_bereich() -> list[tuple[str, list[Werkzeug]]]:
    """Werkzeuge gruppiert nach Bereich, in der Reihenfolge von ``BEREICHE``."""
    gruppen = []
    for bereich in BEREICHE:
        eintraege = [w for w in WERKZEUGE if w.bereich == bereich]
        if eintraege:
            gruppen.append((bereich, eintraege))
    return gruppen


def datei_art(pfad: str | Path) -> str | None:
    """Ordnet eine Datei (nur nach Endung) einer Art zu; Ordner sind ``ORDNER``."""
    pfad = Path(pfad)
    if pfad.is_dir():
        return ORDNER
    endung = pfad.suffix.lower()
    if endung in PDF_ENDUNGEN:
        return PDF
    if endung in VIDEO_ENDUNGEN:
        return VIDEO
    if endung in AUDIO_ENDUNGEN:
        return AUDIO
    if endung in bekannte_bild_endungen():
        return BILD
    return None


def passende_werkzeuge(pfade: Iterable[str | Path]) -> list[tuple[Werkzeug, int]]:
    """Werkzeuge, die mit mindestens einer der Dateien etwas anfangen können (mit Anzahl)."""
    pfade = list(pfade)
    ergebnis = []
    for eintrag in WERKZEUGE:
        anzahl = sum(1 for pfad in pfade if eintrag.passt(pfad))
        if anzahl:
            ergebnis.append((eintrag, anzahl))
    return ergebnis

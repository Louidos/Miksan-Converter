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
        if self.extra == "medien":  # ffmpeg kann auch ohne Extra im PATH liegen
            from ..medien import ffmpeg_vorhanden

            return ffmpeg_vorhanden()
        return self.extra is None or extra_installiert(self.extra)

    def hinweis(self) -> str:
        """Warum das Werkzeug nicht verfügbar ist (leer, wenn es verfügbar ist)."""
        if self.verfuegbar():
            return ""
        if self.extra == "medien":
            return (
                'Video & Audio braucht ffmpeg: pip install "miksan-converter[medien]" '
                "oder ffmpeg installieren (bzw. in den Einstellungen den Pfad angeben)."
            )
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
    Werkzeug(
        "zuschneiden",
        "Zuschneiden",
        "zuschneiden",
        "Bilder",
        "Ausschnitt mit der Maus wählen, feste Verhältnisse und Masse für Profilbilder.",
        "zuschneiden:ZuschneidenSeite",
    ),
    Werkzeug(
        "wasserzeichen",
        "Wasserzeichen",
        "wasserzeichen",
        "Bilder",
        "Text oder Logo auf Bilder legen – Position, Deckkraft und Grösse wählbar.",
        "wasserzeichen:WasserzeichenSeite",
    ),
    Werkzeug(
        "umbenennen",
        "Stapel-Umbenennen",
        "umbenennen",
        "Bilder",
        "Viele Dateien nach einem Muster umbenennen, z. B. urlaub-{datum}-{nr}.",
        "umbenennen:UmbenennenSeite",
    ),
    Werkzeug(
        "animation",
        "Animation",
        "animation",
        "Bilder",
        "GIF oder WebP aus Bildern erstellen – oder Animationen in Einzelbilder zerlegen.",
        "animation:AnimationSeite",
    ),
    Werkzeug(
        "iconset",
        "Icon-Set",
        "iconset",
        "Bilder",
        "favicon.ico und App-Icons in allen üblichen Grössen aus einem Bild.",
        "iconset:IconsetSeite",
    ),
    *(
        Werkzeug(
            name,
            titel,
            icon,
            "PDF",
            text,
            f"pdf:{klasse}",
            arten=arten,
            extra="pdf",
            extra_zweck="Die PDF-Werkzeuge",
        )
        for name, titel, icon, text, klasse, arten in (
            (
                "pdf_zusammenfuegen",
                "PDF zusammenfügen",
                "zusammenfuegen",
                "Mehrere PDFs in der gewünschten Reihenfolge zu einem verbinden.",
                "ZusammenfuegenSeite",
                frozenset({PDF}),
            ),
            (
                "pdf_teilen",
                "PDF teilen",
                "teilen",
                "Jede Seite einzeln oder Bereiche wie 1-3,5 als eigene PDFs speichern.",
                "TeilenSeite",
                frozenset({PDF}),
            ),
            (
                "pdf_seiten",
                "Seiten drehen & löschen",
                "drehen",
                "Einzelne oder alle Seiten drehen und Seiten entfernen.",
                "SeitenSeite",
                frozenset({PDF}),
            ),
            (
                "pdf_bilder",
                "PDF → Bilder",
                "bild",
                "Seiten als PNG oder JPEG speichern, Auflösung wählbar.",
                "BilderSeite",
                frozenset({PDF}),
            ),
            (
                "bilder_pdf",
                "Bilder → PDF",
                "pdf",
                "Bilder zu einem PDF zusammenstellen, A4 oder in Bildgrösse.",
                "AusBildernSeite",
                frozenset({BILD, ORDNER}),
            ),
            (
                "pdf_verkleinern",
                "PDF verkleinern",
                "verkleinern",
                "Eingebettete Bilder neu komprimieren, damit das PDF kleiner wird.",
                "VerkleinernSeite",
                frozenset({PDF}),
            ),
        )
    ),
    *(
        Werkzeug(
            name,
            titel,
            icon,
            "Video & Audio",
            text,
            f"medien:{klasse}",
            arten=frozenset({art}),
            extra="medien",
        )
        for name, titel, icon, text, klasse, art in (
            (
                "video_umwandeln",
                "Video umwandeln",
                "video",
                "In MP4, WebM, MKV, MOV oder GIF – mit Qualität, Auflösung und Bildrate.",
                "VideoUmwandelnSeite",
                VIDEO,
            ),
            (
                "video_kuerzen",
                "Video kürzen",
                "zuschneiden",
                "Anfang und Ende abschneiden, wenn möglich ohne Neukodierung.",
                "KuerzenSeite",
                VIDEO,
            ),
            (
                "video_verkleinern",
                "Video verkleinern",
                "verkleinern",
                "Auf eine Zielgrösse bringen, z. B. unter 10 MB für Discord oder Mail.",
                "VerkleinernSeite",
                VIDEO,
            ),
            (
                "video_gif",
                "Video → GIF",
                "animation",
                "Einen Ausschnitt als GIF mit schöner Farbpalette speichern.",
                "GifSeite",
                VIDEO,
            ),
            (
                "video_ton",
                "Ton herausziehen",
                "audio",
                "Den Ton eines Videos als MP3, M4A, FLAC … speichern.",
                "TonSeite",
                VIDEO,
            ),
            (
                "video_bild",
                "Einzelbild speichern",
                "bild",
                "Ein Bild aus dem Video zu einem Zeitpunkt als PNG oder JPEG speichern.",
                "EinzelbildSeite",
                VIDEO,
            ),
            (
                "audio_umwandeln",
                "Audio umwandeln",
                "audio",
                "MP3, WAV, FLAC, OGG, Opus, M4A – kürzen, Lautstärke angleichen.",
                "AudioSeite",
                AUDIO,
            ),
        )
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

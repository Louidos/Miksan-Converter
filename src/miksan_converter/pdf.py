"""PDF-Werkzeuge (Extra [pdf]): zusammenfügen, teilen, Seiten drehen/löschen, PDF ↔ Bilder,
verkleinern.

Zusammenfügen und Seiten bearbeiten macht pypdf (BSD-3-Clause), das Rendern zu Bildern
pypdfium2 (Apache-2.0/BSD-3-Clause). Alles läuft lokal; das Original wird nie verändert.
"""

from __future__ import annotations

import io
import re
import threading
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from PIL import Image

from .convert import _datei_schreiben, auf_hintergrund, laden
from .fehler import BedienFehler, ExtraFehlt, MiksanFehler

STANDARD_DPI = 150
A4_MM = (210, 297)
SEITENGROESSEN = ("a4", "bild")
STANDARD_QUALITAET = 70  # beim Verkleinern

# pdfium ist nicht threadsicher: alle Aufrufe nacheinander
_PDFIUM_SPERRE = threading.Lock()


class PasswortNoetig(MiksanFehler):
    """Das PDF ist verschlüsselt und braucht ein Passwort."""

    def __init__(self, pfad: Path, falsch: bool = False):
        self.pfad = pfad
        self.falsch = falsch
        text = "Das Passwort ist falsch" if falsch else "Das PDF ist mit einem Passwort geschützt"
        super().__init__(f"'{pfad}': {text}. Bitte mit --passwort angeben.")


def _pypdf():
    try:
        import pypdf
    except ImportError as fehler:
        raise ExtraFehlt("pdf", "Die PDF-Werkzeuge") from fehler
    return pypdf


def _pdfium():
    try:
        import pypdfium2
    except ImportError as fehler:
        raise ExtraFehlt("pdf", "Die PDF-Werkzeuge") from fehler
    return pypdfium2


# --- Lesen -------------------------------------------------------------------------------


def lesen(pfad: str | Path, passwort: str | None = None):
    """Öffnet ein PDF mit pypdf; verschlüsselte brauchen ``passwort``."""
    pypdf = _pypdf()
    pfad = Path(pfad)
    if not pfad.is_file():
        raise MiksanFehler(f"Datei nicht gefunden: {pfad}")
    try:
        leser = pypdf.PdfReader(pfad)
        if leser.is_encrypted:
            if not passwort:
                raise PasswortNoetig(pfad)
            if not leser.decrypt(passwort):
                raise PasswortNoetig(pfad, falsch=True)
        len(leser.pages)  # beschädigte Seitenbäume fallen hier auf
    except MiksanFehler:
        raise
    except Exception as fehler:  # pypdf hat viele Fehlerklassen (PdfReadError, ValueError …)
        raise MiksanFehler(f"'{pfad}' ist kein gültiges oder ein beschädigtes PDF.") from fehler
    return leser


def ist_verschluesselt(pfad: str | Path) -> bool:
    try:
        return bool(_pypdf().PdfReader(Path(pfad)).is_encrypted)
    except ExtraFehlt:
        raise
    except Exception:
        return False


def seiten_anzahl(pfad: str | Path, passwort: str | None = None) -> int:
    return len(lesen(pfad, passwort).pages)


def seiten_parsen(text: str | None, anzahl: int) -> list[list[int]]:
    """Liest Seitenbereiche wie ``1-3,5,8-`` (ab 1); jede Gruppe wird ein Teil.

    Leer/``None`` = jede Seite einzeln. Gibt 0-basierte Seitennummern zurück.
    """
    if text is None or not text.strip():
        return [[i] for i in range(anzahl)]
    gruppen = []
    for teil in text.replace(";", ",").split(","):
        teil = teil.strip()
        if not teil:
            continue
        treffer = re.fullmatch(r"(\d*)\s*-\s*(\d*)|(\d+)", teil)
        if not treffer:
            raise BedienFehler(f"Seitenangabe '{teil}' ist ungültig. Beispiel: 1-3,5")
        if treffer.group(3):
            von = bis = int(treffer.group(3))
        else:
            von = int(treffer.group(1) or 1)
            bis = int(treffer.group(2) or anzahl)
        if not 1 <= von <= bis <= anzahl:
            raise BedienFehler(f"Seiten '{teil}' gibt es nicht (das PDF hat {anzahl} Seiten).")
        gruppen.append(list(range(von - 1, bis)))
    if not gruppen:
        raise BedienFehler("Keine Seiten angegeben.")
    return gruppen


def seiten_menge(text: str | None, anzahl: int) -> list[int]:
    """Alle Seiten aus einer Angabe (leer = alle), sortiert und ohne Doppelte, 0-basiert."""
    if text is None or not text.strip():
        return list(range(anzahl))
    return sorted({seite for gruppe in seiten_parsen(text, anzahl) for seite in gruppe})


def _schreiben(writer, ziel: Path, overwrite: bool) -> Path:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    try:
        _datei_schreiben(ziel, writer.write, overwrite)
    except MiksanFehler:
        raise
    except Exception as fehler:
        raise MiksanFehler(f"'{ziel}' konnte nicht geschrieben werden: {fehler}") from fehler
    return ziel


# --- Zusammenfügen, teilen, Seiten ---------------------------------------------------------


def zusammenfuegen(
    eingaben: Sequence[str | Path],
    ausgabe: str | Path,
    *,
    passwoerter: dict[str, str] | None = None,
    overwrite: bool = False,
) -> Path:
    """Hängt alle PDFs in der angegebenen Reihenfolge zu einem zusammen."""
    if len(eingaben) < 2:
        raise BedienFehler("Zum Zusammenfügen braucht es mindestens zwei PDFs.")
    passwoerter = passwoerter or {}
    writer = _pypdf().PdfWriter()
    for eingabe in eingaben:
        leser = lesen(eingabe, passwoerter.get(str(Path(eingabe))))
        for seite in leser.pages:
            writer.add_page(seite)
    return _schreiben(writer, Path(ausgabe), overwrite)


def _teil_name(eingabe: Path, gruppe: list[int]) -> str:
    if len(gruppe) == 1:
        return f"{eingabe.stem}-seite-{gruppe[0] + 1}.pdf"
    return f"{eingabe.stem}-seiten-{gruppe[0] + 1}-{gruppe[-1] + 1}.pdf"


def teilen(
    eingabe: str | Path,
    ausgabe_ordner: str | Path | None = None,
    *,
    seiten: str | None = None,
    passwort: str | None = None,
    overwrite: bool = False,
) -> list[Path]:
    """Teilt ein PDF: jede Seite einzeln (Standard) oder nach Bereichen wie ``1-3,5``."""
    eingabe = Path(eingabe)
    ordner = Path(ausgabe_ordner) if ausgabe_ordner else eingabe.parent
    leser = lesen(eingabe, passwort)
    ergebnisse = []
    for gruppe in seiten_parsen(seiten, len(leser.pages)):
        writer = _pypdf().PdfWriter()
        for nummer in gruppe:
            writer.add_page(leser.pages[nummer])
        ergebnisse.append(_schreiben(writer, ordner / _teil_name(eingabe, gruppe), overwrite))
    return ergebnisse


def seiten_aendern(
    eingabe: str | Path,
    ausgabe: str | Path,
    *,
    drehen: int = 0,
    drehen_seiten: str | None = None,
    loeschen: str | None = None,
    passwort: str | None = None,
    overwrite: bool = False,
) -> Path:
    """Dreht Seiten (90/180/270 im Uhrzeigersinn) und/oder löscht Seiten."""
    if drehen not in (0, 90, 180, 270):
        raise BedienFehler("Drehen geht nur um 90, 180 oder 270 Grad.")
    leser = lesen(eingabe, passwort)
    anzahl = len(leser.pages)
    zu_drehen = set(seiten_menge(drehen_seiten, anzahl)) if drehen else set()
    weg = set(seiten_menge(loeschen, anzahl)) if loeschen else set()
    if len(weg) >= anzahl:
        raise BedienFehler("Es würden alle Seiten gelöscht – mindestens eine muss bleiben.")
    writer = _pypdf().PdfWriter()
    for nummer, seite in enumerate(leser.pages):
        if nummer in weg:
            continue
        neu = writer.add_page(seite)
        if nummer in zu_drehen:
            neu.rotate(drehen)
    return _schreiben(writer, Path(ausgabe), overwrite)


# --- PDF ↔ Bilder ------------------------------------------------------------------------


def seite_rendern(
    pfad: str | Path, nummer: int = 0, *, dpi: float = 72, passwort: str | None = None
) -> Image.Image:
    """Rendert eine Seite (0-basiert) mit pdfium als RGB-Bild."""
    pdfium = _pdfium()
    with _PDFIUM_SPERRE:
        try:
            dokument = pdfium.PdfDocument(str(pfad), password=passwort)
        except pdfium.PdfiumError as fehler:
            if "password" in str(fehler).lower():
                raise PasswortNoetig(Path(pfad), falsch=bool(passwort)) from fehler
            raise MiksanFehler(f"'{pfad}' ist kein gültiges oder ein beschädigtes PDF.") from fehler
        try:
            if not 0 <= nummer < len(dokument):
                raise BedienFehler(f"Seite {nummer + 1} gibt es nicht.")
            seite = dokument[nummer]
            bild = seite.render(scale=dpi / 72).to_pil().convert("RGB")
            seite.close()
        finally:
            dokument.close()
    return bild


def zu_bildern(
    eingabe: str | Path,
    ausgabe_ordner: str | Path | None = None,
    *,
    bildformat: str = "png",
    dpi: int = STANDARD_DPI,
    seiten: str | None = None,
    passwort: str | None = None,
    overwrite: bool = False,
    abbrechen: threading.Event | None = None,
) -> list[Path]:
    """Speichert Seiten als PNG oder JPEG (``<name>-seite-01.png`` …)."""
    bildformat = {"jpg": "jpeg"}.get(bildformat.lower(), bildformat.lower())
    if bildformat not in ("png", "jpeg"):
        raise BedienFehler("PDF → Bilder kann PNG oder JPEG schreiben.")
    if not 30 <= dpi <= 1200:
        raise BedienFehler("Die Auflösung muss zwischen 30 und 1200 DPI liegen.")
    eingabe = Path(eingabe)
    ordner = Path(ausgabe_ordner) if ausgabe_ordner else eingabe.parent
    anzahl = seiten_anzahl(eingabe, passwort)
    stellen = max(2, len(str(anzahl)))
    endung = ".jpg" if bildformat == "jpeg" else ".png"
    ergebnisse = []
    for nummer in seiten_menge(seiten, anzahl):
        if abbrechen is not None and abbrechen.is_set():
            break
        bild = seite_rendern(eingabe, nummer, dpi=dpi, passwort=passwort)
        ziel = ordner / f"{eingabe.stem}-seite-{nummer + 1:0{stellen}d}{endung}"
        ordner.mkdir(parents=True, exist_ok=True)
        optionen = {"optimize": True, "dpi": (dpi, dpi)}
        if bildformat == "jpeg":
            optionen["quality"] = 92
        _datei_schreiben(
            ziel,
            lambda datei, b=bild, o=optionen: b.save(datei, format=bildformat.upper(), **o),
            overwrite,
        )
        ergebnisse.append(ziel)
    return ergebnisse


def _auf_a4(bild: Image.Image, dpi: int) -> Image.Image:
    """Legt ein Bild zentriert mit Rand auf eine weisse A4-Seite (hoch oder quer)."""
    breite, hoehe = (round(mm / 25.4 * dpi) for mm in A4_MM)
    if bild.width > bild.height:
        breite, hoehe = hoehe, breite
    rand = round(10 / 25.4 * dpi)
    platz = (breite - 2 * rand, hoehe - 2 * rand)
    faktor = min(platz[0] / bild.width, platz[1] / bild.height, 1.0)
    if faktor < 1.0:
        groesse = (max(1, round(bild.width * faktor)), max(1, round(bild.height * faktor)))
        bild = bild.resize(groesse, Image.Resampling.LANCZOS)
    seite = Image.new("RGB", (breite, hoehe), (255, 255, 255))
    seite.paste(bild, ((breite - bild.width) // 2, (hoehe - bild.height) // 2))
    return seite


def aus_bildern(
    bilder: Sequence[str | Path],
    ausgabe: str | Path,
    *,
    seitengroesse: str = "a4",
    dpi: int = STANDARD_DPI,
    overwrite: bool = False,
) -> Path:
    """Macht aus Bildern (alle lesbaren Formate) ein PDF, ein Bild pro Seite."""
    if seitengroesse not in SEITENGROESSEN:
        raise BedienFehler(f"Seitengrösse '{seitengroesse}' gibt es nicht: a4 oder bild.")
    if not bilder:
        raise BedienFehler("Keine Bilder angegeben.")
    seiten = []
    for pfad in bilder:
        bild = laden(Path(pfad)).frames[0]
        if bild.mode in ("RGBA", "LA", "P"):
            bild = auf_hintergrund(bild.convert("RGBA"), (255, 255, 255))
        bild = bild.convert("RGB")
        seiten.append(_auf_a4(bild, dpi) if seitengroesse == "a4" else bild)
    erste, rest = seiten[0], seiten[1:]
    aufloesung = float(dpi) if seitengroesse == "a4" else 72.0

    def schreiben(datei) -> None:
        erste.save(datei, format="PDF", save_all=True, append_images=rest, resolution=aufloesung)

    ziel = Path(ausgabe)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    _datei_schreiben(ziel, schreiben, overwrite)
    return ziel


# --- Verkleinern -------------------------------------------------------------------------


def verkleinern(
    eingabe: str | Path,
    ausgabe: str | Path,
    *,
    qualitaet: int = STANDARD_QUALITAET,
    max_seite: int = 2000,
    passwort: str | None = None,
    overwrite: bool = False,
) -> tuple[Path, int, int]:
    """Komprimiert eingebettete Bilder neu (JPEG) und fasst doppelte Objekte zusammen.

    Gibt (Ausgabe, Grösse vorher, Grösse nachher) in Byte zurück.
    """
    if not 1 <= qualitaet <= 100:
        raise BedienFehler("Die Qualität muss zwischen 1 und 100 liegen.")
    eingabe = Path(eingabe)
    leser = lesen(eingabe, passwort)
    writer = _pypdf().PdfWriter(clone_from=leser)
    for seite in writer.pages:
        for bild in seite.images:
            try:
                neu = bild.image
                if neu.mode not in ("RGB", "L"):
                    neu = neu.convert("RGB")
                if max(neu.size) > max_seite:
                    neu.thumbnail((max_seite, max_seite), Image.Resampling.LANCZOS)
                bild.replace(neu, quality=qualitaet)
            except Exception:  # Masken, exotische Farbräume: Bild unverändert lassen
                continue
        seite.compress_content_streams()
    writer.compress_identical_objects()
    puffer = io.BytesIO()
    writer.write(puffer)
    vorher = eingabe.stat().st_size
    ziel = Path(ausgabe)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    daten = puffer.getvalue()
    if len(daten) >= vorher:  # nichts gewonnen: Original-Inhalt behalten
        daten = eingabe.read_bytes()
    _datei_schreiben(ziel, lambda datei: datei.write(daten), overwrite)
    return ziel, vorher, len(daten)


# --- Hilfen für Oberfläche und Kommandozeile ----------------------------------------------


def standard_name(eingabe: Path, zusatz: str, endung: str = ".pdf") -> str:
    return f"{eingabe.stem}-{zusatz}{endung}"


def nacheinander(
    eingaben: Iterable[Path],
    arbeit: Callable[[Path], list[Path]],
    rueckmeldung: Callable[[int, int, str], None] | None = None,
    abbrechen: threading.Event | None = None,
):
    """Verarbeitet PDFs nacheinander und sammelt das Ergebnis wie ``stapel.ausfuehren``."""
    from .stapel import Auftrag, StapelErgebnis

    eingaben = list(eingaben)
    ergebnis = StapelErgebnis()
    for index, eingabe in enumerate(eingaben):
        if abbrechen is not None and abbrechen.is_set():
            ergebnis.uebersprungen.append(Auftrag(eingabe, eingabe))
            continue
        try:
            ausgaben = arbeit(eingabe)
        except MiksanFehler as fehler:
            ergebnis.fehler.append((eingabe, str(fehler)))
        else:
            for ausgabe in ausgaben:
                ergebnis.ok.append(Auftrag(eingabe, ausgabe))
        if rueckmeldung is not None:
            rueckmeldung(index + 1, len(eingaben), eingabe.name)
    return ergebnis

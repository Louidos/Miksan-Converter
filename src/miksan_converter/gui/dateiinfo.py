"""Angaben, Miniaturen und Status für die Dateiliste (ohne Qt, normal testbar)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..convert import laden
from ..formats import format_aus_name
from ..stapel import StapelErgebnis, dateien_sammeln


@dataclass
class DateiInfo:
    """Angaben für eine Zeile der Dateiliste."""

    pfad: Path
    ordner: bool = False
    format: str = ""
    breite: int | None = None
    hoehe: int | None = None
    groesse: int | None = None  # Byte
    anzahl: int | None = None  # bei Ordnern: Anzahl Bilder (ohne Unterordner)
    seiten: int | None = None  # bei PDFs
    geschuetzt: bool = False  # PDF mit Passwort

    def text(self) -> str:
        """Kurze Zeile unter dem Dateinamen, z. B. "PNG · 1200 × 800 · 1.4 MB"."""
        if self.ordner:
            return "Ordner" if self.anzahl is None else f"Ordner · {self.anzahl} Dateien"
        teile = [self.format] if self.format else []
        if self.geschuetzt:
            teile.append("mit Passwort")
        elif self.seiten is not None:
            teile.append(f"{self.seiten} Seite{'n' if self.seiten != 1 else ''}")
        if self.breite and self.hoehe:
            teile.append(f"{self.breite} × {self.hoehe}")
        if self.groesse is not None:
            teile.append(groesse_text(self.groesse))
        return " · ".join(teile)


def groesse_text(byte: int) -> str:
    """Dateigrösse lesbar (1 KB = 1000 Byte wie bei ``--zielgroesse``)."""
    if byte < 1000:
        return f"{byte} B"
    for einheit, faktor in (("KB", 1e3), ("MB", 1e6), ("GB", 1e9)):
        wert = byte / faktor
        if wert < 1000 or einheit == "GB":
            return f"{wert:.0f} {einheit}" if wert >= 100 else f"{wert:.1f} {einheit}"
    return f"{byte} B"  # pragma: no cover


def datei_info(pfad: str | Path) -> DateiInfo:
    """Liest Format und Masse aus dem Dateikopf (schnell, ohne das ganze Bild zu laden)."""
    from PIL import Image

    pfad = Path(pfad)
    if pfad.is_dir():
        try:
            dateien, _ = dateien_sammeln([pfad], rekursiv=False)
            anzahl = len(dateien)
        except Exception:  # Ordner nicht lesbar: nur "Ordner" anzeigen
            anzahl = None
        return DateiInfo(pfad, ordner=True, anzahl=anzahl)
    info = DateiInfo(pfad, format=pfad.suffix.lstrip(".").upper())
    try:
        info.groesse = pfad.stat().st_size
    except OSError:
        return info
    if pfad.suffix.lower() == ".pdf":
        return _pdf_info(info)
    try:
        with Image.open(pfad) as bild:
            info.breite, info.hoehe = bild.size
            fmt = format_aus_name(bild.format.lower()) if bild.format else None
            info.format = fmt.name.upper() if fmt else (bild.format or info.format)
            if bild.getexif().get(0x0112, 1) in (5, 6, 7, 8):  # wird beim Laden gedreht
                info.breite, info.hoehe = info.hoehe, info.breite
    except Exception:  # SVG, RAW, PDF, Video … : nur Endung und Grösse
        pass
    return info


def _pdf_info(info: DateiInfo) -> DateiInfo:
    try:
        from .. import pdf

        if pdf.ist_verschluesselt(info.pfad):
            info.geschuetzt = True
        else:
            info.seiten = pdf.seiten_anzahl(info.pfad)
    except Exception:  # ohne Extra [pdf] oder beschädigt: nur Endung und Grösse
        pass
    return info


def _pdf_miniatur(pfad: Path, kante: int):
    from .. import pdf

    try:
        bild = pdf.seite_rendern(pfad, 0, dpi=36)
    except Exception:  # ohne Extra, geschützt oder beschädigt
        return None
    faktor = kante / max(bild.size)
    if faktor < 1:
        groesse = (max(1, round(bild.width * faktor)), max(1, round(bild.height * faktor)))
        bild = bild.resize(groesse)
    return bild.convert("RGBA")


def miniatur(pfad: str | Path, kante: int = 96):
    """Kleines Vorschaubild (PIL, RGBA) oder ``None``, wenn die Datei kein Bild ist."""
    from PIL import Image, ImageOps

    pfad = Path(pfad)
    if pfad.is_dir():
        return None
    if pfad.suffix.lower() == ".pdf":
        return _pdf_miniatur(pfad, kante)
    try:
        with Image.open(pfad) as offen:
            offen.draft("RGB", (kante * 2, kante * 2))  # JPEG: gleich verkleinert laden
            offen.seek(0)
            bild = ImageOps.exif_transpose(offen).convert("RGBA")
    except Exception:  # SVG, RAW u. a. über den normalen Weg laden
        try:
            bild = laden(pfad).frames[0].convert("RGBA")
        except Exception:
            return None
    bild.thumbnail((kante, kante), Image.Resampling.LANCZOS)
    return bild


OK = "ok"
HINWEIS = "hinweis"
FEHLER = "fehler"


def status_fuer(pfad: str | Path, ergebnis: StapelErgebnis) -> tuple[str, str]:
    """Status eines Listeneintrags nach dem Lauf: (``OK``/``HINWEIS``/``FEHLER``/"", Text).

    Bei Ordnern werden alle Dateien darin zusammengezählt.
    """
    pfad = Path(pfad)

    def gehoert(anderer: Path) -> bool:
        return anderer == pfad or pfad in anderer.parents

    ok = sum(1 for auftrag in ergebnis.ok if gehoert(auftrag.eingabe))
    fehler = [meldung for p, meldung in ergebnis.fehler if gehoert(Path(p))]
    hinweise = [meldung for p, meldung in ergebnis.hinweise if gehoert(Path(p))]
    if pfad.is_dir():
        if not (ok or fehler):
            return ("", "")
        text = f"{ok} ok, {len(fehler)} Fehler"
        return (FEHLER if fehler else HINWEIS if hinweise else OK, text)
    if fehler:
        return (FEHLER, fehler[0].replace(f"'{pfad}' ", "").replace(f"{pfad}: ", ""))
    if hinweise:
        return (HINWEIS, hinweise[0])
    if ok:
        return (OK, "fertig")
    if any(gehoert(auftrag.eingabe) for auftrag in ergebnis.uebersprungen):
        return (HINWEIS, "abgebrochen")
    return ("", "")

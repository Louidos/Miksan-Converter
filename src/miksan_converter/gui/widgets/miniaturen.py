"""Lädt Miniaturbilder und Dateiangaben im Hintergrund (Thread-Pool), mit Zwischenspeicher."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QImage

from .. import dateiinfo as logik

KANTE = 96  # Pixel der Miniatur (wird für hohe Auflösung doppelt so gross geladen)


def qimage_aus_pil(bild) -> QImage:
    """PIL-Bild (RGBA) -> QImage (Kopie, darf aus jedem Thread kommen)."""
    rgba = bild.convert("RGBA")
    daten = rgba.tobytes("raw", "RGBA")
    breite, hoehe = rgba.size
    return QImage(daten, breite, hoehe, breite * 4, QImage.Format.Format_RGBA8888).copy()


class _Bote(QObject):
    fertig = Signal(str, object, object)  # Pfad, QImage | None, DateiInfo


class _Aufgabe(QRunnable):
    def __init__(self, pfad: str, bote: _Bote, mit_bild: Callable[[str], object]) -> None:
        super().__init__()
        self.pfad = pfad
        self.bote = bote
        self.mit_bild = mit_bild

    def run(self) -> None:
        try:
            info = logik.datei_info(self.pfad)
            bild = self.mit_bild(self.pfad)
            qbild = qimage_aus_pil(bild) if bild is not None else None
        except Exception:  # eine kaputte Datei darf den Pool nie stören
            info, qbild = logik.DateiInfo(Path(self.pfad)), None
        self.bote.fertig.emit(self.pfad, qbild, info)


class MiniaturLader(QObject):
    """Ein Lader für das ganze Fenster: jede Datei wird nur einmal gelesen."""

    geladen = Signal(str)  # Pfad

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bilder: dict[str, QImage | None] = {}
        self._infos: dict[str, logik.DateiInfo] = {}
        self._laufend: set[str] = set()
        self._bote = _Bote()
        self._bote.fertig.connect(self._fertig)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)  # Fenster bleibt flüssig
        # austauschbar (z. B. Video-Vorschaubild in späteren Werkzeugen)
        self.bild_laden: Callable[[str], object] = lambda pfad: logik.miniatur(pfad, KANTE * 2)

    def anfordern(self, pfad: str) -> None:
        if pfad in self._infos or pfad in self._laufend:
            return
        self._laufend.add(pfad)
        self.pool.start(_Aufgabe(pfad, self._bote, self.bild_laden))

    def bild(self, pfad: str) -> QImage | None:
        return self._bilder.get(pfad)

    def info(self, pfad: str) -> logik.DateiInfo | None:
        return self._infos.get(pfad)

    def vergessen(self, pfad: str) -> None:
        """Nach dem Ändern einer Datei neu laden lassen."""
        self._bilder.pop(pfad, None)
        self._infos.pop(pfad, None)

    def warten(self, ms: int = 10_000) -> bool:
        return self.pool.waitForDone(ms)

    def _fertig(self, pfad: str, bild, info) -> None:
        self._laufend.discard(pfad)
        self._bilder[pfad] = bild
        self._infos[pfad] = info
        self.geladen.emit(pfad)

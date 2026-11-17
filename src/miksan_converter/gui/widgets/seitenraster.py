"""Seiten-Miniaturen eines PDFs (im Hintergrund gerendert), mit Mehrfachauswahl."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QListView, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from .. import design
from .miniaturen import qimage_aus_pil

KANTE = 120
HOECHSTENS = 300  # mehr Seiten werden nicht als Miniatur gezeigt


class _Bote(QObject):
    seite = Signal(int, str, int, object)  # Lauf, Pfad, Nummer, QImage
    fehler = Signal(int, str)


class _Rendern(QRunnable):
    def __init__(self, lauf: int, pfad: str, passwort: str | None, bote: _Bote) -> None:
        super().__init__()
        self.lauf, self.pfad, self.passwort, self.bote = lauf, pfad, passwort, bote
        self.abbrechen = False

    def run(self) -> None:
        from ... import pdf

        try:
            anzahl = min(pdf.seiten_anzahl(self.pfad, self.passwort), HOECHSTENS)
            for nummer in range(anzahl):
                if self.abbrechen:
                    return
                bild = pdf.seite_rendern(self.pfad, nummer, dpi=24, passwort=self.passwort)
                bild.thumbnail((KANTE, KANTE))
                self.bote.seite.emit(self.lauf, self.pfad, nummer, qimage_aus_pil(bild))
        except Exception as fehler:  # geschützt, beschädigt: Hinweis statt Absturz
            self.bote.fehler.emit(self.lauf, str(fehler))


class SeitenRaster(QWidget):
    """Zeigt alle Seiten des gewählten PDFs; ``auswahl()`` liefert die markierten (ab 1)."""

    auswahl_geaendert = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.pfad: str | None = None
        self._lauf = 0
        self._aufgabe: _Rendern | None = None
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._bote = _Bote()
        self._bote.seite.connect(self._seite)
        self._bote.fehler.connect(self._fehler)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, design.abstand(1), 0, 0)
        layout.setSpacing(design.abstand(0.5))
        self.titel = design.eigenschaft(QLabel("Seiten"), "untertitel")
        layout.addWidget(self.titel)
        self.liste = QListWidget()
        self.liste.setViewMode(QListView.ViewMode.IconMode)
        self.liste.setIconSize(QSize(KANTE, KANTE))
        self.liste.setResizeMode(QListView.ResizeMode.Adjust)
        self.liste.setMovement(QListView.Movement.Static)
        self.liste.setSpacing(design.abstand(1))
        self.liste.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.liste.itemSelectionChanged.connect(lambda: self.auswahl_geaendert.emit(self.auswahl()))
        layout.addWidget(self.liste, 1)
        self.hinweis = design.eigenschaft(QLabel(""), "hinweis")
        self.hinweis.setWordWrap(True)
        layout.addWidget(self.hinweis)

    def zeigen(self, pfad: str | None, passwort: str | None = None) -> None:
        if self._aufgabe is not None:
            self._aufgabe.abbrechen = True
        self._lauf += 1
        self.pfad = pfad
        self.liste.clear()
        self.hinweis.setText("")
        if pfad is None:
            self.titel.setText("Seiten")
            return
        self.titel.setText("Seiten werden geladen …")
        self._aufgabe = _Rendern(self._lauf, pfad, passwort, self._bote)
        self._aufgabe.setAutoDelete(False)
        self._pool.start(self._aufgabe)

    def auswahl(self) -> list[int]:
        return sorted(self.liste.row(e) + 1 for e in self.liste.selectedItems())

    def warten(self, ms: int = 10_000) -> bool:
        return self._pool.waitForDone(ms)

    def _seite(self, lauf: int, pfad: str, nummer: int, bild) -> None:
        if lauf != self._lauf:
            return
        eintrag = QListWidgetItem(QPixmap.fromImage(bild), f"{nummer + 1}")
        eintrag.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.liste.addItem(eintrag)
        self.titel.setText(f"Seiten ({self.liste.count()})")

    def _fehler(self, lauf: int, text: str) -> None:
        if lauf == self._lauf:
            self.titel.setText("Seiten")
            self.hinweis.setText(text)

    def schliessen(self) -> None:
        if self._aufgabe is not None:
            self._aufgabe.abbrechen = True
        self._pool.waitForDone(5000)

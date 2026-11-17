"""Dateiliste mit Miniaturbild, Name, Angaben, Status nach dem Lauf und X zum Entfernen."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import dateiinfo as logik
from .. import design
from . import abgelegte_pfade
from .miniaturen import MiniaturLader

_STATUS_ROLLE = {logik.OK: "erfolg", logik.HINWEIS: "warnung", logik.FEHLER: "fehler"}
_STATUS_ICON = {logik.OK: "haken", logik.HINWEIS: "warnung", logik.FEHLER: "fehler"}
_STATUS_FARBE = {
    logik.OK: design.ERFOLG,
    logik.HINWEIS: design.WARNUNG,
    logik.FEHLER: design.FEHLER,
}
MINIATUR = 48


class DateiZeile(QWidget):
    """Eine Zeile der Liste (wird über ``setItemWidget`` angezeigt)."""

    entfernen = Signal(str)

    def __init__(self, pfad: str) -> None:
        super().__init__()
        self.pfad = pfad
        self.setToolTip(pfad)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(design.abstand(1), design.abstand(0.5), design.abstand(0.5), 4)
        layout.setSpacing(design.abstand(1.5))

        self.bild = QLabel()
        self.bild.setFixedSize(MINIATUR, MINIATUR)
        self.bild.setAlignment(Qt.AlignmentFlag.AlignCenter)
        symbol = "ordner" if Path(pfad).is_dir() else "bild"
        if Path(pfad).suffix.lower() == ".pdf":
            symbol = "pdf"
        from ..werkzeuge import AUDIO, VIDEO, datei_art

        symbol = {VIDEO: "video", AUDIO: "audio"}.get(datei_art(pfad), symbol)
        self.bild.setPixmap(design.icon(symbol, design.NEBENTEXT).pixmap(28, 28))
        layout.addWidget(self.bild)

        texte = QVBoxLayout()
        texte.setSpacing(2)
        self.name = QLabel(Path(pfad).name or pfad)
        self.name.setTextFormat(Qt.TextFormat.PlainText)
        self.angaben = design.eigenschaft(QLabel(""), "hinweis")
        self.status = QLabel("")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.status.setVisible(False)
        texte.addWidget(self.name)
        texte.addWidget(self.angaben)
        texte.addWidget(self.status)
        layout.addLayout(texte, 1)

        self.status_symbol = QLabel()
        self.status_symbol.setFixedSize(20, 20)
        layout.addWidget(self.status_symbol)
        self.knopf_entfernen = design.eigenschaft(QToolButton(), "flach")
        self.knopf_entfernen.setIcon(design.icon("schliessen", design.NEBENTEXT))
        self.knopf_entfernen.setToolTip("Aus der Liste entfernen")
        self.knopf_entfernen.setAccessibleName(f"{Path(pfad).name} entfernen")
        self.knopf_entfernen.clicked.connect(lambda: self.entfernen.emit(self.pfad))
        layout.addWidget(self.knopf_entfernen)

    def info_setzen(self, bild, info: logik.DateiInfo | None) -> None:
        if bild is not None and not bild.isNull():
            pixmap = QPixmap.fromImage(bild)
            verhaeltnis = self.devicePixelRatioF() or 1.0
            pixmap = pixmap.scaled(
                QSize(MINIATUR, MINIATUR) * verhaeltnis,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            pixmap.setDevicePixelRatio(verhaeltnis)
            self.bild.setPixmap(pixmap)
        if info is not None:
            self.angaben.setText(info.text())

    def status_setzen(self, art: str, text: str) -> None:
        self.status.setText(text if art != logik.OK else "")
        self.status.setVisible(bool(text) and art != logik.OK)
        if art:
            design.eigenschaft(self.status, _STATUS_ROLLE[art])
            icon = design.icon(_STATUS_ICON[art], _STATUS_FARBE[art])
            self.status_symbol.setPixmap(icon.pixmap(18, 18))
            self.status_symbol.setToolTip(text)
        else:
            self.status_symbol.clear()


class DateiListe(QListWidget):
    """Liste der Eingaben einer Werkzeug-Seite; nimmt Dateien und Ordner per Drag & Drop an."""

    abgelegt = Signal(list)
    geaendert = Signal()

    def __init__(self, lader: MiniaturLader, passt: Callable[[str], bool] | None = None) -> None:
        super().__init__()
        self.lader = lader
        self.passt = passt or (lambda pfad: True)
        self._zeilen: dict[str, tuple[QListWidgetItem, DateiZeile]] = {}
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setUniformItemSizes(False)
        self._sortierbar = False
        lader.geladen.connect(self._geladen)

    def sortierbar_machen(self) -> None:
        """Reihenfolge per Ziehen (und Alt+↑/↓) änderbar, z. B. zum Zusammenfügen."""
        self._sortierbar = True
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setToolTip("Reihenfolge per Ziehen oder mit Alt+↑/↓ ändern")

    def verschieben(self, von: int, nach: int) -> None:
        """Verschiebt den Eintrag von Zeile ``von`` nach ``nach`` (mit neuem Zeilen-Widget)."""
        if not (0 <= von < self.count()) or von == nach:
            return
        nach = max(0, min(nach, self.count() - 1))
        eintrag = self.takeItem(von)
        pfad = eintrag.data(Qt.ItemDataRole.UserRole)
        alte = self._zeilen[pfad][1]
        self.insertItem(nach, eintrag)
        zeile = DateiZeile(pfad)
        zeile.entfernen.connect(self.entfernen)
        zeile.info_setzen(self.lader.bild(pfad), self.lader.info(pfad))
        zeile.status_setzen("", "")
        alte.deleteLater()
        self.setItemWidget(eintrag, zeile)
        eintrag.setSizeHint(zeile.sizeHint())
        self._zeilen[pfad] = (eintrag, zeile)
        self.setCurrentRow(nach)
        self.geaendert.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if self._sortierbar and event.modifiers() & Qt.KeyboardModifier.AltModifier:
            schritt = {Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1}.get(event.key())
            if schritt is not None and self.currentRow() >= 0:
                self.verschieben(self.currentRow(), self.currentRow() + schritt)
                return
        super().keyPressEvent(event)

    # --- Inhalt ---------------------------------------------------------------------

    def pfade(self) -> list[str]:
        return [self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]

    def pfade_hinzufuegen(self, pfade) -> tuple[list[str], list[str]]:
        """Fügt passende, noch nicht enthaltene Pfade an; gibt (neu, abgelehnt) zurück."""
        neu, abgelehnt = [], []
        for pfad in pfade:
            text = str(Path(pfad))
            if text in self._zeilen:
                continue
            if not self.passt(text):
                abgelehnt.append(text)
                continue
            eintrag = QListWidgetItem()
            eintrag.setData(Qt.ItemDataRole.UserRole, text)
            eintrag.setToolTip(text)
            zeile = DateiZeile(text)
            zeile.entfernen.connect(self.entfernen)
            eintrag.setSizeHint(zeile.sizeHint())
            self.addItem(eintrag)
            self.setItemWidget(eintrag, zeile)
            self._zeilen[text] = (eintrag, zeile)
            zeile.info_setzen(self.lader.bild(text), self.lader.info(text))
            self.lader.anfordern(text)
            neu.append(text)
        if neu:
            self.geaendert.emit()
        return neu, abgelehnt

    def entfernen(self, pfad: str) -> None:
        eintrag = self._zeilen.pop(pfad, (None, None))[0]
        if eintrag is not None:
            self.takeItem(self.row(eintrag))
            self.geaendert.emit()

    def auswahl_entfernen(self) -> None:
        for eintrag in self.selectedItems():
            self._zeilen.pop(eintrag.data(Qt.ItemDataRole.UserRole), None)
            self.takeItem(self.row(eintrag))
        self.geaendert.emit()

    def leeren(self) -> None:
        self._zeilen.clear()
        self.clear()
        self.geaendert.emit()

    def zeile(self, pfad: str) -> DateiZeile | None:
        return self._zeilen.get(str(Path(pfad)), (None, None))[1]

    def ausgewaehlter_pfad(self) -> str | None:
        eintrag = self.currentItem()
        return eintrag.data(Qt.ItemDataRole.UserRole) if eintrag is not None else None

    # --- Status ---------------------------------------------------------------------

    def status_setzen(self, ergebnis) -> None:
        for pfad, (eintrag, zeile) in self._zeilen.items():
            zeile.status_setzen(*logik.status_fuer(pfad, ergebnis))
            eintrag.setSizeHint(zeile.sizeHint())

    def status_zuruecksetzen(self) -> None:
        for eintrag, zeile in self._zeilen.values():
            zeile.status_setzen("", "")
            eintrag.setSizeHint(zeile.sizeHint())

    def _geladen(self, pfad: str) -> None:
        eintrag, zeile = self._zeilen.get(pfad, (None, None))
        if zeile is not None:
            zeile.info_setzen(self.lader.bild(pfad), self.lader.info(pfad))
            eintrag.setSizeHint(zeile.sizeHint())

    # --- Drag & Drop ----------------------------------------------------------------

    def dragEnterEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if self._sortierbar and event.source() is self:
            event.accept()
        elif event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if self._sortierbar and event.source() is self:
            event.accept()
        elif event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if self._sortierbar and event.source() is self:
            ziel = self.indexAt(event.position().toPoint()).row()
            ziel = self.count() - 1 if ziel < 0 else ziel
            if self.currentRow() >= 0:
                self.verschieben(self.currentRow(), ziel)
            event.setDropAction(Qt.DropAction.IgnoreAction)
            event.accept()
            return
        pfade = abgelegte_pfade(event)
        if pfade:
            event.acceptProposedAction()
            self.abgelegt.emit(pfade)
        else:
            super().dropEvent(event)

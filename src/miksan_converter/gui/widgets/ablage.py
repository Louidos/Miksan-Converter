"""Grosse Ablagefläche „Dateien hierher ziehen“ mit Knöpfen zum Wählen."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from .. import design
from . import abgelegte_pfade


class Ablageflaeche(QFrame):
    """Nimmt Dateien und Ordner per Drag & Drop an; Knöpfe öffnen die Auswahldialoge."""

    abgelegt = Signal(list)
    dateien_waehlen = Signal()
    ordner_waehlen = Signal()

    def __init__(self, text: str = "Dateien hierher ziehen", unten: str = "") -> None:
        super().__init__()
        design.eigenschaft(self, "ablage")
        self.setAcceptDrops(True)
        self.setMinimumHeight(design.abstand(22))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*[design.abstand(3)] * 4)
        layout.setSpacing(design.abstand(1.5))
        layout.addStretch(1)
        symbol = QLabel()
        symbol.setPixmap(design.icon("herunterladen", design.AKZENT).pixmap(48, 48))
        symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(symbol)
        titel = design.eigenschaft(QLabel(text), "untertitel")
        titel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titel)
        if unten:
            hinweis = design.eigenschaft(QLabel(unten), "hinweis")
            hinweis.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hinweis.setWordWrap(True)
            layout.addWidget(hinweis)

        knoepfe = QHBoxLayout()
        knoepfe.addStretch(1)
        self.knopf_dateien = QPushButton(design.icon("hinzufuegen", design.AKZENT), "Dateien …")
        self.knopf_dateien.clicked.connect(self.dateien_waehlen)
        self.knopf_ordner = QPushButton(design.icon("ordner", design.AKZENT), "Ordner …")
        self.knopf_ordner.clicked.connect(self.ordner_waehlen)
        knoepfe.addWidget(self.knopf_dateien)
        knoepfe.addWidget(self.knopf_ordner)
        knoepfe.addStretch(1)
        layout.addLayout(knoepfe)
        layout.addStretch(1)

    def _aktiv(self, aktiv: bool) -> None:
        self.setProperty("aktiv", aktiv)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._aktiv(True)

    def dragMoveEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self._aktiv(False)

    def dropEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self._aktiv(False)
        pfade = abgelegte_pfade(event)
        if pfade:
            event.acceptProposedAction()
            self.abgelegt.emit(pfade)

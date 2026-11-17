"""Startseite: Karten für alle Werkzeuge und eine grosse Ablagefläche.

Nach dem Ablegen werden die Werkzeuge angeboten, die zu den Dateien passen.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import design
from ..werkzeuge import Werkzeug, nach_bereich, passende_werkzeuge
from ..widgets.ablage import Ablageflaeche
from .basis import kopf

SPALTEN = 3


class Karte(QFrame):
    """Klickbare Karte für ein Werkzeug (auch mit Tastatur: Leertaste/Enter)."""

    gewaehlt = Signal(str)

    def __init__(self, werkzeug: Werkzeug) -> None:
        super().__init__()
        self.werkzeug = werkzeug
        design.eigenschaft(self, "karte")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(werkzeug.titel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(*[design.abstand(2)] * 4)
        layout.setSpacing(design.abstand(1))
        farbe = design.AKZENT if werkzeug.verfuegbar() else design.TEXT_AUS
        symbol = QLabel()
        symbol.setPixmap(design.icon(werkzeug.icon, farbe).pixmap(design.ICON_GROSS))
        layout.addWidget(symbol)
        layout.addWidget(design.eigenschaft(QLabel(werkzeug.titel), "untertitel"))
        text = design.eigenschaft(QLabel(werkzeug.hinweis() or werkzeug.beschreibung), "hinweis")
        text.setWordWrap(True)
        layout.addWidget(text, 1)
        self.setToolTip(werkzeug.hinweis() or werkzeug.beschreibung)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if event.button() == Qt.MouseButton.LeftButton:
            self.gewaehlt.emit(self.werkzeug.name)

    def keyPressEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.gewaehlt.emit(self.werkzeug.name)
        else:
            super().keyPressEvent(event)


class StartSeite(QWidget):
    werkzeug_gewaehlt = Signal(str, list)  # Name, Dateien (leer = ohne Dateien öffnen)

    def __init__(self, settings: QSettings) -> None:
        super().__init__()
        self.settings = settings
        self.abgelegte: list[str] = []
        self.setAcceptDrops(True)
        aussen = QVBoxLayout(self)
        aussen.setContentsMargins(0, 0, 0, 0)

        inhalt = QWidget()
        layout = QVBoxLayout(inhalt)
        layout.setContentsMargins(0, 0, design.abstand(3), design.abstand(3))
        layout.setSpacing(design.abstand(2))
        layout.addWidget(
            kopf(
                "Willkommen bei Miksan-Converter",
                "Dateien ablegen oder ein Werkzeug wählen. Alles läuft lokal auf diesem Rechner.",
            )
        )
        innen = QVBoxLayout()
        innen.setContentsMargins(design.abstand(3), 0, 0, 0)
        innen.setSpacing(design.abstand(2))
        self.ablage = Ablageflaeche(
            "Dateien hierher ziehen", "Danach werden die passenden Werkzeuge angeboten."
        )
        self.ablage.abgelegt.connect(self.dateien_ablegen)
        self.ablage.dateien_waehlen.connect(self.dateien_waehlen)
        self.ablage.ordner_waehlen.connect(self.ordner_waehlen)
        innen.addWidget(self.ablage)

        self.auswahl = QFrame()
        design.eigenschaft(self.auswahl, "karte")
        self.auswahl_layout = QVBoxLayout(self.auswahl)
        self.auswahl_layout.setContentsMargins(*[design.abstand(2)] * 4)
        self.auswahl.setVisible(False)
        innen.addWidget(self.auswahl)

        self.karten: dict[str, Karte] = {}
        for bereich, eintraege in nach_bereich():
            innen.addWidget(design.eigenschaft(QLabel(bereich), "untertitel"))
            raster = QGridLayout()
            raster.setSpacing(design.abstand(2))
            for i, werkzeug in enumerate(eintraege):
                karte = Karte(werkzeug)
                karte.gewaehlt.connect(lambda name: self.werkzeug_gewaehlt.emit(name, []))
                self.karten[werkzeug.name] = karte
                raster.addWidget(karte, i // SPALTEN, i % SPALTEN)
            for spalte in range(SPALTEN):
                raster.setColumnStretch(spalte, 1)
            innen.addLayout(raster)
        innen.addStretch(1)
        layout.addLayout(innen)

        rollen = QScrollArea()
        rollen.setWidgetResizable(True)
        rollen.setFrameShape(QScrollArea.Shape.NoFrame)
        rollen.setWidget(inhalt)
        aussen.addWidget(rollen)

    # --- Dateien --------------------------------------------------------------------

    def pfade_hinzufuegen(self, pfade) -> list[str]:
        self.dateien_ablegen(list(pfade))
        return list(pfade)

    def dateien_ablegen(self, pfade: list[str]) -> None:
        """Merkt die Dateien und bietet die passenden Werkzeuge an."""
        for pfad in pfade:
            if str(Path(pfad)) not in self.abgelegte:
                self.abgelegte.append(str(Path(pfad)))
        self._auswahl_zeigen()

    def dateien_waehlen(self) -> None:
        dateien, _ = QFileDialog.getOpenFileNames(
            self, "Dateien wählen", self.settings.value("letzter_ordner", "", type=str)
        )
        if dateien:
            self.settings.setValue("letzter_ordner", str(Path(dateien[0]).parent))
            self.dateien_ablegen(dateien)

    def ordner_waehlen(self) -> None:
        ordner = QFileDialog.getExistingDirectory(
            self, "Ordner wählen", self.settings.value("letzter_ordner", "", type=str)
        )
        if ordner:
            self.dateien_ablegen([ordner])

    def leeren(self) -> None:
        self.abgelegte = []
        self._auswahl_zeigen()

    def _auswahl_zeigen(self) -> None:
        while self.auswahl_layout.count():
            eintrag = self.auswahl_layout.takeAt(0)
            if eintrag.widget():
                eintrag.widget().deleteLater()
            elif eintrag.layout():
                _layout_leeren(eintrag.layout())
        if not self.abgelegte:
            self.auswahl.setVisible(False)
            return
        anzahl = len(self.abgelegte)
        titel = f"{anzahl} Datei{'en' if anzahl != 1 else ''} abgelegt – was möchtest du tun?"
        self.auswahl_layout.addWidget(design.eigenschaft(QLabel(titel), "untertitel"))
        self.knoepfe: dict[str, QPushButton] = {}
        passende = passende_werkzeuge(self.abgelegte)
        zeile = QHBoxLayout()
        zeile.setSpacing(design.abstand(1))
        for werkzeug, treffer in passende:
            knopf = QPushButton(design.icon(werkzeug.icon, design.AKZENT), werkzeug.titel)
            knopf.setToolTip(werkzeug.hinweis() or f"{treffer} von {anzahl} Dateien passen")
            knopf.setEnabled(werkzeug.verfuegbar())
            knopf.clicked.connect(lambda _=False, name=werkzeug.name: self._oeffnen(name))
            zeile.addWidget(knopf)
            self.knoepfe[werkzeug.name] = knopf
        zeile.addStretch(1)
        leeren = design.eigenschaft(QPushButton("Verwerfen"), "flach")
        leeren.clicked.connect(self.leeren)
        zeile.addWidget(leeren)
        self.auswahl_layout.addLayout(zeile)
        if not passende:
            self.auswahl_layout.addWidget(
                design.eigenschaft(QLabel("Für diese Dateien gibt es kein Werkzeug."), "warnung")
            )
        self.auswahl.setVisible(True)

    def _oeffnen(self, name: str) -> None:
        pfade, self.abgelegte = self.abgelegte, []
        self._auswahl_zeigen()
        self.werkzeug_gewaehlt.emit(name, pfade)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self.ablage.dropEvent(event)


def _layout_leeren(layout) -> None:
    while layout.count():
        eintrag = layout.takeAt(0)
        if eintrag.widget():
            eintrag.widget().deleteLater()

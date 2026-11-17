"""Feste Leiste unten auf jeder Werkzeug-Seite: Ausgabeordner, Fortschritt, Start, Abbrechen."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import design


class Ausklapper(QWidget):
    """„Erweitert“: Knopf mit Pfeil, der einen Bereich mit seltenen Optionen ein- und ausklappt."""

    def __init__(self, titel: str = "Erweitert", inhalt: QWidget | None = None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.knopf = design.eigenschaft(QPushButton(titel), "flach")
        self.knopf.setCheckable(True)
        self.knopf.toggled.connect(self.aufklappen)
        layout.addWidget(self.knopf, 0, Qt.AlignmentFlag.AlignLeft)
        self.inhalt = inhalt or QWidget()
        layout.addWidget(self.inhalt)
        self.aufklappen(False)

    def aufklappen(self, offen: bool) -> None:
        if self.knopf.isChecked() != offen:
            self.knopf.setChecked(offen)
            return
        self.knopf.setIcon(design.icon("aufklappen" if offen else "zuklappen", design.AKZENT))
        self.inhalt.setVisible(offen)


class Ablaufleiste(QFrame):
    def __init__(self, start_text: str = "Start") -> None:
        super().__init__()
        design.eigenschaft(self, "leiste")
        self._offen: Path | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(design.abstand(3), design.abstand(1.5), design.abstand(3), 16)
        layout.setSpacing(design.abstand(1))

        zeile = QHBoxLayout()
        zeile.setSpacing(design.abstand(1))
        zeile.addWidget(QLabel("Ausgabeordner:"))
        self.ausgabe_ordner = QLineEdit()
        self.ausgabe_ordner.setClearButtonEnabled(True)
        zeile.addWidget(self.ausgabe_ordner, 1)
        self.knopf_ausgabe = QPushButton(design.icon("ordner", design.AKZENT), "Wählen …")
        self.knopf_ausgabe.clicked.connect(self._ausgabe_waehlen)
        zeile.addWidget(self.knopf_ausgabe)
        layout.addLayout(zeile)

        zeile = QHBoxLayout()
        zeile.setSpacing(design.abstand(1))
        self.fortschritt = QProgressBar()
        self.fortschritt.setValue(0)
        zeile.addWidget(self.fortschritt, 1)
        self.knopf_abbrechen = QPushButton(design.icon("stopp", design.AKZENT), "Abbrechen")
        self.knopf_abbrechen.setEnabled(False)
        self.knopf_abbrechen.setToolTip("Abbrechen (Esc)")
        zeile.addWidget(self.knopf_abbrechen)
        self.knopf_start = QPushButton(design.icon("abspielen", design.AUF_AKZENT), start_text)
        design.eigenschaft(self.knopf_start, "primaer")
        self.knopf_start.setDefault(True)
        self.knopf_start.setToolTip("Starten (Strg+Enter)")
        zeile.addWidget(self.knopf_start)
        layout.addLayout(zeile)

        zeile = QHBoxLayout()
        self.status = QLabel("Bereit.")
        self.status.setWordWrap(True)
        zeile.addWidget(self.status, 1)
        self.knopf_oeffnen = QPushButton(
            design.icon("ordner_oeffnen", design.AKZENT), "Ausgabeordner öffnen"
        )
        self.knopf_oeffnen.setEnabled(False)
        self.knopf_oeffnen.clicked.connect(self._ausgabe_oeffnen)
        zeile.addWidget(self.knopf_oeffnen)
        layout.addLayout(zeile)

        self.banner = QFrame()
        design.eigenschaft(self.banner, "karte")
        banner = QHBoxLayout(self.banner)
        banner.setContentsMargins(design.abstand(2), design.abstand(1), design.abstand(1), 8)
        self.banner_symbol = QLabel()
        banner.addWidget(self.banner_symbol)
        self.banner_text = QLabel()
        self.banner_text.setWordWrap(True)
        banner.addWidget(self.banner_text, 1)
        self.banner_oeffnen = QPushButton(
            design.icon("ordner_oeffnen", design.AUF_AKZENT), "Ordner öffnen"
        )
        design.eigenschaft(self.banner_oeffnen, "primaer")
        self.banner_oeffnen.clicked.connect(self._ausgabe_oeffnen)
        banner.addWidget(self.banner_oeffnen)
        schliessen = design.eigenschaft(QPushButton(), "flach")
        schliessen.setIcon(design.icon("schliessen", design.NEBENTEXT))
        schliessen.setToolTip("Meldung schliessen")
        schliessen.clicked.connect(lambda: self.banner.setVisible(False))
        banner.addWidget(schliessen)
        self.banner.setVisible(False)
        layout.insertWidget(0, self.banner)

        self.meldungen = QListWidget()
        self.meldungen.setMaximumHeight(design.abstand(15))
        self.meldungen.setVisible(False)
        layout.addWidget(self.meldungen)

    def standard_setzen(self, ordner: str) -> None:
        """Platzhalter: was bei leerem Feld passiert."""
        self.ausgabe_ordner.setPlaceholderText(
            f"Standard: {ordner}" if ordner else "neben dem Original"
        )

    def ordner(self, standard: str = "") -> Path | None:
        text = self.ausgabe_ordner.text().strip() or standard.strip()
        return Path(text) if text else None

    def _ausgabe_waehlen(self) -> None:
        ordner = QFileDialog.getExistingDirectory(
            self, "Ausgabeordner wählen", self.ausgabe_ordner.text()
        )
        if ordner:
            self.ausgabe_ordner.setText(ordner)

    def oeffnen_setzen(self, ordner: Path | None) -> None:
        self._offen = ordner
        self.knopf_oeffnen.setEnabled(ordner is not None and ordner.is_dir())

    def _ausgabe_oeffnen(self) -> None:
        if self._offen is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._offen)))

    def fertig_melden(self, text: str, fehler: bool) -> None:
        """Meldung nach dem Lauf mit Knopf „Ordner öffnen“ (wenn es einen Ordner gibt)."""
        symbol, farbe = ("warnung", design.WARNUNG) if fehler else ("haken", design.ERFOLG)
        self.banner_symbol.setPixmap(design.icon(symbol, farbe).pixmap(20, 20))
        self.banner_text.setText(text)
        self.banner_oeffnen.setVisible(self.knopf_oeffnen.isEnabled())
        self.banner.setVisible(True)

    def meldungen_setzen(self, zeilen: list[str]) -> None:
        self.meldungen.clear()
        self.meldungen.addItems(zeilen)
        self.meldungen.setVisible(bool(zeilen))

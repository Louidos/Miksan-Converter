"""Werkzeug „Wasserzeichen“: Text oder Logo, Position, Deckkraft, Grösse – mit Vorschau."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QWidget,
)

from ...convert import farbe_parsen, laden
from ...fehler import BedienFehler
from ...werkzeuge import wasserzeichen
from .. import design
from .bildwerkzeug import BildWerkzeugSeite

POSITIONEN = {
    "oben-links": "oben links",
    "oben": "oben Mitte",
    "oben-rechts": "oben rechts",
    "links": "Mitte links",
    "mitte": "Mitte",
    "rechts": "Mitte rechts",
    "unten-links": "unten links",
    "unten": "unten Mitte",
    "unten-rechts": "unten rechts",
    "gekachelt": "gekachelt (über das ganze Bild)",
}


def _zeile(*widgets) -> QWidget:
    zeile = QWidget()
    layout = QHBoxLayout(zeile)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget, 1 if isinstance(widget, QLineEdit | QSlider) else 0)
    return zeile


class WasserzeichenSeite(BildWerkzeugSeite):
    zusatz = "wasserzeichen"
    mit_vorschau = True
    start_text = "Anwenden"

    def optionen_aufbauen(self) -> None:
        f = self.formular
        self._logo_cache: tuple[str, object] | None = None
        self.art = QComboBox()
        self.art.addItem("Text", "text")
        self.art.addItem("Logo (Bild)", "logo")
        self.art.currentIndexChanged.connect(self._art_geaendert)
        f.addRow("Art:", self.art)
        self.text = QLineEdit()
        self.text.setPlaceholderText("z. B. © Miksan 2026")
        f.addRow("Text:", self.text)
        self.logo = QLineEdit()
        self.logo.setPlaceholderText("PNG mit Transparenz")
        waehlen = QPushButton(design.icon("bild", design.AKZENT), "Wählen …")
        waehlen.clicked.connect(self._logo_waehlen)
        self.logo_zeile = _zeile(self.logo, waehlen)
        f.addRow("Logo:", self.logo_zeile)
        self.position = QComboBox()
        for name, text in POSITIONEN.items():
            self.position.addItem(text, name)
        f.addRow("Position:", self.position)
        self.groesse = QSpinBox()
        self.groesse.setRange(1, 100)
        self.groesse.setSuffix(" % der Breite")
        f.addRow("Grösse:", self.groesse)
        self.deckkraft = QSlider(Qt.Orientation.Horizontal)
        self.deckkraft.setRange(0, 100)
        self.deckkraft_wert = QLabel()
        self.deckkraft.valueChanged.connect(lambda w: self.deckkraft_wert.setText(f"{w} %"))
        f.addRow("Deckkraft:", _zeile(self.deckkraft, self.deckkraft_wert))
        self._farbe = "#ffffff"
        self.knopf_farbe = QPushButton()
        self.knopf_farbe.clicked.connect(self._farbe_waehlen)
        self.farb_zeile = self.knopf_farbe
        f.addRow("Textfarbe:", self.knopf_farbe)

    def _art_geaendert(self, *_args) -> None:
        text = self.art.currentData() == "text"
        self.formular.setRowVisible(self.text, text)
        self.formular.setRowVisible(self.knopf_farbe, text)
        self.formular.setRowVisible(self.logo_zeile, not text)
        self.vorschau_aktualisieren()

    def _logo_waehlen(self) -> None:
        datei, _ = QFileDialog.getOpenFileName(
            self, "Logo wählen", "", f"Bilder ({self.dateien_muster()})"
        )
        if datei:
            self.logo.setText(datei)

    def farbe_setzen(self, farbe: str) -> None:
        self._farbe = QColor(farbe).name() if QColor(farbe).isValid() else "#ffffff"
        bild = QPixmap(32, 16)
        bild.fill(QColor(self._farbe))
        self.knopf_farbe.setIcon(QIcon(bild))
        self.knopf_farbe.setText(self._farbe)
        self.vorschau_aktualisieren()

    def _farbe_waehlen(self) -> None:
        farbe = QColorDialog.getColor(QColor(self._farbe), self, "Textfarbe")
        if farbe.isValid():
            self.farbe_setzen(farbe.name())

    # --- Einstellungen ----------------------------------------------------------------------

    def einstellungen_laden(self) -> None:
        super().einstellungen_laden()
        self.art.setCurrentIndex(max(0, self.art.findData(self.wert("art", "text"))))
        self.text.setText(self.wert("text", ""))
        self.logo.setText(self.wert("logo", ""))
        position = self.wert("position", wasserzeichen.STANDARD_POSITION)
        self.position.setCurrentIndex(max(0, self.position.findData(position)))
        self.groesse.setValue(self.wert("groesse", 20, int))
        self.deckkraft.setValue(self.wert("deckkraft", 50, int))
        self.deckkraft_wert.setText(f"{self.deckkraft.value()} %")
        self.farbe_setzen(self.wert("farbe", "#ffffff"))
        self._art_geaendert()

    def einstellungen_speichern(self) -> None:
        for schluessel, wert in (
            ("art", self.art.currentData()),
            ("text", self.text.text()),
            ("logo", self.logo.text()),
            ("position", self.position.currentData()),
            ("groesse", self.groesse.value()),
            ("deckkraft", self.deckkraft.value()),
            ("farbe", self._farbe),
        ):
            self.setzen(schluessel, wert)
        super().einstellungen_speichern()

    # --- Vorschau und Lauf ------------------------------------------------------------------

    def _optionen(self) -> dict:
        logo = None
        if self.art.currentData() == "logo":
            pfad = self.logo.text().strip()
            if not pfad:
                raise BedienFehler("Bitte ein Logo wählen.")
            if self._logo_cache is None or self._logo_cache[0] != pfad:
                self._logo_cache = (pfad, laden(Path(pfad)).frames[0])
            logo = self._logo_cache[1]
        return {
            "text": self.text.text() if logo is None else None,
            "logo": logo,
            "position": self.position.currentData(),
            "groesse": self.groesse.value(),
            "deckkraft": self.deckkraft.value(),
            "farbe": farbe_parsen(self._farbe),
        }

    def bild_funktion(self):
        optionen = self._optionen()
        if optionen["logo"] is None and not (optionen["text"] or "").strip():
            return None
        return lambda bild: wasserzeichen.anwenden(bild, **optionen)

    def arbeit_erstellen(self):
        optionen = self._optionen()
        logo_pfad = self.logo.text().strip() if optionen["logo"] is not None else None
        ueber = self.ueberschreiben()

        def arbeit(auftrag) -> list[str]:
            return wasserzeichen.wasserzeichen(
                auftrag.eingabe,
                auftrag.ausgabe,
                text=optionen["text"],
                logo=logo_pfad,
                position=optionen["position"],
                groesse=optionen["groesse"],
                deckkraft=optionen["deckkraft"],
                farbe=self._farbe,
                overwrite=ueber,
            ).hinweise

        return arbeit

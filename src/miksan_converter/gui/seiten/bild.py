"""Gemeinsame Felder der Bild-Werkzeuge (Zielformat, Bearbeiten, Hintergrundfarbe).

Die Arbeit selbst machen dieselben Funktionen wie in der Kommandozeile
(``logik.planen`` → ``stapel``/``convert``/``hintergrund``), hier wird nur eingesammelt.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from ...stapel import StapelErgebnis
from .. import logik
from ..arbeiter import plan_aufgabe
from .basis import WerkzeugSeite


class BildSeite(WerkzeugSeite):
    aktion = logik.UMWANDELN
    standard_format = "jpeg"
    wie_original = False

    # --- Bausteine für die Unterklassen ---------------------------------------------------

    def format_feld(self, formular) -> None:
        self.format_auswahl = QComboBox()
        self.format_auswahl.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.format_auswahl.setMinimumContentsLength(14)
        self.format_auswahl.currentIndexChanged.connect(self._format_geaendert)
        self.format_hinweis = self.hinweis_label()
        formular.addRow("Zielformat:", self.format_auswahl)
        formular.addRow("", self.format_hinweis)
        modell = self.format_auswahl.model()
        for eintrag in logik.formate_fuer_auswahl(wie_original=self.wie_original):
            text = eintrag.text if eintrag.verfuegbar else f"{eintrag.text} (nicht verfügbar)"
            self.format_auswahl.addItem(text, eintrag.name)
            zeile = self.format_auswahl.count() - 1
            self.format_auswahl.setItemData(zeile, eintrag.hinweis, Qt.ItemDataRole.ToolTipRole)
            if not eintrag.verfuegbar and isinstance(modell, QStandardItemModel):
                modell.item(zeile).setEnabled(False)

    def max_seite_feld(self, formular) -> None:
        self.max_seite = QSpinBox()
        self.max_seite.setRange(0, 100_000)
        self.max_seite.setSingleStep(100)
        self.max_seite.setSuffix(" px")
        self.max_seite.setSpecialValueText("unverändert")
        self.max_seite.setToolTip("Längste Seite höchstens so lang (verkleinert nur)")
        formular.addRow("Maximale Grösse:", self.max_seite)

    def qualitaet_feld(self, formular) -> None:
        self.qualitaet = QSpinBox()
        self.qualitaet.setRange(0, 100)
        self.qualitaet.setSpecialValueText("automatisch")
        self.qualitaet.setToolTip("Qualität 1–100 für JPEG, WebP, AVIF, HEIC")
        formular.addRow("Qualität:", self.qualitaet)

    def zielgroesse_feld(self, formular) -> None:
        self.zielgroesse = QLineEdit()
        self.zielgroesse.setPlaceholderText("z. B. 500KB oder 2MB")
        self.zielgroesse.setToolTip("Datei höchstens so gross (sucht die passende Qualität)")
        formular.addRow("Zielgrösse:", self.zielgroesse)

    def drehen_spiegeln_felder(self, formular) -> None:
        self.drehen = QComboBox()
        self.drehen.addItems(list(logik.DREHEN))
        formular.addRow("Drehen:", self.drehen)
        self.spiegeln = QComboBox()
        self.spiegeln.addItems(list(logik.SPIEGELN))
        formular.addRow("Spiegeln:", self.spiegeln)

    def metadaten_feld(self, formular) -> None:
        self.metadaten = QCheckBox("Metadaten entfernen (EXIF, GPS, XMP)")
        formular.addRow("", self.metadaten)

    def farbe_feld(self, formular) -> None:
        self._farbe = "#ffffff"
        self.knopf_farbe = QPushButton()
        self.knopf_farbe.setToolTip("Füllfarbe für Transparenz bei Formaten ohne Transparenz")
        self.knopf_farbe.clicked.connect(self._farbe_waehlen)
        formular.addRow("Hintergrundfarbe:", self.knopf_farbe)

    # --- Felder lesen und setzen --------------------------------------------------------

    def _format_geaendert(self, *_args) -> None:
        hinweis = self.format_auswahl.currentData(Qt.ItemDataRole.ToolTipRole) or ""
        self.format_hinweis.setText(hinweis)
        self.format_hinweis.setVisible(bool(hinweis))

    def format_waehlen(self, name: str) -> None:
        index = self.format_auswahl.findData(name)
        if (
            index >= 0
            and self.format_auswahl.model().flags(self.format_auswahl.model().index(index, 0))
            & Qt.ItemFlag.ItemIsEnabled
        ):
            self.format_auswahl.setCurrentIndex(index)

    def farbe_setzen(self, farbe: str) -> None:
        self._farbe = QColor(farbe).name() if QColor(farbe).isValid() else "#ffffff"
        bild = QPixmap(32, 16)
        bild.fill(QColor(self._farbe))
        self.knopf_farbe.setIcon(QIcon(bild))
        self.knopf_farbe.setText(self._farbe)

    def _farbe_waehlen(self) -> None:
        farbe = QColorDialog.getColor(QColor(self._farbe), self, "Hintergrundfarbe wählen")
        if farbe.isValid():
            self.farbe_setzen(farbe.name())

    def einstellungen(self) -> logik.Einstellungen:
        """Liest alle Felder dieser Seite (fehlende Felder bleiben beim Standard)."""
        e = logik.Einstellungen(
            aktion=self.aktion,
            ausgabe_ordner=self.ausgabe_ordner(),
            rekursiv=self.rekursiv(),
            ueberschreiben=self.ueberschreiben(),
        )
        if hasattr(self, "format_auswahl"):
            e.ziel_format = self.format_auswahl.currentData() or ""
        if hasattr(self, "max_seite"):
            e.max_seite = self.max_seite.value() or None
        if hasattr(self, "qualitaet"):
            e.qualitaet = self.qualitaet.value() or None
        if hasattr(self, "zielgroesse"):
            e.zielgroesse = self.zielgroesse.text()
        if hasattr(self, "drehen"):
            e.drehen = logik.DREHEN[self.drehen.currentText()]
            e.spiegeln = logik.SPIEGELN[self.spiegeln.currentText()]
        if hasattr(self, "metadaten"):
            e.metadaten_entfernen = self.metadaten.isChecked()
        if hasattr(self, "knopf_farbe"):
            e.hintergrundfarbe = self._farbe
        return e

    def einstellungen_laden(self) -> None:
        super().einstellungen_laden()
        alt = f"ziel_format/{self.aktion}"  # Schlüssel bis Version 0.2
        gewaehlt = self.wert("ziel_format", None)
        if gewaehlt is None and self.settings.contains(alt):
            gewaehlt = self.settings.value(alt, "", type=str)
        self.format_auswahl.setCurrentIndex(0)
        self.format_waehlen(self.standard_format)
        if gewaehlt is not None:
            self.format_waehlen(gewaehlt)
        self._format_geaendert()
        if hasattr(self, "max_seite"):
            self.max_seite.setValue(self.wert("max_seite", 0, int))
        if hasattr(self, "qualitaet"):
            self.qualitaet.setValue(self.wert("qualitaet", 0, int))
        if hasattr(self, "zielgroesse"):
            self.zielgroesse.setText(self.wert("zielgroesse", ""))
        if hasattr(self, "drehen"):
            self.drehen.setCurrentText(self.wert("drehen", "keine"))
            self.spiegeln.setCurrentText(self.wert("spiegeln", "keine"))
        if hasattr(self, "metadaten"):
            self.metadaten.setChecked(self.wert("metadaten_entfernen", False, bool))
        if hasattr(self, "knopf_farbe"):
            self.farbe_setzen(self.wert("hintergrundfarbe", "#ffffff"))

    def einstellungen_speichern(self) -> None:
        e = self.einstellungen()
        self.setzen("ziel_format", e.ziel_format)
        if hasattr(self, "max_seite"):
            self.setzen("max_seite", self.max_seite.value())
        if hasattr(self, "qualitaet"):
            self.setzen("qualitaet", self.qualitaet.value())
        if hasattr(self, "zielgroesse"):
            self.setzen("zielgroesse", e.zielgroesse)
        if hasattr(self, "drehen"):
            self.setzen("drehen", self.drehen.currentText())
            self.setzen("spiegeln", self.spiegeln.currentText())
        if hasattr(self, "metadaten"):
            self.setzen("metadaten_entfernen", e.metadaten_entfernen)
        if hasattr(self, "knopf_farbe"):
            self.setzen("hintergrundfarbe", e.hintergrundfarbe)
        super().einstellungen_speichern()

    # --- Lauf -----------------------------------------------------------------------------

    def vorbereiten(self):
        einstellungen = self.einstellungen()
        plan = logik.planen(self.pfade(), einstellungen)
        if not plan.auftraege:
            self.ergebnis_zeigen(StapelErgebnis(fehler=plan.fehler))
            if not plan.fehler:
                self.status.setText("Keine Bilddateien gefunden.")
            return None
        if not self.lauf_erlaubt(einstellungen):
            return None
        return plan_aufgabe(plan, einstellungen), self.start_meldung(plan)

    def lauf_erlaubt(self, einstellungen: logik.Einstellungen) -> bool:
        return True

    def start_meldung(self, plan: logik.Plan) -> str:
        return f"{len(plan.auftraege)} Dateien werden verarbeitet …"

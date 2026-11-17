"""Werkzeug „Hintergrund entfernen“ mit lokalem KI-Modell (Extra [ki])."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QMessageBox

from ...hintergrund import modell_ordner
from .. import logik
from .bild import BildSeite

MODELL_TEXTE = {
    "klein": "schnell, gut für einfache Motive",
    "genau": "genauer, etwas langsamer",
    "person": "für Personen und Porträts",
    "sehr-genau": "am genauesten, langsam und gross",
}


class HintergrundSeite(BildSeite):
    aktion = logik.HINTERGRUND
    standard_format = "png"
    start_text = "Freistellen"
    mit_vorschau = False  # Vorschau mit Maske folgt mit dem Ausbau des Werkzeugs

    def optionen_aufbauen(self) -> None:
        self.modell = QComboBox()
        self.modell.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.modell.setMinimumContentsLength(14)
        for name in logik.modelle_fuer_auswahl():
            self.modell.addItem(f"{name} – {MODELL_TEXTE.get(name, '')}".rstrip(" –"), name)
        self.formular.addRow("KI-Modell:", self.modell)
        self.format_feld(self.formular)
        self.farbe_feld(self.formular_erweitert)

    def einstellungen(self) -> logik.Einstellungen:
        e = super().einstellungen()
        e.modell = self.modell.currentData() or logik.STANDARD_MODELL
        return e

    def einstellungen_laden(self) -> None:
        super().einstellungen_laden()
        index = self.modell.findData(self.wert("modell", logik.STANDARD_MODELL))
        self.modell.setCurrentIndex(max(index, 0))

    def einstellungen_speichern(self) -> None:
        self.setzen("modell", self.modell.currentData())
        super().einstellungen_speichern()

    def lauf_erlaubt(self, einstellungen: logik.Einstellungen) -> bool:
        return self._modell_download_bestaetigen(einstellungen.modell)

    def start_meldung(self, plan: logik.Plan) -> str:
        return "KI-Modell wird geladen …"

    def _modell_download_bestaetigen(self, modell: str) -> bool:
        if logik.modell_vorhanden(modell):
            return True
        antwort = QMessageBox.question(
            self,
            "KI-Modell herunterladen",
            f"Das KI-Modell '{modell}' wird beim ersten Mal einmalig aus dem Internet geladen "
            f"(je nach Modell etwa 5 bis 200 MB) und in\n{modell_ordner()}\ngespeichert. "
            "Danach funktioniert das Entfernen des Hintergrunds ohne Internet.\n\nJetzt laden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return antwort == QMessageBox.StandardButton.Yes

"""Werkzeug „Verkleinern & Bearbeiten“: Grösse, Qualität, Drehen, Spiegeln, Metadaten."""

from __future__ import annotations

from .. import logik
from .bild import BildSeite


class BearbeitenSeite(BildSeite):
    aktion = logik.BEARBEITEN
    standard_format = logik.WIE_ORIGINAL
    wie_original = True
    start_text = "Bearbeiten"

    def optionen_aufbauen(self) -> None:
        self.max_seite_feld(self.formular)
        self.qualitaet_feld(self.formular)
        self.zielgroesse_feld(self.formular)
        self.drehen_spiegeln_felder(self.formular)
        self.metadaten_feld(self.formular)
        self.format_feld(self.formular_erweitert)
        self.farbe_feld(self.formular_erweitert)

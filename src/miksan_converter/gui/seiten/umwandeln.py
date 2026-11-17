"""Werkzeug „Umwandeln“: Bilder in ein anderes Format."""

from __future__ import annotations

from .. import logik
from .bild import BildSeite


class UmwandelnSeite(BildSeite):
    aktion = logik.UMWANDELN
    standard_format = "jpeg"
    start_text = "Umwandeln"

    def optionen_aufbauen(self) -> None:
        self.format_feld(self.formular)
        self.qualitaet_feld(self.formular)
        self.max_seite_feld(self.formular_erweitert)
        self.farbe_feld(self.formular_erweitert)
        self.metadaten_feld(self.formular_erweitert)

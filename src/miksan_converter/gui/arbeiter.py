"""Hintergrund-Thread: verarbeitet einen Plan, ohne das Fenster zu blockieren."""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from ..fehler import MiksanFehler
from ..stapel import Auftrag
from .logik import Einstellungen, Plan, plan_ausfuehren


class Arbeiter(QObject):
    """Läuft in einem eigenen ``QThread``; meldet sich nur über Signale beim Fenster."""

    fortschritt = Signal(int, int, str)  # fertig, gesamt, Dateiname
    fertig = Signal(object)  # StapelErgebnis
    fehlgeschlagen = Signal(str)

    def __init__(self, plan: Plan, einstellungen: Einstellungen):
        super().__init__()
        self.plan = plan
        self.einstellungen = einstellungen
        self.abbrechen = threading.Event()

    def _rueckmeldung(self, fertig: int, gesamt: int, auftrag: Auftrag) -> None:
        self.fortschritt.emit(fertig, gesamt, auftrag.eingabe.name)

    def starten(self) -> None:
        try:
            ergebnis = plan_ausfuehren(
                self.plan,
                self.einstellungen,
                rueckmeldung=self._rueckmeldung,
                abbrechen=self.abbrechen,
            )
        except MiksanFehler as fehler:
            self.fehlgeschlagen.emit(str(fehler))
        except Exception as fehler:  # nie den Thread mit einer Ausnahme beenden
            self.fehlgeschlagen.emit(f"Unerwarteter Fehler: {fehler}")
        else:
            self.fertig.emit(ergebnis)

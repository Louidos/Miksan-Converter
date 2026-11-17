"""Hintergrund-Thread: führt eine Aufgabe aus, ohne das Fenster zu blockieren."""

from __future__ import annotations

import threading
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from ..fehler import MiksanFehler
from ..stapel import Auftrag, StapelErgebnis
from .logik import Einstellungen, Plan, plan_ausfuehren

# Aufgabe(rueckmeldung, abbrechen) -> StapelErgebnis
Aufgabe = Callable[[Callable[[int, int, str], None], threading.Event], StapelErgebnis]


def plan_aufgabe(plan: Plan, einstellungen: Einstellungen) -> Aufgabe:
    """Aufgabe für die Bild-Werkzeuge: einen Plan mit den Kernfunktionen abarbeiten."""

    def aufgabe(rueckmeldung, abbrechen) -> StapelErgebnis:
        def melden(fertig: int, gesamt: int, auftrag: Auftrag) -> None:
            rueckmeldung(fertig, gesamt, auftrag.eingabe.name)

        return plan_ausfuehren(plan, einstellungen, rueckmeldung=melden, abbrechen=abbrechen)

    return aufgabe


class Arbeiter(QObject):
    """Läuft in einem eigenen ``QThread``; meldet sich nur über Signale beim Fenster."""

    fortschritt = Signal(int, int, str)  # fertig, gesamt, Dateiname (gesamt 0 = unbestimmt)
    fertig = Signal(object)  # StapelErgebnis
    fehlgeschlagen = Signal(str)

    def __init__(self, aufgabe: Aufgabe):
        super().__init__()
        self.aufgabe = aufgabe
        self.abbrechen = threading.Event()

    def _rueckmeldung(self, fertig: int, gesamt: int, name: str) -> None:
        self.fortschritt.emit(fertig, gesamt, name)

    def starten(self) -> None:
        try:
            ergebnis = self.aufgabe(self._rueckmeldung, self.abbrechen)
        except MiksanFehler as fehler:
            self.fehlgeschlagen.emit(str(fehler))
        except Exception as fehler:  # nie den Thread mit einer Ausnahme beenden
            self.fehlgeschlagen.emit(f"Unerwarteter Fehler: {fehler}")
        else:
            self.fertig.emit(ergebnis)

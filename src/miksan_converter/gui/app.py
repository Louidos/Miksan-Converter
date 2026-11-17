"""Start der Oberfläche: Design anwenden, Hauptfenster öffnen, Dateien aus den Argumenten."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from . import design
from .einzelfenster import Einzelinstanz, an_laufendes_senden, verbinden
from .fenster import TITEL, Hauptfenster

programm_icon = design.programm_icon

__all__ = ["TITEL", "Hauptfenster", "programm_icon", "starten"]


def starten(argv: list[str]) -> int:
    design.hohe_aufloesung_einrichten()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    vorhandene = [str(Path(pfad).resolve()) for pfad in argv if Path(pfad).exists()]
    # Nur ein Fenster: läuft schon eines, bekommt es die Dateien und kommt nach vorne
    if an_laufendes_senden(vorhandene):
        return 0
    instanz = Einzelinstanz()
    if not instanz.starten():
        # gleichzeitig gestartet (z. B. mehrere Dateien im Explorer): noch einmal versuchen
        if an_laufendes_senden(vorhandene):
            return 0
        instanz.aufraeumen_und_starten()
    design.anwenden(app)
    app.setApplicationName(TITEL)
    app.setOrganizationName("Miksan")
    app.setWindowIcon(programm_icon())
    fenster = Hauptfenster()
    verbinden(fenster, instanz, fenster.nach_vorne)
    if vorhandene:
        fenster.dateien_von_aussen(vorhandene)
    fenster.show()
    ergebnis = app.exec()
    instanz.schliessen()
    return ergebnis

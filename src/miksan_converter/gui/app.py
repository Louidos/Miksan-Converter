"""Start der Oberfläche: Design anwenden, Hauptfenster öffnen, Dateien aus den Argumenten."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from . import design
from .fenster import TITEL, Hauptfenster

programm_icon = design.programm_icon

__all__ = ["TITEL", "Hauptfenster", "programm_icon", "starten"]


def starten(argv: list[str]) -> int:
    design.hohe_aufloesung_einrichten()
    app = QApplication.instance() or QApplication(sys.argv[:1])
    design.anwenden(app)
    app.setApplicationName(TITEL)
    app.setOrganizationName("Miksan")
    app.setWindowIcon(programm_icon())
    fenster = Hauptfenster()
    vorhandene = [pfad for pfad in argv if Path(pfad).exists()]
    if vorhandene:
        fenster.pfade_hinzufuegen(vorhandene)
    fenster.show()
    return app.exec()

"""Basis der weiteren Bild-Werkzeuge: pro Bild eine Funktion aus ``miksan_converter.werkzeuge``.

Geplant und ausgeführt wird mit ``stapel`` (wie in der Kommandozeile): Dateien und Ordner
sammeln, Ziele bestimmen, parallel abarbeiten. Optional mit Vorschau.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSlider, QSpinBox

from ...stapel import Auftrag, Datei, StapelErgebnis, auftraege_planen, ausfuehren, dateien_sammeln
from .. import vorschaubild
from ..widgets.vorschau import VorschauBereich
from .basis import WerkzeugSeite


class BildWerkzeugSeite(WerkzeugSeite):
    zusatz = "bearbeitet"  # <name>-<zusatz> neben dem Original
    mit_vorschau = False
    vorschau: VorschauBereich | None = None

    # --- Vorschau -------------------------------------------------------------------------

    def aufbau_fertig(self) -> None:
        if not self.mit_vorschau:
            return
        self.vorschau = VorschauBereich()
        self.links.addWidget(self.vorschau)
        self.links.setStretchFactor(0, 2)
        self.links.setStretchFactor(1, 3)
        self.liste.currentItemChanged.connect(self.vorschau_aktualisieren)
        self.liste.geaendert.connect(self._erste_waehlen)
        signale = (
            (QComboBox, "currentIndexChanged"),
            (QSpinBox, "valueChanged"),
            (QLineEdit, "textChanged"),
            (QCheckBox, "toggled"),
            (QSlider, "valueChanged"),
        )
        for typ, signal in signale:
            for feld in self.optionen.findChildren(typ):
                getattr(feld, signal).connect(self.vorschau_aktualisieren)

    def _erste_waehlen(self) -> None:
        if self.liste.count() and self.liste.currentRow() < 0:
            self.liste.setCurrentRow(0)
        elif not self.liste.count():
            self.vorschau_aktualisieren()

    def vorschau_datei(self) -> str | None:
        pfad = self.liste.ausgewaehlter_pfad() or (self.pfade()[0] if self.pfade() else None)
        if pfad is None:
            return None
        try:
            dateien, _ = dateien_sammeln([pfad], rekursiv=self.rekursiv())
        except Exception:  # Ordner nicht lesbar o. ä.
            return None
        return str(dateien[0].pfad) if dateien else None

    def bild_funktion(self):
        """Unterklassen mit Vorschau: Funktion Bild -> Bild mit den aktuellen Feldern."""
        return None

    def vorschau_aktualisieren(self, *_args) -> None:
        if self.vorschau is None:
            return
        pfad = self.vorschau_datei()
        try:
            funktion = self.bild_funktion() if pfad else None
        except Exception as fehler:  # z. B. Logo fehlt: Hinweis statt Vorschau
            self.vorschau.anstossen(None)
            self.vorschau.info.setText(str(fehler))
            return
        if funktion is None:
            self.vorschau.anstossen(None)
            return
        self.vorschau.anstossen(lambda: vorschaubild.vorschau_mit_funktion(pfad, funktion))

    # --- Lauf -------------------------------------------------------------------------------

    def ziel_fuer(self) -> Callable[[Datei], Path]:
        """Ziel je Datei: im Ausgabeordner gleicher Name, sonst ``<name>-<zusatz>`` daneben."""
        ordner = self.ausgabe_ordner()
        zusatz = self.zusatz

        def ziel(datei: Datei) -> Path:
            if ordner is not None:
                return ordner / datei.relativ
            return datei.pfad.with_name(f"{datei.pfad.stem}-{zusatz}{datei.pfad.suffix}")

        return ziel

    def arbeit_erstellen(self) -> Callable[[Auftrag], list[str]]:
        raise NotImplementedError

    def vorbereiten(self):
        dateien, fehler = dateien_sammeln(self.pfade(), rekursiv=self.rekursiv())
        ordner = self.ausgabe_ordner()
        auftraege, planfehler = auftraege_planen(dateien, self.ziel_fuer(), ordner)
        fehler += planfehler
        if not auftraege:
            self.ergebnis_zeigen(StapelErgebnis(fehler=fehler))
            return None
        arbeit = self.arbeit_erstellen()

        def mit_ordner(auftrag: Auftrag) -> list[str]:
            auftrag.ausgabe.parent.mkdir(parents=True, exist_ok=True)
            return arbeit(auftrag)

        def aufgabe(rueckmeldung, abbrechen) -> StapelErgebnis:
            def melden(fertig, gesamt, auftrag):
                rueckmeldung(fertig, gesamt, auftrag.eingabe.name)

            ergebnis = ausfuehren(auftraege, mit_ordner, rueckmeldung=melden, abbrechen=abbrechen)
            ergebnis.fehler = fehler + ergebnis.fehler
            return ergebnis

        return aufgabe, f"{len(auftraege)} Dateien werden verarbeitet …"

    def schliessen(self) -> None:
        if self.vorschau is not None:
            self.vorschau.anstossen(None)
            self.vorschau.warten(5000)
        super().schliessen()

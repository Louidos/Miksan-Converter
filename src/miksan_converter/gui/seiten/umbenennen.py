"""Werkzeug „Stapel-Umbenennen“: Muster mit Platzhaltern, Vorschau alt → neu, Konflikte
werden vor dem Start gemeldet – es wird nie etwas überschrieben."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from ...fehler import MiksanFehler
from ...stapel import Auftrag, StapelErgebnis, dateien_sammeln
from ...werkzeuge import umbenennen
from .. import design
from .basis import WerkzeugSeite


class UmbenennenSeite(WerkzeugSeite):
    start_text = "Umbenennen"

    def optionen_aufbauen(self) -> None:
        f = self.formular
        self.muster = QLineEdit()
        self.muster.setPlaceholderText("z. B. urlaub-{datum}-{nr}")
        self.muster.textChanged.connect(self.neue_namen_zeigen)
        f.addRow("Muster:", self.muster)
        knoepfe = QWidget()
        zeile = QHBoxLayout(knoepfe)
        zeile.setContentsMargins(0, 0, 0, 0)
        for platzhalter in umbenennen.PLATZHALTER:
            knopf = design.eigenschaft(QPushButton(f"{{{platzhalter}}}"), "flach")
            knopf.setToolTip(f"{{{platzhalter}}} ins Muster einfügen")
            knopf.clicked.connect(lambda _=False, p=platzhalter: self.muster.insert(f"{{{p}}}"))
            zeile.addWidget(knopf)
        zeile.addStretch(1)
        f.addRow("", knoepfe)
        self.start = QSpinBox()
        self.start.setRange(0, 999_999)
        self.start.valueChanged.connect(self.neue_namen_zeigen)
        f.addRow("Erste Nummer:", self.start)
        self.konflikt = design.eigenschaft(self.hinweis_label(), "fehler")
        f.addRow("", self.konflikt)
        hinweis = self.hinweis_label()
        hinweis.setText(
            "{datum} = Aufnahmedatum (EXIF), sonst Änderungsdatum. Die Endung bleibt. "
            "Mit Ausgabeordner werden umbenannte Kopien angelegt, die Originale bleiben."
        )
        hinweis.setVisible(True)
        f.addRow("", hinweis)

    def aufbau_fertig(self) -> None:
        self.tabelle = QTreeWidget()
        self.tabelle.setHeaderLabels(["Alter Name", "Neuer Name"])
        self.tabelle.setRootIsDecorated(False)
        self.tabelle.setAlternatingRowColors(True)
        self.links.addWidget(self.tabelle)
        self.liste.geaendert.connect(self.neue_namen_zeigen)
        self.ablauf.ausgabe_ordner.textChanged.connect(self.neue_namen_zeigen)
        self.neue_namen_zeigen()

    def standard_ordner(self) -> str:
        return ""  # leer = an Ort und Stelle umbenennen (kein Standard-Ausgabeordner)

    def einstellungen_laden(self) -> None:
        super().einstellungen_laden()
        self.ablauf.ausgabe_ordner.setPlaceholderText("leer = umbenennen, sonst Kopien hierhin")
        self.muster.setText(self.wert("muster", "{name}-{nr}"))
        self.start.setValue(self.wert("start", 1, int))

    def einstellungen_speichern(self) -> None:
        self.setzen("muster", self.muster.text())
        self.setzen("start", self.start.value())
        super().einstellungen_speichern()

    def dateien(self) -> list[Path]:
        dateien, _ = dateien_sammeln(self.pfade(), rekursiv=self.rekursiv())
        return sorted((d.pfad for d in dateien), key=lambda p: (str(p.parent), p.name.lower()))

    def neue_namen_zeigen(self, *_args) -> list[str]:
        """Füllt die Tabelle alt → neu und gibt die Konflikte zurück (leer = startbereit)."""
        if not hasattr(self, "tabelle"):
            return []
        self.tabelle.clear()
        gruende: list[str] = []
        try:
            paare = umbenennen.neue_namen(
                self.dateien(),
                self.muster.text(),
                start=self.start.value(),
                ziel_ordner=self.ausgabe_ordner(),
            )
            gruende = umbenennen.konflikte(paare)
        except MiksanFehler as fehler:
            paare, gruende = [], [str(fehler)]
        for paar in paare:
            eintrag = QTreeWidgetItem([paar.alt.name, paar.neu.name])
            eintrag.setToolTip(0, str(paar.alt))
            eintrag.setToolTip(1, str(paar.neu))
            self.tabelle.addTopLevelItem(eintrag)
        self.tabelle.resizeColumnToContents(0)
        self.konflikt.setText("\n".join(gruende))
        self.konflikt.setVisible(bool(gruende))
        self._knoepfe_aktualisieren()
        return gruende

    def _knoepfe_aktualisieren(self) -> None:
        super()._knoepfe_aktualisieren()
        if hasattr(self, "konflikt") and self.konflikt.isVisibleTo(self):
            self.ablauf.knopf_start.setEnabled(False)

    def vorbereiten(self):
        gruende = self.neue_namen_zeigen()
        if gruende:
            self._melden(self.werkzeug.titel, "Nicht umbenannt:\n" + "\n".join(gruende))
            return None
        dateien, muster, start = self.dateien(), self.muster.text(), self.start.value()
        ordner = self.ausgabe_ordner()

        def aufgabe(rueckmeldung, abbrechen) -> StapelErgebnis:
            ergebnis = StapelErgebnis()
            try:
                paare = umbenennen.umbenennen(dateien, muster, start=start, ziel_ordner=ordner)
            except MiksanFehler as fehler:
                ergebnis.fehler.append((dateien[0] if dateien else Path("."), str(fehler)))
            else:
                ergebnis.ok.extend(Auftrag(p.alt, p.neu) for p in paare)
            rueckmeldung(len(dateien), len(dateien), "")
            return ergebnis

        return aufgabe, f"{len(dateien)} Dateien werden umbenannt …"

    def ergebnis_zeigen(self, ergebnis: StapelErgebnis) -> None:
        super().ergebnis_zeigen(ergebnis)
        if self.ausgabe_ordner() is None and ergebnis.ok:
            # Die Liste zeigt jetzt die neuen Namen
            neu = [str(auftrag.ausgabe) for auftrag in ergebnis.ok]
            self.pfade_setzen(neu)
            self.liste.status_setzen(StapelErgebnis(ok=[Auftrag(Path(p), Path(p)) for p in neu]))

"""Gemeinsamer Aufbau aller Werkzeug-Seiten.

Oben Titel, links Ablagefläche bzw. Dateiliste, rechts die Optionen nur dieses Werkzeugs
(seltene hinter „Erweitert“), unten fest die Ablaufleiste. Unterklassen bauen nur ihre
Optionen und liefern mit ``vorbereiten()`` die Aufgabe für den Hintergrund-Thread.
"""

from __future__ import annotations

import gc
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...fehler import MiksanFehler
from ...formats import bekannte_bild_endungen
from ...stapel import StapelErgebnis
from .. import design, logik
from ..arbeiter import Arbeiter, Aufgabe
from ..werkzeuge import Werkzeug
from ..widgets.ablage import Ablageflaeche
from ..widgets.ablauf import Ablaufleiste, Ausklapper
from ..widgets.dateiliste import DateiListe
from ..widgets.miniaturen import MiniaturLader


def kopf(titel: str, text: str, icon: str | None = None) -> QWidget:
    """Seitenkopf mit Icon, Titel und einem Satz Beschreibung."""
    bereich = QWidget()
    layout = QHBoxLayout(bereich)
    layout.setContentsMargins(design.abstand(3), design.abstand(3), design.abstand(3), 8)
    layout.setSpacing(design.abstand(1.5))
    if icon:
        symbol = QLabel()
        symbol.setPixmap(design.icon(icon, design.AKZENT).pixmap(32, 32))
        layout.addWidget(symbol, 0, Qt.AlignmentFlag.AlignTop)
    texte = QVBoxLayout()
    texte.setSpacing(2)
    texte.addWidget(design.eigenschaft(QLabel(titel), "titel"))
    unter = design.eigenschaft(QLabel(text), "hinweis")
    unter.setWordWrap(True)
    texte.addWidget(unter)
    layout.addLayout(texte, 1)
    return bereich


class WerkzeugSeite(QWidget):
    """Basis jeder Werkzeug-Seite."""

    lauf_geaendert = Signal(bool)  # läuft / läuft nicht (für Fenster und Taskleiste)
    dateien_filter = "Bilder ({muster});;Alle Dateien (*)"
    start_text = "Start"

    def __init__(self, werkzeug: Werkzeug, settings: QSettings, lader: MiniaturLader) -> None:
        super().__init__()
        self.werkzeug = werkzeug
        self.settings = settings
        self.lader = lader
        self.letztes_ergebnis: StapelErgebnis | None = None
        self._thread: QThread | None = None
        self._arbeiter: Arbeiter | None = None
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(kopf(werkzeug.titel, werkzeug.beschreibung, werkzeug.icon))

        self.teiler = QSplitter(Qt.Orientation.Horizontal)
        self.teiler.setChildrenCollapsible(False)
        self.teiler.setContentsMargins(design.abstand(3), 0, design.abstand(3), 0)
        self.links = QSplitter(Qt.Orientation.Vertical)
        self.links.setChildrenCollapsible(False)
        self.links.addWidget(self._dateien_bereich())
        self.teiler.addWidget(self.links)
        self.teiler.addWidget(self._optionen_rahmen())
        self.teiler.setStretchFactor(0, 3)
        self.teiler.setStretchFactor(1, 2)
        rand = QWidget()
        rand_layout = QVBoxLayout(rand)
        rand_layout.setContentsMargins(design.abstand(3), design.abstand(1), design.abstand(3), 16)
        rand_layout.addWidget(self.teiler)
        layout.addWidget(rand, 1)

        self.ablauf = Ablaufleiste(self.start_text)
        self.ablauf.knopf_start.clicked.connect(self.starten)
        self.ablauf.knopf_abbrechen.clicked.connect(self.abbrechen)
        layout.addWidget(self.ablauf)

        self.einstellungen_laden()
        self.aufbau_fertig()
        self._knoepfe_aktualisieren()

    # --- Aufbau ---------------------------------------------------------------------

    def _dateien_bereich(self) -> QWidget:
        self.dateien_stapel = QStackedWidget()
        self.ablage = Ablageflaeche(unten="oder mit den Knöpfen wählen")
        self.ablage.abgelegt.connect(self.pfade_hinzufuegen)
        self.ablage.dateien_waehlen.connect(self.dateien_waehlen)
        self.ablage.ordner_waehlen.connect(self.ordner_waehlen)
        self.dateien_stapel.addWidget(self.ablage)

        mit_liste = QWidget()
        liste_layout = QVBoxLayout(mit_liste)
        liste_layout.setContentsMargins(0, 0, 0, 0)
        liste_layout.setSpacing(design.abstand(1))
        self.liste = DateiListe(self.lader, self.werkzeug.passt)
        self.liste.abgelegt.connect(self.pfade_hinzufuegen)
        self.liste.geaendert.connect(self._liste_geaendert)
        self.liste.itemSelectionChanged.connect(self._knoepfe_aktualisieren)
        liste_layout.addWidget(self.liste, 1)
        knoepfe = QHBoxLayout()
        self.knopf_dateien = QPushButton(design.icon("hinzufuegen", design.AKZENT), "Dateien …")
        self.knopf_dateien.setToolTip("Dateien hinzufügen (Strg+O)")
        self.knopf_dateien.clicked.connect(self.dateien_waehlen)
        self.knopf_ordner = QPushButton(design.icon("ordner", design.AKZENT), "Ordner …")
        self.knopf_ordner.clicked.connect(self.ordner_waehlen)
        self.knopf_entfernen = QPushButton(design.icon("entfernen", design.AKZENT), "Entfernen")
        self.knopf_entfernen.setToolTip("Markierte entfernen (Entf)")
        self.knopf_entfernen.clicked.connect(self.auswahl_entfernen)
        self.knopf_leeren = QPushButton("Liste leeren")
        self.knopf_leeren.clicked.connect(self.liste.leeren)
        for knopf in (self.knopf_dateien, self.knopf_ordner):
            knoepfe.addWidget(knopf)
        knoepfe.addStretch(1)
        for knopf in (self.knopf_entfernen, self.knopf_leeren):
            knoepfe.addWidget(knopf)
        liste_layout.addLayout(knoepfe)
        self.dateien_stapel.addWidget(mit_liste)
        return self.dateien_stapel

    def _optionen_rahmen(self) -> QWidget:
        self.optionen = QWidget()
        layout = QVBoxLayout(self.optionen)
        layout.setContentsMargins(design.abstand(2), 0, design.abstand(1), 0)
        layout.setSpacing(design.abstand(2))
        layout.addWidget(design.eigenschaft(QLabel("Optionen"), "untertitel"))
        self.formular = QFormLayout()
        self.formular.setSpacing(design.abstand(1.5))
        self.formular.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addLayout(self.formular)
        erweitert_inhalt = QWidget()
        self.formular_erweitert = QFormLayout(erweitert_inhalt)
        self.formular_erweitert.setContentsMargins(0, 0, 0, 0)
        self.formular_erweitert.setSpacing(design.abstand(1.5))
        self.erweitert = Ausklapper("Erweitert", erweitert_inhalt)
        layout.addWidget(self.erweitert)
        self.optionen_aufbauen()
        self.erweitert.setVisible(self.formular_erweitert.rowCount() > 0)
        layout.addStretch(1)

        rollen = QScrollArea()
        rollen.setWidgetResizable(True)
        rollen.setFrameShape(QScrollArea.Shape.NoFrame)
        rollen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rollen.setWidget(self.optionen)
        rollen.setMinimumWidth(design.abstand(40))
        return rollen

    def optionen_aufbauen(self) -> None:
        """Unterklassen: Felder in ``self.formular`` bzw. ``self.formular_erweitert``."""

    def aufbau_fertig(self) -> None:
        """Unterklassen: nach Aufbau und Laden der Einstellungen (z. B. Vorschau einbauen)."""

    def hinweis_label(self) -> QLabel:
        label = design.eigenschaft(QLabel(), "hinweis")
        label.setWordWrap(True)
        label.setVisible(False)
        return label

    # --- Einstellungen (QSettings) ----------------------------------------------------

    def wert(self, schluessel: str, standard, typ=str):
        """Wert dieses Werkzeugs; fällt auf den alten, gemeinsamen Schlüssel zurück."""
        eigener = f"werkzeug/{self.werkzeug.name}/{schluessel}"
        for kandidat in (eigener, schluessel):
            if self.settings.contains(kandidat):
                return self.settings.value(kandidat, standard, type=typ)
        return standard

    def setzen(self, schluessel: str, wert) -> None:
        self.settings.setValue(f"werkzeug/{self.werkzeug.name}/{schluessel}", wert)

    def einstellungen_laden(self) -> None:
        """Unterklassen ergänzen; hier nur der Ausgabeordner der Seite."""
        self.ablauf.ausgabe_ordner.setText(
            self.settings.value(f"werkzeug/{self.werkzeug.name}/ausgabe_ordner", "", type=str)
        )
        self.ablauf.standard_setzen(self.standard_ordner())

    def einstellungen_speichern(self) -> None:
        self.setzen("ausgabe_ordner", self.ablauf.ausgabe_ordner.text().strip())
        self.settings.sync()

    def standard_ordner(self) -> str:
        return self.settings.value("ausgabe_ordner", "", type=str)

    def ausgabe_ordner(self) -> Path | None:
        return self.ablauf.ordner(self.standard_ordner())

    def rekursiv(self) -> bool:
        return self.settings.value("rekursiv", False, type=bool)

    def ueberschreiben(self) -> bool:
        return self.settings.value("ueberschreiben", False, type=bool)

    # --- Dateien --------------------------------------------------------------------

    def pfade(self) -> list[str]:
        return self.liste.pfade()

    def pfade_hinzufuegen(self, pfade) -> list[str]:
        if self.laeuft():
            return []
        neu, abgelehnt = self.liste.pfade_hinzufuegen(pfade)
        if abgelehnt:
            namen = ", ".join(Path(p).name for p in abgelehnt[:3])
            mehr = " …" if len(abgelehnt) > 3 else ""
            self.ablauf.status.setText(f"Passt nicht zu „{self.werkzeug.titel}“: {namen}{mehr}")
        return neu

    def pfade_setzen(self, pfade) -> None:
        self.liste.leeren()
        self.pfade_hinzufuegen(pfade)

    def dateien_muster(self) -> str:
        return " ".join(f"*{endung}" for endung in sorted(bekannte_bild_endungen()))

    def dateien_waehlen(self) -> None:
        dateien, _ = QFileDialog.getOpenFileNames(
            self,
            "Dateien hinzufügen",
            self.settings.value("letzter_ordner", "", type=str),
            self.dateien_filter.format(muster=self.dateien_muster()),
        )
        if dateien:
            self.settings.setValue("letzter_ordner", str(Path(dateien[0]).parent))
            self.pfade_hinzufuegen(dateien)

    def ordner_waehlen(self) -> None:
        ordner = QFileDialog.getExistingDirectory(
            self, "Ordner hinzufügen", self.settings.value("letzter_ordner", "", type=str)
        )
        if ordner:
            self.settings.setValue("letzter_ordner", ordner)
            self.pfade_hinzufuegen([ordner])

    def auswahl_entfernen(self) -> None:
        if not self.laeuft():
            self.liste.auswahl_entfernen()

    def _liste_geaendert(self) -> None:
        self.dateien_stapel.setCurrentIndex(1 if self.liste.count() else 0)
        self._knoepfe_aktualisieren()

    def dragEnterEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if event.mimeData().hasUrls() and not self.laeuft():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self.liste.dropEvent(event)

    # --- Ablauf ---------------------------------------------------------------------

    @property
    def status(self) -> QLabel:
        return self.ablauf.status

    @property
    def knopf_start(self) -> QPushButton:
        return self.ablauf.knopf_start

    def laeuft(self) -> bool:
        return self._thread is not None

    def _knoepfe_aktualisieren(self) -> None:
        laeuft = self.laeuft()
        hat_eintraege = self.liste.count() > 0
        self.ablauf.knopf_start.setEnabled(hat_eintraege and not laeuft)
        self.ablauf.knopf_abbrechen.setEnabled(laeuft)
        self.knopf_entfernen.setEnabled(bool(self.liste.selectedItems()) and not laeuft)
        self.knopf_leeren.setEnabled(hat_eintraege and not laeuft)
        for widget in (self.knopf_dateien, self.knopf_ordner, self.optionen, self.ablage):
            widget.setEnabled(not laeuft)
        self.ablauf.ausgabe_ordner.setEnabled(not laeuft)
        self.ablauf.knopf_ausgabe.setEnabled(not laeuft)
        self.liste.setAcceptDrops(not laeuft)

    def _melden(self, titel: str, text: str) -> None:
        QMessageBox.warning(self, titel, text)

    def vorbereiten(self) -> tuple[Aufgabe, str] | None:
        """Unterklassen: prüft die Eingaben und liefert (Aufgabe, Statustext) oder ``None``."""
        raise NotImplementedError

    def starten(self) -> None:
        if self.laeuft():
            return
        if not self.pfade():
            self._melden(self.werkzeug.titel, "Bitte zuerst Dateien oder Ordner hinzufügen.")
            return
        try:
            vorbereitet = self.vorbereiten()
        except MiksanFehler as fehler:
            self._melden("Einstellungen prüfen", str(fehler))
            return
        if vorbereitet is None:
            return
        aufgabe, text = vorbereitet
        self.einstellungen_speichern()
        self.letztes_ergebnis = None
        self.liste.status_zuruecksetzen()
        self.ablauf.meldungen_setzen([])
        self.ablauf.oeffnen_setzen(None)
        self.ablauf.fortschritt.setRange(0, 0)  # unbestimmt, bis die erste Datei fertig ist
        self.ablauf.status.setText(text)

        # Alte Qt-Objekte jetzt im Fenster-Thread aufräumen: räumt die Garbage Collection sie
        # später in einem Arbeits-Thread weg, stürzt Qt (vor allem unter Windows) ab.
        gc.collect()
        self._thread = QThread(self)
        self._arbeiter = Arbeiter(aufgabe)
        self._arbeiter.moveToThread(self._thread)
        self._thread.started.connect(self._arbeiter.starten)
        self._arbeiter.fortschritt.connect(self._fortschritt)
        self._arbeiter.fertig.connect(self._fertig)
        self._arbeiter.fehlgeschlagen.connect(self._fehlgeschlagen)
        self._thread.start()
        self._knoepfe_aktualisieren()
        self.lauf_geaendert.emit(True)

    def abbrechen(self) -> None:
        if self._arbeiter is not None and not self._arbeiter.abbrechen.is_set():
            self._arbeiter.abbrechen.set()
            self.ablauf.knopf_abbrechen.setEnabled(False)
            self.ablauf.status.setText("Wird abgebrochen – laufende Dateien werden noch fertig …")

    def _fortschritt(self, fertig: int, gesamt: int, name: str) -> None:
        self.ablauf.fortschritt.setRange(0, gesamt)
        self.ablauf.fortschritt.setValue(fertig)
        if self._arbeiter is not None and not self._arbeiter.abbrechen.is_set():
            self.ablauf.status.setText(f"{fertig} von {gesamt}: {name}" if gesamt else name)

    def _lauf_beenden(self) -> None:
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread.deleteLater()
        if self._arbeiter is not None:
            self._arbeiter.deleteLater()
        self._thread = None
        self._arbeiter = None
        self._knoepfe_aktualisieren()
        self.lauf_geaendert.emit(False)

    def _fertig(self, ergebnis: StapelErgebnis) -> None:
        self._lauf_beenden()
        self.ergebnis_zeigen(ergebnis)

    def _fehlgeschlagen(self, meldung: str) -> None:
        self._lauf_beenden()
        self.ablauf.fortschritt.setRange(0, 1)
        self.ablauf.fortschritt.setValue(0)
        self.ablauf.status.setText("Fehlgeschlagen.")
        self._melden(self.werkzeug.titel, meldung)

    def ausgabe_ordner_von(self, ergebnis: StapelErgebnis) -> Path | None:
        ordner = self.ausgabe_ordner()
        if ordner is not None:
            return ordner
        return ergebnis.ok[0].ausgabe.parent if ergebnis.ok else None

    def ergebnis_zeigen(self, ergebnis: StapelErgebnis) -> None:
        self.letztes_ergebnis = ergebnis
        gesamt = len(ergebnis.ok) + len(ergebnis.fehler) + len(ergebnis.uebersprungen)
        self.ablauf.fortschritt.setRange(0, max(gesamt, 1))
        self.ablauf.fortschritt.setValue(gesamt)
        self.ablauf.status.setText(f"Fertig: {logik.zusammenfassung(ergebnis)}")
        self.ablauf.meldungen_setzen(logik.meldungen(ergebnis))
        self.liste.status_setzen(ergebnis)
        self.ablauf.oeffnen_setzen(self.ausgabe_ordner_von(ergebnis))

    def schliessen(self) -> None:
        """Beim Schliessen des Fensters: laufende Arbeit beenden, Einstellungen sichern."""
        if self._arbeiter is not None:
            self._arbeiter.abbrechen.set()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        self.einstellungen_speichern()

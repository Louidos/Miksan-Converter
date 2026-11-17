"""Hauptfenster: Seitenleiste links, Seiten rechts (Start, Werkzeuge, Einstellungen, Info)."""

from __future__ import annotations

import importlib
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, medien
from . import design
from .seiten.basis import WerkzeugSeite
from .seiten.einstellungen import EinstellungenSeite, InfoSeite, NichtVerfuegbarSeite
from .seiten.start import StartSeite
from .werkzeuge import EINSTELLUNGEN, INFO, START, WERKZEUGE, nach_bereich, werkzeug
from .widgets import abgelegte_pfade
from .widgets.miniaturen import MiniaturLader

TITEL = "Miksan-Converter"
MINDESTGROESSE = QSize(900, 600)
_SEITE = Qt.ItemDataRole.UserRole


def _seitenleiste() -> QListWidget:
    liste = QListWidget()
    design.eigenschaft(liste, "seitenleiste")
    liste.setIconSize(QSize(design.ICON, design.ICON))
    liste.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    liste.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    return liste


def _eintrag(liste: QListWidget, name: str, text: str, icon: str, hinweis: str = "") -> None:
    eintrag = QListWidgetItem(design.icon(icon, design.TEXT_AUS if hinweis else design.TEXT), text)
    eintrag.setData(_SEITE, name)
    if hinweis:
        eintrag.setToolTip(hinweis)
        eintrag.setForeground(QBrush(QColor(design.TEXT_AUS)))
    liste.addItem(eintrag)


def _bereich(liste: QListWidget, text: str) -> None:
    eintrag = QListWidgetItem(text.upper())
    eintrag.setFlags(Qt.ItemFlag.NoItemFlags)
    schrift = eintrag.font()
    schrift.setPointSizeF(schrift.pointSizeF() * 0.85)
    schrift.setBold(True)
    eintrag.setFont(schrift)
    eintrag.setForeground(QBrush(QColor(design.NEBENTEXT)))
    eintrag.setSizeHint(QSize(0, design.abstand(4)))
    liste.addItem(eintrag)


class Hauptfenster(QMainWindow):
    def __init__(self, einstellungen: QSettings | None = None) -> None:
        super().__init__()
        self.settings = einstellungen or QSettings("Miksan", "Miksan-Converter")
        medien.pfad_setzen(self.settings.value("ffmpeg_pfad", "", type=str))
        self.lader = MiniaturLader(self)
        self.seiten: dict[str, QWidget] = {}
        self._aktuell = START
        self._leiste = None  # Taskleisten-Fortschritt, erst bei Bedarf

        self.setWindowTitle(f"{TITEL} {__version__}")
        self.setWindowIcon(design.programm_icon())
        self.setAcceptDrops(True)
        self.setMinimumSize(MINDESTGROESSE)
        self.resize(1120, 760)

        leiste = QFrame()
        design.eigenschaft(leiste, "seitenleiste")
        leiste.setFixedWidth(design.SEITENLEISTE_BREITE)
        leiste_layout = QVBoxLayout(leiste)
        leiste_layout.setContentsMargins(0, 0, 0, 0)
        leiste_layout.setSpacing(0)
        self.navigation = _seitenleiste()
        _eintrag(self.navigation, START, "Start", "start")
        for bereich, eintraege in nach_bereich():
            _bereich(self.navigation, bereich)
            for w in eintraege:
                _eintrag(self.navigation, w.name, w.titel, w.icon, w.hinweis())
        self.navigation_unten = _seitenleiste()
        _eintrag(self.navigation_unten, EINSTELLUNGEN, "Einstellungen", "einstellungen")
        _eintrag(self.navigation_unten, INFO, "Info", "info")
        self.navigation_unten.setFixedHeight(design.abstand(12))
        leiste_layout.addWidget(self.navigation, 1)
        leiste_layout.addWidget(self.navigation_unten)
        for liste in (self.navigation, self.navigation_unten):
            liste.currentItemChanged.connect(self._navigation_gewaehlt)

        self.stapel = QStackedWidget()
        self.startseite = StartSeite(self.settings)
        self.startseite.werkzeug_gewaehlt.connect(self.werkzeug_oeffnen)
        self._hinzufuegen(START, self.startseite)

        zentral = QWidget()
        layout = QHBoxLayout(zentral)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(leiste)
        layout.addWidget(self.stapel, 1)
        self.setCentralWidget(zentral)

        self._tastenkuerzel()
        self.seite_zeigen(START)

    # --- Seiten ---------------------------------------------------------------------

    def _hinzufuegen(self, name: str, seite: QWidget) -> QWidget:
        self.seiten[name] = seite
        self.stapel.addWidget(seite)
        return seite

    def seite(self, name: str) -> QWidget:
        """Gibt die Seite zurück und erzeugt sie beim ersten Gebrauch (schneller Start)."""
        if name in self.seiten:
            return self.seiten[name]
        if name == EINSTELLUNGEN:
            return self._hinzufuegen(name, EinstellungenSeite(self.settings))
        if name == INFO:
            return self._hinzufuegen(name, InfoSeite())
        eintrag = werkzeug(name)
        if not eintrag.verfuegbar():
            return self._hinzufuegen(name, NichtVerfuegbarSeite(eintrag))
        modul_name, klasse = eintrag.seite.split(":")
        modul = importlib.import_module(f".seiten.{modul_name}", __package__)
        seite = getattr(modul, klasse)(eintrag, self.settings, self.lader)
        seite.lauf_geaendert.connect(self._lauf_geaendert)
        seite.ablauf.fortschritt.valueChanged.connect(lambda _w, s=seite: self._taskleiste(s))
        return self._hinzufuegen(name, seite)

    def aktuelle_seite(self) -> QWidget:
        return self.seiten[self._aktuell]

    def seite_zeigen(self, name: str) -> QWidget:
        vorher = self.seiten.get(self._aktuell)
        seite = self.seite(name)
        if isinstance(vorher, WerkzeugSeite) and isinstance(seite, WerkzeugSeite):
            self._dateien_uebernehmen(vorher, seite)
        self._aktuell = name
        self.stapel.setCurrentWidget(seite)
        for liste in (self.navigation, self.navigation_unten):
            liste.blockSignals(True)
            liste.setCurrentRow(-1)
            for i in range(liste.count()):
                if liste.item(i).data(_SEITE) == name:
                    liste.setCurrentRow(i)
            liste.blockSignals(False)
        return seite

    def werkzeug_oeffnen(self, name: str, pfade: list | None = None) -> QWidget:
        seite = self.seite_zeigen(name)
        if pfade and isinstance(seite, WerkzeugSeite):
            seite.pfade_hinzufuegen(pfade)
        return seite

    def _dateien_uebernehmen(self, von: WerkzeugSeite, nach: WerkzeugSeite) -> None:
        """Die Dateiliste bleibt beim Werkzeugwechsel, soweit die Dateien passen."""
        if von is nach or nach.laeuft():
            return
        passende = [pfad for pfad in von.pfade() if nach.werkzeug.passt(pfad)]
        if passende and passende != nach.pfade():
            nach.pfade_setzen(passende)

    def _navigation_gewaehlt(self, eintrag, _vorher=None) -> None:
        if eintrag is not None and eintrag.data(_SEITE):
            self.seite_zeigen(eintrag.data(_SEITE))

    # --- Dateien und Tastenkürzel ---------------------------------------------------

    def dateien_von_aussen(self, pfade) -> None:
        """Dateien aus dem Explorer-Rechtsklick oder einem zweiten Start: auf der Startseite
        die passenden Werkzeuge anbieten."""
        vorhandene = [str(Path(p)) for p in pfade if Path(p).exists()]
        if not vorhandene:
            return
        self.seite_zeigen(START)
        self.startseite.dateien_ablegen(vorhandene)

    def nach_vorne(self) -> None:
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        QApplication.alert(self)

    def pfade_hinzufuegen(self, pfade) -> None:
        """Dateien an die aktuelle Seite geben (Startseite: passende Werkzeuge anbieten)."""
        seite = self.aktuelle_seite()
        if not hasattr(seite, "pfade_hinzufuegen"):
            seite = self.seite_zeigen(START)
        seite.pfade_hinzufuegen([str(Path(p)) for p in pfade])

    def _tastenkuerzel(self) -> None:
        def kuerzel(taste, methode: str) -> None:
            QShortcut(QKeySequence(taste), self, lambda: self._an_seite(methode))

        kuerzel(QKeySequence.StandardKey.Open, "dateien_waehlen")
        kuerzel(Qt.Key.Key_Delete, "auswahl_entfernen")
        kuerzel("Ctrl+Return", "starten")
        kuerzel("Ctrl+Enter", "starten")
        kuerzel(Qt.Key.Key_Escape, "abbrechen")

    def _an_seite(self, methode: str) -> None:
        funktion = getattr(self.aktuelle_seite(), methode, None)
        if funktion is not None:
            funktion()

    def dragEnterEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self.dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        pfade = abgelegte_pfade(event)
        if pfade:
            event.acceptProposedAction()
            self.pfade_hinzufuegen(pfade)

    # --- Lauf -----------------------------------------------------------------------

    def laeuft(self) -> bool:
        return any(isinstance(s, WerkzeugSeite) and s.laeuft() for s in self.seiten.values())

    def _lauf_geaendert(self, laeuft: bool) -> None:
        """Fortschritt in der Taskleiste ein-/ausschalten; nach dem Lauf das Symbol blinken."""
        if not laeuft:
            if not self.laeuft():
                self._taskleiste_setzen(None)
            if not self.isActiveWindow():
                QApplication.alert(self)

    def _taskleiste(self, seite: WerkzeugSeite) -> None:
        if seite.laeuft():
            balken = seite.ablauf.fortschritt
            self._taskleiste_setzen((balken.value() - balken.minimum(), balken.maximum()))

    def _taskleiste_setzen(self, wert: tuple[int, int] | None) -> None:
        if self._leiste is None:
            from .taskleiste import Taskleiste

            self._leiste = Taskleiste()
        if not self._leiste.aktiv:
            return
        from . import taskleiste

        fenster = int(self.winId())
        if wert is None:
            self._leiste.zustand(fenster, taskleiste.KEIN)
        elif wert[1] <= 0:
            self._leiste.zustand(fenster, taskleiste.UNBESTIMMT)
        else:
            self._leiste.zustand(fenster, taskleiste.NORMAL)
            self._leiste.wert(fenster, wert[0], wert[1])

    def closeEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        for seite in self.seiten.values():
            if isinstance(seite, WerkzeugSeite):
                seite.schliessen()
        self.settings.setValue("seite", self._aktuell)
        self.lader.warten(3000)
        super().closeEvent(event)


def alle_werkzeuge() -> list[str]:
    return [w.name for w in WERKZEUGE]

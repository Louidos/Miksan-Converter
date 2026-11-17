"""Werkzeug „Zuschneiden“: Ausschnitt mit der Maus, feste Verhältnisse und Zielmasse."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QComboBox, QPushButton

from ...stapel import Auftrag
from ...werkzeuge import zuschneiden
from .. import dateiinfo
from ..widgets.miniaturen import qimage_aus_pil
from ..widgets.zuschnitt import ZuschnittAnsicht
from .bildwerkzeug import BildWerkzeugSeite

ANZEIGE = 1200  # Kantenlänge des Bildes für die Auswahl


class _Bote(QObject):
    fertig = Signal(str, object)


class _Laden(QRunnable):
    def __init__(self, pfad: str, bote: _Bote) -> None:
        super().__init__()
        self.pfad, self.bote = pfad, bote

    def run(self) -> None:
        bild = dateiinfo.miniatur(self.pfad, ANZEIGE)
        self.bote.fertig.emit(self.pfad, qimage_aus_pil(bild) if bild is not None else None)


class ZuschneidenSeite(BildWerkzeugSeite):
    zusatz = "zugeschnitten"
    start_text = "Zuschneiden"

    def optionen_aufbauen(self) -> None:
        f = self.formular
        self.verhaeltnis = QComboBox()
        for name in zuschneiden.VERHAELTNISSE:
            self.verhaeltnis.addItem(name, name)
        self.verhaeltnis.currentIndexChanged.connect(self._verhaeltnis_geaendert)
        f.addRow("Seitenverhältnis:", self.verhaeltnis)
        self.vorlage = QComboBox()
        self.vorlage.addItem("keine (Grösse bleibt)", "")
        for name, (text, _) in zuschneiden.VORLAGEN.items():
            self.vorlage.addItem(text, name)
        self.vorlage.currentIndexChanged.connect(self._vorlage_geaendert)
        f.addRow("Zielmasse:", self.vorlage)
        self.knopf_mittig = QPushButton("Ausschnitt mittig")
        self.knopf_mittig.clicked.connect(self.mittig)
        f.addRow("", self.knopf_mittig)
        hinweis = self.hinweis_label()
        hinweis.setText(
            "Im Bild links ein Rechteck aufziehen oder den Ausschnitt verschieben. "
            "Jedes Bild der Liste merkt sich seinen eigenen Ausschnitt."
        )
        hinweis.setVisible(True)
        f.addRow("", hinweis)

    def aufbau_fertig(self) -> None:
        self.ausschnitte: dict[str, tuple] = {}
        self.ansicht = ZuschnittAnsicht()
        self.links.addWidget(self.ansicht)
        self.links.setStretchFactor(0, 1)
        self.links.setStretchFactor(1, 3)
        self.ansicht.geaendert.connect(self._ausschnitt_merken)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._bote = _Bote()
        self._bote.fertig.connect(self._bild_geladen)
        self.liste.currentItemChanged.connect(self._bild_zeigen)
        self.liste.geaendert.connect(self._erste_waehlen)
        self._verhaeltnis_geaendert()

    def _erste_waehlen(self) -> None:
        if self.liste.count() and self.liste.currentRow() < 0:
            self.liste.setCurrentRow(0)

    def _bild_zeigen(self, *_args) -> None:
        pfad = self.vorschau_datei()
        if pfad is None:
            self.ansicht.bild_setzen(None)
            return
        self._pool.start(_Laden(pfad, self._bote))

    def _bild_geladen(self, pfad: str, bild) -> None:
        if pfad != self.vorschau_datei():
            return
        self.ansicht.pfad = pfad
        pixmap = QPixmap.fromImage(bild) if bild is not None else None
        self.ansicht.bild_setzen(pixmap, self.ausschnitte.get(pfad))

    def _ausschnitt_merken(self, relativ: tuple) -> None:
        pfad = getattr(self.ansicht, "pfad", None)
        if pfad:
            self.ausschnitte[pfad] = relativ

    def aktuelles_verhaeltnis(self) -> tuple[int, int] | None:
        vorlage = self.vorlage.currentData()
        if vorlage:
            return zuschneiden.VORLAGEN[vorlage][1]
        return zuschneiden.verhaeltnis_parsen(self.verhaeltnis.currentData())

    def _verhaeltnis_geaendert(self, *_args) -> None:
        if not hasattr(self, "ansicht"):
            return
        self.ausschnitte.clear()  # alte Ausschnitte passen nicht mehr zum Verhältnis
        self.ansicht.verhaeltnis_setzen(self.aktuelles_verhaeltnis())

    def _vorlage_geaendert(self, *_args) -> None:
        self.verhaeltnis.setEnabled(not self.vorlage.currentData())
        self._verhaeltnis_geaendert()

    def mittig(self) -> None:
        self.ausschnitte.clear()
        self.ansicht.verhaeltnis_setzen(self.aktuelles_verhaeltnis())

    def einstellungen_laden(self) -> None:
        super().einstellungen_laden()
        self.verhaeltnis.setCurrentIndex(
            max(0, self.verhaeltnis.findData(self.wert("verhaeltnis", "frei")))
        )
        self.vorlage.setCurrentIndex(max(0, self.vorlage.findData(self.wert("vorlage", ""))))

    def einstellungen_speichern(self) -> None:
        self.setzen("verhaeltnis", self.verhaeltnis.currentData())
        self.setzen("vorlage", self.vorlage.currentData())
        super().einstellungen_speichern()

    def arbeit_erstellen(self):
        verhaeltnis = self.aktuelles_verhaeltnis()
        vorlage = self.vorlage.currentData()
        ziel = zuschneiden.VORLAGEN[vorlage][1] if vorlage else None
        ausschnitte, ueber = dict(self.ausschnitte), self.ueberschreiben()

        def arbeit(auftrag: Auftrag) -> list[str]:
            return zuschneiden.zuschneiden(
                auftrag.eingabe,
                auftrag.ausgabe,
                relativ=ausschnitte.get(str(auftrag.eingabe)),
                verhaeltnis=verhaeltnis,
                ziel=ziel,
                overwrite=ueber,
            ).hinweise

        return arbeit

    def schliessen(self) -> None:
        self._pool.waitForDone(5000)
        super().schliessen()

"""Werkzeug „Hintergrund entfernen“ (Extra [ki]): Modell, neuer Hintergrund, weiche Kante.

Die Maske wird für die Vorschau einmal pro Datei und Modell gerechnet und zwischengespeichert;
ein Wechsel des Hintergrunds ist deshalb sofort sichtbar. Modelle werden nur über den Knopf
„Herunterladen“ geladen (mit Fortschritt), nie ungefragt mitten im Lauf.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QWidget,
)

from ...hintergrund import (
    BILD,
    FARBE,
    MODELL_INFOS,
    TRANSPARENT,
    WEICH,
    modell_herunterladen,
)
from .. import design, logik, vorschaubild
from .bild import BildSeite

NEUE_HINTERGRUENDE = {
    TRANSPARENT: "Transparent",
    FARBE: "Farbe",
    BILD: "Eigenes Bild",
    WEICH: "Weichgezeichnetes Original",
}
SCHNELLFARBEN = (("Weiss", "#ffffff"), ("Schwarz", "#000000"), ("Blau", design.AKZENT))


def modell_text(name: str) -> str:
    info = MODELL_INFOS.get(name)
    if info is None:
        return name
    return f"{info.titel} – {info.text} ({info.groesse_mb} MB)"


class _Bote(QObject):
    fortschritt = Signal(int, int)
    fertig = Signal(str)  # Fehlertext, leer = ok


class _Download(QRunnable):
    def __init__(self, modell: str, bote: _Bote, abbrechen: threading.Event) -> None:
        super().__init__()
        self.modell, self.bote, self.abbrechen = modell, bote, abbrechen

    def run(self) -> None:
        try:
            modell_herunterladen(self.modell, self.bote.fortschritt.emit, self.abbrechen)
        except Exception as fehler:  # Meldung im Fenster statt Absturz
            self.bote.fertig.emit(str(fehler))
        else:
            self.bote.fertig.emit("")


def _zeile(*widgets) -> QWidget:
    zeile = QWidget()
    layout = QHBoxLayout(zeile)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(design.abstand(1))
    for widget in widgets:
        layout.addWidget(widget, 1 if isinstance(widget, QLineEdit | QSlider) else 0)
    return zeile


class HintergrundSeite(BildSeite):
    aktion = logik.HINTERGRUND
    standard_format = "png"
    start_text = "Freistellen"

    def optionen_aufbauen(self) -> None:
        self.speicher = vorschaubild.MaskenSpeicher()
        self._download_abbrechen = threading.Event()
        self._pool = QThreadPool(self)
        self._bote = _Bote()
        self._bote.fortschritt.connect(self._download_fortschritt)
        self._bote.fertig.connect(self._download_fertig)
        f = self.formular

        self.modell = QComboBox()
        self.modell.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.modell.setMinimumContentsLength(14)
        for name in logik.modelle_fuer_auswahl():
            self.modell.addItem(modell_text(name), name)
        self.modell.currentIndexChanged.connect(self._modell_geaendert)
        f.addRow("KI-Modell:", self.modell)
        self.modell_status = design.eigenschaft(QLabel(), "hinweis")
        self.knopf_laden = QPushButton(design.icon("herunterladen", design.AKZENT), "Herunterladen")
        self.knopf_laden.clicked.connect(self.modell_laden)
        self.laden_balken = QProgressBar()
        self.laden_balken.setVisible(False)
        f.addRow("", _zeile(self.modell_status, self.knopf_laden))
        f.addRow("", self.laden_balken)

        self.neuer_hintergrund = QComboBox()
        for name, text in NEUE_HINTERGRUENDE.items():
            self.neuer_hintergrund.addItem(text, name)
        self.neuer_hintergrund.currentIndexChanged.connect(self._art_geaendert)
        f.addRow("Neuer Hintergrund:", self.neuer_hintergrund)

        self._ersatz_farbe = "#ffffff"
        self.knopf_ersatz_farbe = QPushButton()
        self.knopf_ersatz_farbe.clicked.connect(self._ersatz_farbe_waehlen)
        schnell = []
        for text, farbe in SCHNELLFARBEN:
            knopf = design.eigenschaft(QPushButton(text), "flach")
            knopf.clicked.connect(lambda _=False, f=farbe: self.ersatz_farbe_setzen(f))
            schnell.append(knopf)
        self.farb_zeile = _zeile(self.knopf_ersatz_farbe, *schnell)
        f.addRow("Farbe:", self.farb_zeile)

        self.ersatz_bild = QLineEdit()
        self.ersatz_bild.setPlaceholderText("Bild für den Hintergrund")
        waehlen = QPushButton(design.icon("bild", design.AKZENT), "Wählen …")
        waehlen.clicked.connect(self._ersatz_bild_waehlen)
        self.bild_zeile = _zeile(self.ersatz_bild, waehlen)
        f.addRow("Bild:", self.bild_zeile)

        self.unschaerfe = QSpinBox()
        self.unschaerfe.setRange(1, 100)
        self.unschaerfe.setToolTip("Wie stark das Original weichgezeichnet wird")
        f.addRow("Stärke:", self.unschaerfe)

        self.kante = QSlider(Qt.Orientation.Horizontal)
        self.kante.setRange(0, 10)
        self.kante.setPageStep(1)
        self.kante_wert = QLabel("0 px")
        self.kante.valueChanged.connect(lambda wert: self.kante_wert.setText(f"{wert} px"))
        self.kante.valueChanged.connect(self.vorschau_aktualisieren)
        f.addRow("Kante weicher:", _zeile(self.kante, self.kante_wert))

        self.format_feld(self.formular)
        self.farbe_feld(self.formular_erweitert)

    # --- Felder ---------------------------------------------------------------------------

    def _art_geaendert(self, *_args) -> None:
        art = self.neuer_hintergrund.currentData()
        for widget, sichtbar in (
            (self.farb_zeile, art == FARBE),
            (self.bild_zeile, art == BILD),
            (self.unschaerfe, art == WEICH),
        ):
            self.formular.setRowVisible(widget, sichtbar)

    def ersatz_farbe_setzen(self, farbe: str) -> None:
        self._ersatz_farbe = QColor(farbe).name() if QColor(farbe).isValid() else "#ffffff"
        bild = QPixmap(32, 16)
        bild.fill(QColor(self._ersatz_farbe))
        self.knopf_ersatz_farbe.setIcon(QIcon(bild))
        self.knopf_ersatz_farbe.setText(self._ersatz_farbe)
        self.vorschau_aktualisieren()

    def _ersatz_farbe_waehlen(self) -> None:
        farbe = QColorDialog.getColor(QColor(self._ersatz_farbe), self, "Neuer Hintergrund")
        if farbe.isValid():
            self.ersatz_farbe_setzen(farbe.name())

    def _ersatz_bild_waehlen(self) -> None:
        datei, _ = QFileDialog.getOpenFileName(
            self,
            "Bild für den Hintergrund",
            self.settings.value("letzter_ordner", "", type=str),
            f"Bilder ({self.dateien_muster()});;Alle Dateien (*)",
        )
        if datei:
            self.ersatz_bild.setText(datei)

    def einstellungen(self) -> logik.Einstellungen:
        e = super().einstellungen()
        e.modell = self.modell.currentData() or logik.STANDARD_MODELL
        e.neuer_hintergrund = self.neuer_hintergrund.currentData() or TRANSPARENT
        e.ersatz_farbe = self._ersatz_farbe
        e.ersatz_bild = self.ersatz_bild.text().strip()
        e.unschaerfe = self.unschaerfe.value()
        e.kante = self.kante.value()
        return e

    def einstellungen_laden(self) -> None:
        super().einstellungen_laden()
        index = self.modell.findData(self.wert("modell", logik.STANDARD_MODELL))
        self.modell.setCurrentIndex(max(index, 0))
        index = self.neuer_hintergrund.findData(self.wert("neuer_hintergrund", TRANSPARENT))
        self.neuer_hintergrund.setCurrentIndex(max(index, 0))
        self.ersatz_farbe_setzen(self.wert("ersatz_farbe", "#ffffff"))
        self.ersatz_bild.setText(self.wert("ersatz_bild", ""))
        self.unschaerfe.setValue(self.wert("unschaerfe", 20, int))
        self.kante.setValue(self.wert("kante", 0, int))
        self._art_geaendert()
        self._modell_geaendert()

    def einstellungen_speichern(self) -> None:
        e = self.einstellungen()
        for schluessel in ("modell", "neuer_hintergrund", "ersatz_farbe", "ersatz_bild"):
            self.setzen(schluessel, getattr(e, schluessel))
        self.setzen("unschaerfe", e.unschaerfe)
        self.setzen("kante", int(e.kante))
        super().einstellungen_speichern()

    # --- Modell laden ---------------------------------------------------------------------

    def _modell_geaendert(self, *_args) -> None:
        name = self.modell.currentData() or logik.STANDARD_MODELL
        vorhanden = logik.modell_vorhanden(name)
        self.modell_status.setText("✓ geladen" if vorhanden else "noch nicht geladen")
        design.eigenschaft(self.modell_status, "erfolg" if vorhanden else "warnung")
        self.knopf_laden.setVisible(not vorhanden and name in MODELL_INFOS)
        info = MODELL_INFOS.get(name)
        if info is not None:
            self.knopf_laden.setText(f"Herunterladen ({info.groesse_mb} MB)")
            self.knopf_laden.setToolTip(
                f"Einmalig aus dem Internet laden, danach offline nutzbar (Lizenz {info.lizenz})"
            )

    def modell_laden(self) -> None:
        name = self.modell.currentData()
        self._download_abbrechen.clear()
        self.laden_balken.setRange(0, 0)
        self.laden_balken.setVisible(True)
        self.knopf_laden.setEnabled(False)
        self.modell.setEnabled(False)
        self.modell_status.setText("wird geladen …")
        self._pool.start(_Download(name, self._bote, self._download_abbrechen))

    def _download_fortschritt(self, fertig: int, gesamt: int) -> None:
        if gesamt:
            self.laden_balken.setRange(0, 1000)
            self.laden_balken.setValue(round(fertig / gesamt * 1000))
            self.laden_balken.setFormat(f"{fertig / 1e6:.0f} von {gesamt / 1e6:.0f} MB")

    def _download_fertig(self, fehler: str) -> None:
        self.laden_balken.setVisible(False)
        self.modell.setEnabled(True)
        self.knopf_laden.setEnabled(True)
        self._modell_geaendert()
        if fehler:
            self.status.setText(f"Modell nicht geladen: {fehler}")
        else:
            self.status.setText("Modell geladen – funktioniert jetzt auch ohne Internet.")
            self.vorschau_aktualisieren()

    # --- Vorschau und Lauf ------------------------------------------------------------------

    def vorschau_rechnung(self, pfad: str):
        einstellungen = self.einstellungen()
        return lambda: vorschaubild.vorschau_hintergrund(pfad, einstellungen, self.speicher)

    def lauf_erlaubt(self, einstellungen: logik.Einstellungen) -> bool:
        if logik.modell_vorhanden(einstellungen.modell):
            return True
        self._melden(
            self.werkzeug.titel,
            f"Das Modell „{modell_text(einstellungen.modell)}“ ist noch nicht geladen. "
            "Bitte zuerst „Herunterladen“ drücken – danach geht es ohne Internet.",
        )
        return False

    def start_meldung(self, plan: logik.Plan) -> str:
        return "KI-Modell wird geladen …"

    def schliessen(self) -> None:
        self._download_abbrechen.set()
        self._pool.waitForDone(5000)
        super().schliessen()

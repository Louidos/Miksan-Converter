"""Hauptfenster: Dateien hineinziehen, Aktion und Optionen wählen, Start drücken."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPixmap, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..fehler import MiksanFehler
from ..formats import bekannte_bild_endungen
from ..hintergrund import modell_ordner
from ..stapel import StapelErgebnis
from . import logik
from .arbeiter import Arbeiter

TITEL = "Miksan-Converter"
_ORDNER_SYMBOL = QStyle.StandardPixmap.SP_DirIcon
_DATEI_SYMBOL = QStyle.StandardPixmap.SP_FileIcon

_MODELL_TEXTE = {
    "klein": "schnell, gut für einfache Motive",
    "genau": "genauer, etwas langsamer",
    "person": "für Personen und Porträts",
    "sehr-genau": "am genauesten, langsam und gross",
}


def programm_icon() -> QIcon:
    """Programm-Icon aus dem Paket (falls vorhanden), sonst das Standard-Icon von Qt."""
    pfad = Path(__file__).with_name("miksan.png")
    return QIcon(str(pfad)) if pfad.is_file() else QIcon()


class DateiListe(QListWidget):
    """Liste der Eingaben; nimmt Dateien und Ordner per Drag & Drop an."""

    abgelegt = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        pfade = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if pfade:
            event.acceptProposedAction()
            self.abgelegt.emit(pfade)
        else:
            super().dropEvent(event)


class Hauptfenster(QMainWindow):
    def __init__(self, einstellungen: QSettings | None = None) -> None:
        super().__init__()
        self.settings = einstellungen or QSettings("Miksan", "Miksan-Converter")
        self.letztes_ergebnis: StapelErgebnis | None = None
        self._thread: QThread | None = None
        self._arbeiter: Arbeiter | None = None
        self._farbe = "#ffffff"
        self._ausgabe_ordner_offen: Path | None = None
        self._format_je_aktion: dict[str, str] = {}  # zuletzt gewähltes Zielformat je Aktion
        self._formate_fuer = logik.UMWANDELN

        self.setWindowTitle(f"{TITEL} {__version__}")
        self.setWindowIcon(programm_icon())
        self.setAcceptDrops(True)
        self.resize(980, 680)

        oben = QSplitter(Qt.Orientation.Horizontal)
        oben.addWidget(self._dateien_bereich())
        oben.addWidget(self._optionen_bereich())
        oben.setStretchFactor(0, 3)
        oben.setStretchFactor(1, 2)

        zentral = QWidget()
        layout = QVBoxLayout(zentral)
        layout.addWidget(oben, 1)
        layout.addWidget(self._ablauf_bereich())
        self.setCentralWidget(zentral)

        self._einstellungen_laden()
        self._aktion_geaendert()
        self._knoepfe_aktualisieren()

    # --- Aufbau -------------------------------------------------------------------

    def _dateien_bereich(self) -> QWidget:
        gruppe = QGroupBox("Bilder und Ordner")
        layout = QVBoxLayout(gruppe)
        hinweis = QLabel("Bilder oder Ordner hierher ziehen oder über die Knöpfe hinzufügen.")
        hinweis.setWordWrap(True)
        layout.addWidget(hinweis)

        self.liste = DateiListe()
        self.liste.abgelegt.connect(self.pfade_hinzufuegen)
        self.liste.itemSelectionChanged.connect(self._knoepfe_aktualisieren)
        layout.addWidget(self.liste, 1)

        knoepfe = QHBoxLayout()
        self.knopf_dateien = QPushButton("Dateien hinzufügen …")
        self.knopf_dateien.clicked.connect(self._dateien_waehlen)
        self.knopf_ordner = QPushButton("Ordner hinzufügen …")
        self.knopf_ordner.clicked.connect(self._ordner_waehlen)
        self.knopf_entfernen = QPushButton("Entfernen")
        self.knopf_entfernen.clicked.connect(self._auswahl_entfernen)
        self.knopf_leeren = QPushButton("Liste leeren")
        self.knopf_leeren.clicked.connect(self._liste_leeren)
        for knopf in (
            self.knopf_dateien,
            self.knopf_ordner,
            self.knopf_entfernen,
            self.knopf_leeren,
        ):
            knoepfe.addWidget(knopf)
        layout.addLayout(knoepfe)

        self.rekursiv = QCheckBox("Unterordner einbeziehen")
        layout.addWidget(self.rekursiv)
        return gruppe

    def _optionen_bereich(self) -> QWidget:
        inhalt = QWidget()
        layout = QVBoxLayout(inhalt)

        # Aktion
        aktion = QGroupBox("Aktion")
        aktion_layout = QVBoxLayout(aktion)
        self.aktion_gruppe = QButtonGroup(self)
        self.aktion_knoepfe: dict[str, QRadioButton] = {}
        self.aktion_hinweis = QLabel()
        self.aktion_hinweis.setWordWrap(True)
        self.aktion_hinweis.setStyleSheet("color: gray")
        hinweise = []
        for eintrag in logik.aktionen_fuer_auswahl():
            knopf = QRadioButton(eintrag.text)
            knopf.setProperty("aktion", eintrag.name)
            knopf.setEnabled(eintrag.verfuegbar)
            if eintrag.hinweis:
                knopf.setToolTip(eintrag.hinweis)
                hinweise.append(eintrag.hinweis)
            self.aktion_gruppe.addButton(knopf)
            self.aktion_knoepfe[eintrag.name] = knopf
            aktion_layout.addWidget(knopf)
        self.aktion_knoepfe[logik.UMWANDELN].setChecked(True)
        self.aktion_gruppe.buttonToggled.connect(self._aktion_geaendert)
        self.aktion_hinweis.setText("\n".join(hinweise))
        self.aktion_hinweis.setVisible(bool(hinweise))
        aktion_layout.addWidget(self.aktion_hinweis)
        layout.addWidget(aktion)

        # Ziel
        ziel = QGroupBox("Ziel")
        ziel_layout = QFormLayout(ziel)
        self.format_auswahl = QComboBox()
        self.format_auswahl.currentIndexChanged.connect(self._format_geaendert)
        ziel_layout.addRow("Zielformat:", self.format_auswahl)
        self.format_hinweis = QLabel()
        self.format_hinweis.setWordWrap(True)
        self.format_hinweis.setStyleSheet("color: gray")
        ziel_layout.addRow("", self.format_hinweis)

        ordner_zeile = QHBoxLayout()
        self.ausgabe_ordner = QLineEdit()
        self.ausgabe_ordner.setPlaceholderText("neben dem Original")
        self.ausgabe_ordner.setClearButtonEnabled(True)
        ordner_zeile.addWidget(self.ausgabe_ordner, 1)
        self.knopf_ausgabe = QPushButton("Wählen …")
        self.knopf_ausgabe.clicked.connect(self._ausgabe_waehlen)
        ordner_zeile.addWidget(self.knopf_ausgabe)
        ziel_layout.addRow("Ausgabeordner:", ordner_zeile)
        self.ueberschreiben = QCheckBox("Vorhandene Dateien überschreiben")
        ziel_layout.addRow("", self.ueberschreiben)
        layout.addWidget(ziel)

        # Bearbeiten
        self.bearbeiten_gruppe = QGroupBox("Bearbeiten")
        bearbeiten_layout = QFormLayout(self.bearbeiten_gruppe)
        self.max_seite = QSpinBox()
        self.max_seite.setRange(0, 100_000)
        self.max_seite.setSingleStep(100)
        self.max_seite.setSuffix(" px")
        self.max_seite.setSpecialValueText("unverändert")
        self.max_seite.setToolTip("Längste Seite höchstens so lang (verkleinert nur)")
        bearbeiten_layout.addRow("Maximale Grösse:", self.max_seite)
        self.qualitaet = QSpinBox()
        self.qualitaet.setRange(0, 100)
        self.qualitaet.setSpecialValueText("automatisch")
        self.qualitaet.setToolTip("Qualität 1–100 für JPEG, WebP, AVIF, HEIC")
        bearbeiten_layout.addRow("Qualität:", self.qualitaet)
        self.zielgroesse = QLineEdit()
        self.zielgroesse.setPlaceholderText("z. B. 500KB oder 2MB")
        self.zielgroesse.setToolTip("Datei höchstens so gross (sucht die passende Qualität)")
        bearbeiten_layout.addRow("Zielgrösse:", self.zielgroesse)
        self.drehen = QComboBox()
        self.drehen.addItems(list(logik.DREHEN))
        bearbeiten_layout.addRow("Drehen:", self.drehen)
        self.spiegeln = QComboBox()
        self.spiegeln.addItems(list(logik.SPIEGELN))
        bearbeiten_layout.addRow("Spiegeln:", self.spiegeln)
        self.metadaten = QCheckBox("Metadaten entfernen (EXIF, GPS, XMP)")
        bearbeiten_layout.addRow("", self.metadaten)
        layout.addWidget(self.bearbeiten_gruppe)

        # Hintergrund
        hintergrund = QGroupBox("Hintergrund")
        hintergrund_layout = QFormLayout(hintergrund)
        self.knopf_farbe = QPushButton()
        self.knopf_farbe.setToolTip("Füllfarbe für Transparenz bei Formaten ohne Transparenz")
        self.knopf_farbe.clicked.connect(self._farbe_waehlen)
        hintergrund_layout.addRow("Hintergrundfarbe:", self.knopf_farbe)
        self.modell = QComboBox()
        for name in logik.modelle_fuer_auswahl():
            self.modell.addItem(f"{name} – {_MODELL_TEXTE.get(name, '')}".rstrip(" –"), name)
        self.modell_label = QLabel("KI-Modell:")
        hintergrund_layout.addRow(self.modell_label, self.modell)
        layout.addWidget(hintergrund)
        layout.addStretch(1)

        rollen = QScrollArea()
        rollen.setWidgetResizable(True)
        rollen.setWidget(inhalt)
        rollen.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rand = rollen.verticalScrollBar().sizeHint().width() + 2 * rollen.frameWidth()
        rollen.setMinimumWidth(inhalt.minimumSizeHint().width() + rand)
        self.optionen = inhalt
        return rollen

    def _ablauf_bereich(self) -> QWidget:
        bereich = QWidget()
        layout = QVBoxLayout(bereich)
        layout.setContentsMargins(0, 0, 0, 0)

        zeile = QHBoxLayout()
        self.fortschritt = QProgressBar()
        self.fortschritt.setValue(0)
        zeile.addWidget(self.fortschritt, 1)
        self.knopf_start = QPushButton("Start")
        self.knopf_start.setDefault(True)
        self.knopf_start.clicked.connect(self.starten)
        zeile.addWidget(self.knopf_start)
        self.knopf_abbrechen = QPushButton("Abbrechen")
        self.knopf_abbrechen.setEnabled(False)
        self.knopf_abbrechen.clicked.connect(self.abbrechen)
        zeile.addWidget(self.knopf_abbrechen)
        layout.addLayout(zeile)

        status_zeile = QHBoxLayout()
        self.status = QLabel("Bereit.")
        status_zeile.addWidget(self.status, 1)
        self.knopf_oeffnen = QPushButton("Ausgabeordner öffnen")
        self.knopf_oeffnen.setEnabled(False)
        self.knopf_oeffnen.clicked.connect(self._ausgabe_oeffnen)
        status_zeile.addWidget(self.knopf_oeffnen)
        layout.addLayout(status_zeile)

        self.meldungen = QListWidget()
        self.meldungen.setMaximumHeight(140)
        self.meldungen.setVisible(False)
        layout.addWidget(self.meldungen)
        return bereich

    # --- Dateiliste -----------------------------------------------------------------

    def pfade(self) -> list[str]:
        return [
            self.liste.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.liste.count())
        ]

    def pfade_hinzufuegen(self, pfade: list[str | Path]) -> None:
        vorhanden = set(self.pfade())
        stil = self.style()
        for pfad in pfade:
            text = str(Path(pfad))
            if text in vorhanden:
                continue
            vorhanden.add(text)
            symbol = _ORDNER_SYMBOL if Path(text).is_dir() else _DATEI_SYMBOL
            eintrag = QListWidgetItem(stil.standardIcon(symbol), text)
            eintrag.setData(Qt.ItemDataRole.UserRole, text)
            self.liste.addItem(eintrag)
        self._knoepfe_aktualisieren()

    def dragEnterEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self.liste.dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self.liste.dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self.liste.dropEvent(event)

    def _dateien_waehlen(self) -> None:
        muster = " ".join(f"*{endung}" for endung in sorted(bekannte_bild_endungen()))
        dateien, _ = QFileDialog.getOpenFileNames(
            self,
            "Bilder hinzufügen",
            self.settings.value("letzter_ordner", "", type=str),
            f"Bilder ({muster});;Alle Dateien (*)",
        )
        if dateien:
            self.settings.setValue("letzter_ordner", str(Path(dateien[0]).parent))
            self.pfade_hinzufuegen(dateien)

    def _ordner_waehlen(self) -> None:
        ordner = QFileDialog.getExistingDirectory(
            self, "Ordner hinzufügen", self.settings.value("letzter_ordner", "", type=str)
        )
        if ordner:
            self.settings.setValue("letzter_ordner", ordner)
            self.pfade_hinzufuegen([ordner])

    def _auswahl_entfernen(self) -> None:
        for eintrag in self.liste.selectedItems():
            self.liste.takeItem(self.liste.row(eintrag))
        self._knoepfe_aktualisieren()

    def _liste_leeren(self) -> None:
        self.liste.clear()
        self._knoepfe_aktualisieren()

    # --- Optionen -------------------------------------------------------------------

    def aktion(self) -> str:
        knopf = self.aktion_gruppe.checkedButton()
        return knopf.property("aktion") if knopf else logik.UMWANDELN

    def _aktion_geaendert(self, *_args) -> None:
        aktion = self.aktion()
        gewaehlt = self._format_je_aktion.get(aktion)
        if gewaehlt is None and self.settings.contains(f"ziel_format/{aktion}"):
            gewaehlt = self.settings.value(f"ziel_format/{aktion}", "", type=str)
        self._formate_fuellen(aktion, gewaehlt)
        self.bearbeiten_gruppe.setEnabled(aktion != logik.HINTERGRUND)
        self.modell.setVisible(aktion == logik.HINTERGRUND)
        self.modell_label.setVisible(aktion == logik.HINTERGRUND)

    def _formate_fuellen(self, aktion: str, gewaehlt: str | None) -> None:
        eintraege = logik.formate_fuer_auswahl(wie_original=aktion == logik.BEARBEITEN)
        standard = {logik.UMWANDELN: "jpeg", logik.BEARBEITEN: logik.WIE_ORIGINAL}
        if gewaehlt is None or (gewaehlt == logik.WIE_ORIGINAL and aktion != logik.BEARBEITEN):
            gewaehlt = standard.get(aktion, "png")
        self._formate_fuer = aktion
        self.format_auswahl.blockSignals(True)
        self.format_auswahl.clear()
        modell = self.format_auswahl.model()
        index = 0
        for eintrag in eintraege:
            text = eintrag.text if eintrag.verfuegbar else f"{eintrag.text} (nicht verfügbar)"
            self.format_auswahl.addItem(text, eintrag.name)
            zeile = self.format_auswahl.count() - 1
            self.format_auswahl.setItemData(zeile, eintrag.hinweis, Qt.ItemDataRole.ToolTipRole)
            if not eintrag.verfuegbar and isinstance(modell, QStandardItemModel):
                modell.item(zeile).setEnabled(False)
            if eintrag.name == gewaehlt and eintrag.verfuegbar:
                index = zeile
        self.format_auswahl.setCurrentIndex(index)
        self.format_auswahl.blockSignals(False)
        self._format_geaendert()

    def _format_geaendert(self, *_args) -> None:
        if self.format_auswahl.count():
            self._format_je_aktion[self._formate_fuer] = self.format_auswahl.currentData()
        hinweis = self.format_auswahl.currentData(Qt.ItemDataRole.ToolTipRole) or ""
        self.format_hinweis.setText(hinweis)
        self.format_hinweis.setVisible(bool(hinweis))

    def format_waehlen(self, name: str) -> None:
        index = self.format_auswahl.findData(name)
        if index >= 0:
            self.format_auswahl.setCurrentIndex(index)

    def _ausgabe_waehlen(self) -> None:
        ordner = QFileDialog.getExistingDirectory(
            self, "Ausgabeordner wählen", self.ausgabe_ordner.text()
        )
        if ordner:
            self.ausgabe_ordner.setText(ordner)

    def farbe_setzen(self, farbe: str) -> None:
        self._farbe = QColor(farbe).name() if QColor(farbe).isValid() else "#ffffff"
        bild = QPixmap(32, 16)
        bild.fill(QColor(self._farbe))
        self.knopf_farbe.setIcon(QIcon(bild))
        self.knopf_farbe.setText(self._farbe)

    def _farbe_waehlen(self) -> None:
        farbe = QColorDialog.getColor(QColor(self._farbe), self, "Hintergrundfarbe wählen")
        if farbe.isValid():
            self.farbe_setzen(farbe.name())

    def einstellungen(self) -> logik.Einstellungen:
        """Liest alle Felder des Fensters."""
        ordner = self.ausgabe_ordner.text().strip()
        return logik.Einstellungen(
            aktion=self.aktion(),
            ziel_format=self.format_auswahl.currentData() or "",
            ausgabe_ordner=Path(ordner) if ordner else None,
            rekursiv=self.rekursiv.isChecked(),
            ueberschreiben=self.ueberschreiben.isChecked(),
            max_seite=self.max_seite.value() or None,
            qualitaet=self.qualitaet.value() or None,
            zielgroesse=self.zielgroesse.text(),
            drehen=logik.DREHEN[self.drehen.currentText()],
            spiegeln=logik.SPIEGELN[self.spiegeln.currentText()],
            metadaten_entfernen=self.metadaten.isChecked(),
            hintergrundfarbe=self._farbe,
            modell=self.modell.currentData() or logik.STANDARD_MODELL,
        )

    def _einstellungen_laden(self) -> None:
        s = self.settings
        aktion = s.value("aktion", logik.UMWANDELN, type=str)
        knopf = self.aktion_knoepfe.get(aktion)
        if knopf is not None and knopf.isEnabled():
            knopf.setChecked(True)
        self.rekursiv.setChecked(s.value("rekursiv", False, type=bool))
        self.ueberschreiben.setChecked(s.value("ueberschreiben", False, type=bool))
        self.ausgabe_ordner.setText(s.value("ausgabe_ordner", "", type=str))
        self.max_seite.setValue(s.value("max_seite", 0, type=int))
        self.qualitaet.setValue(s.value("qualitaet", 0, type=int))
        self.zielgroesse.setText(s.value("zielgroesse", "", type=str))
        self.drehen.setCurrentText(s.value("drehen", "keine", type=str))
        self.spiegeln.setCurrentText(s.value("spiegeln", "keine", type=str))
        self.metadaten.setChecked(s.value("metadaten_entfernen", False, type=bool))
        self.farbe_setzen(s.value("hintergrundfarbe", "#ffffff", type=str))
        index = self.modell.findData(s.value("modell", logik.STANDARD_MODELL, type=str))
        self.modell.setCurrentIndex(max(index, 0))
        self._format_je_aktion.clear()  # Format wird je Aktion in _aktion_geaendert gewählt

    def einstellungen_speichern(self) -> None:
        s = self.settings
        e = self.einstellungen()
        s.setValue("aktion", e.aktion)
        for aktion, ziel_format in self._format_je_aktion.items():
            s.setValue(f"ziel_format/{aktion}", ziel_format)
        s.setValue("rekursiv", e.rekursiv)
        s.setValue("ueberschreiben", e.ueberschreiben)
        s.setValue("ausgabe_ordner", self.ausgabe_ordner.text().strip())
        s.setValue("max_seite", self.max_seite.value())
        s.setValue("qualitaet", self.qualitaet.value())
        s.setValue("zielgroesse", e.zielgroesse)
        s.setValue("drehen", self.drehen.currentText())
        s.setValue("spiegeln", self.spiegeln.currentText())
        s.setValue("metadaten_entfernen", e.metadaten_entfernen)
        s.setValue("hintergrundfarbe", e.hintergrundfarbe)
        s.setValue("modell", e.modell)
        s.sync()

    # --- Ablauf ---------------------------------------------------------------------

    def laeuft(self) -> bool:
        return self._thread is not None

    def _knoepfe_aktualisieren(self) -> None:
        laeuft = self.laeuft()
        hat_eintraege = self.liste.count() > 0
        self.knopf_start.setEnabled(hat_eintraege and not laeuft)
        self.knopf_abbrechen.setEnabled(laeuft)
        self.knopf_entfernen.setEnabled(bool(self.liste.selectedItems()) and not laeuft)
        self.knopf_leeren.setEnabled(hat_eintraege and not laeuft)
        for widget in (self.knopf_dateien, self.knopf_ordner, self.rekursiv, self.optionen):
            widget.setEnabled(not laeuft)
        self.liste.setAcceptDrops(not laeuft)
        self.setAcceptDrops(not laeuft)

    def _melden(self, titel: str, text: str) -> None:
        QMessageBox.warning(self, titel, text)

    def _modell_download_bestaetigen(self, modell: str) -> bool:
        if logik.modell_vorhanden(modell):
            return True
        antwort = QMessageBox.question(
            self,
            "KI-Modell herunterladen",
            f"Das KI-Modell '{modell}' wird beim ersten Mal einmalig aus dem Internet geladen "
            f"(je nach Modell etwa 5 bis 200 MB) und in\n{modell_ordner()}\ngespeichert. "
            "Danach funktioniert das Entfernen des Hintergrunds ohne Internet.\n\nJetzt laden?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return antwort == QMessageBox.StandardButton.Yes

    def starten(self) -> None:
        if self.laeuft():
            return
        pfade = self.pfade()
        if not pfade:
            self._melden(TITEL, "Bitte zuerst Bilder oder Ordner hinzufügen.")
            return
        einstellungen = self.einstellungen()
        try:
            plan = logik.planen(pfade, einstellungen)
        except MiksanFehler as fehler:
            self._melden("Einstellungen prüfen", str(fehler))
            return
        if not plan.auftraege:
            self._ergebnis_zeigen(StapelErgebnis(fehler=plan.fehler), einstellungen)
            if not plan.fehler:
                self.status.setText("Keine Bilddateien gefunden.")
            return
        if einstellungen.aktion == logik.HINTERGRUND and not self._modell_download_bestaetigen(
            einstellungen.modell
        ):
            return
        self.einstellungen_speichern()

        self.letztes_ergebnis = None
        self.meldungen.clear()
        self.meldungen.setVisible(False)
        self.knopf_oeffnen.setEnabled(False)
        self.fortschritt.setRange(0, 0)  # unbestimmt, bis die erste Datei fertig ist
        if einstellungen.aktion == logik.HINTERGRUND:
            self.status.setText("KI-Modell wird geladen …")
        else:
            self.status.setText(f"{len(plan.auftraege)} Dateien werden verarbeitet …")

        self._einstellungen_lauf = einstellungen
        self._thread = QThread(self)
        self._arbeiter = Arbeiter(plan, einstellungen)
        self._arbeiter.moveToThread(self._thread)
        self._thread.started.connect(self._arbeiter.starten)
        self._arbeiter.fortschritt.connect(self._fortschritt)
        self._arbeiter.fertig.connect(self._fertig)
        self._arbeiter.fehlgeschlagen.connect(self._fehlgeschlagen)
        self._thread.start()
        self._knoepfe_aktualisieren()

    def abbrechen(self) -> None:
        if self._arbeiter is not None:
            self._arbeiter.abbrechen.set()
            self.knopf_abbrechen.setEnabled(False)
            self.status.setText("Wird abgebrochen – laufende Dateien werden noch fertig …")

    def _fortschritt(self, fertig: int, gesamt: int, name: str) -> None:
        self.fortschritt.setRange(0, gesamt)
        self.fortschritt.setValue(fertig)
        if self._arbeiter is not None and not self._arbeiter.abbrechen.is_set():
            self.status.setText(f"{fertig} von {gesamt}: {name}")

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

    def _fertig(self, ergebnis: StapelErgebnis) -> None:
        self._lauf_beenden()
        self._ergebnis_zeigen(ergebnis, self._einstellungen_lauf)

    def _fehlgeschlagen(self, meldung: str) -> None:
        self._lauf_beenden()
        self.fortschritt.setRange(0, 1)
        self.fortschritt.setValue(0)
        self.status.setText("Fehlgeschlagen.")
        self._melden(TITEL, meldung)

    def _ergebnis_zeigen(self, ergebnis: StapelErgebnis, einstellungen) -> None:
        self.letztes_ergebnis = ergebnis
        gesamt = len(ergebnis.ok) + len(ergebnis.fehler) + len(ergebnis.uebersprungen)
        self.fortschritt.setRange(0, max(gesamt, 1))
        self.fortschritt.setValue(gesamt)
        text = f"Fertig: {logik.zusammenfassung(ergebnis)}"
        self.status.setText(text)
        zeilen = logik.meldungen(ergebnis)
        self.meldungen.clear()
        self.meldungen.addItems(zeilen)
        self.meldungen.setVisible(bool(zeilen))
        self._ausgabe_ordner_offen = logik.ausgabe_ordner_von(ergebnis, einstellungen)
        self.knopf_oeffnen.setEnabled(
            self._ausgabe_ordner_offen is not None and self._ausgabe_ordner_offen.is_dir()
        )

    def _ausgabe_oeffnen(self) -> None:
        if self._ausgabe_ordner_offen is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._ausgabe_ordner_offen)))

    def closeEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        if self._arbeiter is not None:
            self._arbeiter.abbrechen.set()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
        if self.format_auswahl.count():
            self.einstellungen_speichern()
        super().closeEvent(event)


def starten(argv: list[str]) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName(TITEL)
    app.setOrganizationName("Miksan")
    app.setWindowIcon(programm_icon())
    fenster = Hauptfenster()
    vorhandene = [pfad for pfad in argv if Path(pfad).exists()]
    if vorhandene:
        fenster.pfade_hinzufuegen(vorhandene)
    fenster.show()
    return app.exec()

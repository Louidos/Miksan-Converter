"""Seiten „Einstellungen“, „Info“ und der Platzhalter für nicht verfügbare Werkzeuge."""

from __future__ import annotations

import shutil

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ... import __version__
from ...hintergrund import modell_ordner
from .. import design
from ..werkzeuge import Werkzeug
from .basis import kopf

REPO = "https://github.com/Louidos/Miksan-Converter"

BIBLIOTHEKEN = [
    ("Pillow", "Bilder lesen und schreiben", "MIT-CMU (HPND)"),
    ("pillow-heif", "HEIC/HEIF", "BSD-3-Clause"),
    ("resvg-py", "SVG rendern (Extra [svg])", "MIT"),
    ("rawpy", "Kamera-RAW (Extra [raw])", "MIT"),
    ("rembg", "Hintergrund entfernen (Extra [ki])", "MIT"),
    ("ONNX Runtime", "KI-Modell ausführen (Extra [ki])", "MIT"),
    ("PySide6 / Qt", "Oberfläche (Extra [gui])", "LGPL-3.0"),
    ("pypdf", "PDF bearbeiten (Extra [pdf])", "BSD-3-Clause"),
    ("pypdfium2", "PDF-Seiten rendern (Extra [pdf])", "Apache-2.0 / BSD-3-Clause"),
    ("U²-Net (u2netp)", "Modell „klein“ im Windows-Installer", "Apache-2.0"),
]


def _seite(titel: str, text: str, icon: str) -> tuple[QWidget, QVBoxLayout]:
    seite = QWidget()
    aussen = QVBoxLayout(seite)
    aussen.setContentsMargins(0, 0, 0, 0)
    aussen.addWidget(kopf(titel, text, icon))
    innen = QVBoxLayout()
    innen.setContentsMargins(design.abstand(3), design.abstand(1), design.abstand(3), 24)
    innen.setSpacing(design.abstand(2))
    aussen.addLayout(innen, 1)
    return seite, innen


class EinstellungenSeite(QWidget):
    def __init__(self, settings: QSettings) -> None:
        super().__init__()
        self.settings = settings
        seite, layout = _seite(
            "Einstellungen", "Gilt für alle Werkzeuge und wird sofort gespeichert.", "einstellungen"
        )
        QVBoxLayout(self).addWidget(seite)
        self.layout().setContentsMargins(0, 0, 0, 0)

        formular = QFormLayout()
        formular.setSpacing(design.abstand(1.5))
        zeile = QHBoxLayout()
        self.ausgabe_ordner = QLineEdit(settings.value("ausgabe_ordner", "", type=str))
        self.ausgabe_ordner.setPlaceholderText("neben dem Original")
        self.ausgabe_ordner.setClearButtonEnabled(True)
        self.ausgabe_ordner.editingFinished.connect(self._speichern)
        zeile.addWidget(self.ausgabe_ordner, 1)
        waehlen = QPushButton(design.icon("ordner", design.AKZENT), "Wählen …")
        waehlen.clicked.connect(self._ordner_waehlen)
        zeile.addWidget(waehlen)
        formular.addRow("Standard-Ausgabeordner:", zeile)
        self.ueberschreiben = QCheckBox("Vorhandene Dateien überschreiben")
        self.ueberschreiben.setChecked(settings.value("ueberschreiben", False, type=bool))
        self.ueberschreiben.toggled.connect(self._speichern)
        formular.addRow("", self.ueberschreiben)
        self.rekursiv = QCheckBox("Bei Ordnern auch Unterordner einbeziehen")
        self.rekursiv.setChecked(settings.value("rekursiv", False, type=bool))
        self.rekursiv.toggled.connect(self._speichern)
        formular.addRow("", self.rekursiv)
        layout.addLayout(formular)

        layout.addWidget(design.eigenschaft(QLabel("KI-Modelle"), "untertitel"))
        self.modell_pfad = QLabel(str(modell_ordner()))
        self.modell_pfad.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.modell_pfad.setWordWrap(True)
        layout.addWidget(self.modell_pfad)
        self.modell_groesse = design.eigenschaft(QLabel(), "hinweis")
        layout.addWidget(self.modell_groesse)
        knoepfe = QHBoxLayout()
        oeffnen = QPushButton(design.icon("ordner_oeffnen", design.AKZENT), "Ordner öffnen")
        oeffnen.clicked.connect(self._modelle_oeffnen)
        self.knopf_loeschen = QPushButton(
            design.icon("entfernen", design.AKZENT), "Modelle löschen"
        )
        self.knopf_loeschen.clicked.connect(self.modelle_loeschen)
        knoepfe.addWidget(oeffnen)
        knoepfe.addWidget(self.knopf_loeschen)
        knoepfe.addStretch(1)
        layout.addLayout(knoepfe)
        layout.addStretch(1)
        self._modelle_anzeigen()

    def _speichern(self, *_args) -> None:
        self.settings.setValue("ausgabe_ordner", self.ausgabe_ordner.text().strip())
        self.settings.setValue("ueberschreiben", self.ueberschreiben.isChecked())
        self.settings.setValue("rekursiv", self.rekursiv.isChecked())
        self.settings.sync()

    def _ordner_waehlen(self) -> None:
        ordner = QFileDialog.getExistingDirectory(self, "Standard-Ausgabeordner", "")
        if ordner:
            self.ausgabe_ordner.setText(ordner)
            self._speichern()

    def _modelle_anzeigen(self) -> None:
        ordner = modell_ordner()
        dateien = list(ordner.rglob("*.onnx")) if ordner.is_dir() else []
        groesse = sum(datei.stat().st_size for datei in dateien) / 1e6
        self.modell_groesse.setText(
            f"{len(dateien)} Modelle, {groesse:.0f} MB"
            if dateien
            else "Noch keine Modelle geladen."
        )
        self.knopf_loeschen.setEnabled(bool(dateien))

    def showEvent(self, event) -> None:  # noqa: N802 – Qt-Name
        self._modelle_anzeigen()
        super().showEvent(event)

    def _modelle_oeffnen(self) -> None:
        ordner = modell_ordner()
        ordner.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(ordner)))

    def _bestaetigen(self, text: str) -> bool:
        antwort = QMessageBox.question(self, "Modelle löschen", text)
        return antwort == QMessageBox.StandardButton.Yes

    def modelle_loeschen(self) -> None:
        ordner = modell_ordner()
        if not ordner.is_dir():
            return
        if self._bestaetigen(
            f"Alle heruntergeladenen KI-Modelle in\n{ordner}\nlöschen? "
            "Sie werden bei Bedarf neu geladen."
        ):
            shutil.rmtree(ordner, ignore_errors=True)
        self._modelle_anzeigen()


class InfoSeite(QWidget):
    def __init__(self) -> None:
        super().__init__()
        seite, layout = _seite(
            "Info", f"Miksan-Converter {__version__} – Dateien umwandeln, lokal.", "info"
        )
        QVBoxLayout(self).addWidget(seite)
        self.layout().setContentsMargins(0, 0, 0, 0)
        text = QLabel(
            f"<p><b>Version {__version__}</b> · Lizenz MIT</p>"
            "<p>Alles läuft lokal auf diesem Rechner: <b>ohne Cloud, ohne Werbung, ohne "
            "Telemetrie, ohne Konto</b>. Nur KI-Modelle werden nach Bestätigung einmalig "
            "heruntergeladen.</p>"
            f'<p>Quellcode, Fehler melden und neue Versionen: <a href="{REPO}">{REPO}</a></p>'
        )
        text.setWordWrap(True)
        text.setOpenExternalLinks(True)
        layout.addWidget(text)
        layout.addWidget(design.eigenschaft(QLabel("Genutzte Bibliotheken"), "untertitel"))
        tabelle = QFormLayout()
        tabelle.setSpacing(design.abstand(1))
        for name, zweck, lizenz in BIBLIOTHEKEN:
            tabelle.addRow(f"{name}:", design.eigenschaft(QLabel(f"{zweck} – {lizenz}"), "hinweis"))
        layout.addLayout(tabelle)
        layout.addStretch(1)


class NichtVerfuegbarSeite(QWidget):
    """Statt der Werkzeug-Seite, wenn ein Extra fehlt: Hinweis mit Installationsbefehl."""

    def __init__(self, werkzeug: Werkzeug) -> None:
        super().__init__()
        self.werkzeug = werkzeug
        seite, layout = _seite(werkzeug.titel, werkzeug.beschreibung, werkzeug.icon)
        QVBoxLayout(self).addWidget(seite)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.hinweis = design.eigenschaft(QLabel(werkzeug.hinweis()), "warnung")
        self.hinweis.setWordWrap(True)
        self.hinweis.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.hinweis)
        layout.addWidget(
            design.eigenschaft(
                QLabel("Im Windows-Installer ist alles enthalten. Danach die App neu starten."),
                "hinweis",
            )
        )
        layout.addStretch(1)

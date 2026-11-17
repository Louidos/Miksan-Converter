"""Werkzeuge im Bereich „PDF“ (Extra [pdf]).

Alle nutzen dieselben Funktionen wie ``miksan pdf`` (``miksan_converter.pdf``). Die Felder
werden im Fenster gelesen; im Hintergrund-Thread läuft nur die fertige Aufgabe.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QComboBox, QInputDialog, QLineEdit, QSpinBox

from ... import pdf
from ...fehler import BedienFehler, MiksanFehler
from ...stapel import Auftrag, StapelErgebnis, dateien_sammeln
from ..widgets.seitenraster import SeitenRaster
from .basis import WerkzeugSeite

Arbeit = Callable[[Path], list[Path]]


class PdfSeite(WerkzeugSeite):
    """Gemeinsame Basis: Passwörter, Seiten-Miniaturen, Lauf nacheinander."""

    dateien_filter = "PDF ({muster});;Alle Dateien (*)"
    mit_seiten = True

    def dateien_muster(self) -> str:
        return "*.pdf *.PDF"

    def aufbau_fertig(self) -> None:
        self.passwoerter: dict[str, str] = {}
        self.raster: SeitenRaster | None = None
        if self.mit_seiten:
            self.raster = SeitenRaster()
            self.links.addWidget(self.raster)
            self.links.setStretchFactor(0, 1)
            self.links.setStretchFactor(1, 2)
            self.liste.currentItemChanged.connect(self._seiten_zeigen)
            self.liste.geaendert.connect(self._erste_waehlen)

    def _erste_waehlen(self) -> None:
        if self.liste.count() and self.liste.currentRow() < 0:
            self.liste.setCurrentRow(0)
        elif not self.liste.count() and self.raster is not None:
            self.raster.zeigen(None)

    def _seiten_zeigen(self, *_args) -> None:
        pfad = self.liste.ausgewaehlter_pfad()
        if self.raster is None or pfad is None:
            return
        if pdf.ist_verschluesselt(pfad) and pfad not in self.passwoerter:
            self.raster.zeigen(None)
            self.raster.hinweis.setText("Geschützt – das Passwort wird beim Start abgefragt.")
            return
        self.raster.zeigen(pfad, self.passwoerter.get(pfad))

    # --- Passwörter -----------------------------------------------------------------------

    def passwort_fragen(self, pfad: str, falsch: bool) -> str | None:
        text = "Das Passwort war falsch. " if falsch else ""
        wert, ok = QInputDialog.getText(
            self,
            "PDF mit Passwort",
            f"{text}Passwort für {Path(pfad).name}:",
            QLineEdit.EchoMode.Password,
        )
        return wert if ok and wert else None

    def passwoerter_pruefen(self, pfade: list[Path]) -> bool:
        """Fragt für geschützte PDFs nach dem Passwort (im Fenster, nicht im Lauf)."""
        for pfad in pfade:
            schluessel = str(pfad)
            if not pdf.ist_verschluesselt(pfad):
                continue
            falsch = False
            while True:
                passwort = self.passwoerter.get(schluessel)
                if passwort is None:
                    passwort = self.passwort_fragen(schluessel, falsch)
                    if passwort is None:
                        self.status.setText("Abgebrochen – kein Passwort.")
                        return False
                try:
                    pdf.lesen(pfad, passwort)
                except pdf.PasswortNoetig:
                    self.passwoerter.pop(schluessel, None)
                    falsch = True
                    continue
                except Exception:  # beschädigt: Fehler meldet später der Lauf
                    pass
                self.passwoerter[schluessel] = passwort
                break
        return True

    # --- Lauf -------------------------------------------------------------------------------

    def eingaben(self) -> list[Path]:
        return [Path(p) for p in self.pfade() if Path(p).is_file()]

    def ziel_ordner(self, eingabe: Path) -> Path:
        return self.ausgabe_ordner() or eingabe.parent

    def ordner_fuer(self) -> Callable[[Path], Path]:
        """Ausgabeordner im Fenster lesen; die Funktion darf dann im Thread laufen."""
        ordner = self.ausgabe_ordner()
        return lambda eingabe: ordner or eingabe.parent

    def arbeit_erstellen(self) -> Arbeit:
        """Unterklassen: liest die Felder und liefert die Arbeit pro PDF."""
        raise NotImplementedError

    def vorbereiten(self):
        eingaben = self.eingaben()
        if not self.passwoerter_pruefen(eingaben):
            return None
        arbeit = self.arbeit_erstellen()

        def aufgabe(rueckmeldung, abbrechen) -> StapelErgebnis:
            return pdf.nacheinander(eingaben, arbeit, rueckmeldung, abbrechen)

        return aufgabe, f"{len(eingaben)} PDFs werden verarbeitet …"

    def schliessen(self) -> None:
        if self.raster is not None:
            self.raster.schliessen()
        super().schliessen()


def _zahl(minimum: int, maximum: int, wert: int, suffix: str = "") -> QSpinBox:
    feld = QSpinBox()
    feld.setRange(minimum, maximum)
    feld.setValue(wert)
    feld.setSuffix(suffix)
    return feld


def _seiten_feld(platzhalter: str) -> QLineEdit:
    feld = QLineEdit()
    feld.setPlaceholderText(platzhalter)
    feld.setToolTip("Seiten wie 1-3,5 – oder unten in den Miniaturen markieren")
    return feld


class ZusammenfuegenSeite(PdfSeite):
    start_text = "Zusammenfügen"
    mit_seiten = False

    def optionen_aufbauen(self) -> None:
        self.dateiname = QLineEdit()
        self.dateiname.setPlaceholderText("zusammengefuegt.pdf")
        self.formular.addRow("Dateiname:", self.dateiname)
        hinweis = self.hinweis_label()
        hinweis.setText("Reihenfolge = Reihenfolge der Liste (ziehen oder Alt+↑/↓).")
        hinweis.setVisible(True)
        self.formular.addRow("", hinweis)

    def aufbau_fertig(self) -> None:
        super().aufbau_fertig()
        self.liste.sortierbar_machen()

    def vorbereiten(self):
        eingaben = [Path(p) for p in self.pfade()]
        if len(eingaben) < 2:
            self._melden(self.werkzeug.titel, "Bitte mindestens zwei PDFs hinzufügen.")
            return None
        if not self.passwoerter_pruefen(eingaben):
            return None
        name = self.dateiname.text().strip() or "zusammengefuegt.pdf"
        ziel = self.ziel_ordner(eingaben[0]) / (name if name.endswith(".pdf") else f"{name}.pdf")
        passwoerter, ueberschreiben = dict(self.passwoerter), self.ueberschreiben()

        def aufgabe(rueckmeldung, abbrechen) -> StapelErgebnis:
            ergebnis = StapelErgebnis()
            try:
                pdf.zusammenfuegen(
                    eingaben, ziel, passwoerter=passwoerter, overwrite=ueberschreiben
                )
            except MiksanFehler as fehler:
                ergebnis.fehler.append((eingaben[0], str(fehler)))
            else:
                ergebnis.ok.extend(Auftrag(e, ziel) for e in eingaben)
            rueckmeldung(1, 1, ziel.name)
            return ergebnis

        return aufgabe, f"{len(eingaben)} PDFs werden zusammengefügt …"


class TeilenSeite(PdfSeite):
    start_text = "Teilen"

    def optionen_aufbauen(self) -> None:
        self.seiten = _seiten_feld("leer = jede Seite einzeln")
        self.formular.addRow("Bereiche:", self.seiten)

    def aufbau_fertig(self) -> None:
        super().aufbau_fertig()
        self.raster.auswahl_geaendert.connect(
            lambda seiten: self.seiten.setText(",".join(map(str, seiten)))
        )

    def arbeit_erstellen(self) -> Arbeit:
        seiten = self.seiten.text().strip() or None
        pw, ueber, ordner = dict(self.passwoerter), self.ueberschreiben(), self.ordner_fuer()
        return lambda e: pdf.teilen(
            e, ordner(e), seiten=seiten, passwort=pw.get(str(e)), overwrite=ueber
        )


DREHEN = {"nicht drehen": 0, "90° rechts": 90, "180°": 180, "90° links": 270}


class SeitenSeite(PdfSeite):
    start_text = "Speichern"

    def optionen_aufbauen(self) -> None:
        self.drehen = QComboBox()
        self.drehen.addItems(list(DREHEN))
        self.formular.addRow("Drehen:", self.drehen)
        self.drehen_seiten = _seiten_feld("leer = alle Seiten")
        self.formular.addRow("Seiten drehen:", self.drehen_seiten)
        self.loeschen = _seiten_feld("z. B. 2,5")
        self.formular.addRow("Seiten löschen:", self.loeschen)
        self.markiert = self.hinweis_label()
        self.formular.addRow("", self.markiert)

    def aufbau_fertig(self) -> None:
        super().aufbau_fertig()
        self.raster.auswahl_geaendert.connect(self._markiert)

    def _markiert(self, seiten: list[int]) -> None:
        text = ",".join(map(str, seiten))
        self.markiert.setText(f"Markiert: {text}" if text else "")
        self.markiert.setVisible(bool(text))
        if text:
            ziel = self.loeschen if self.drehen.currentIndex() == 0 else self.drehen_seiten
            ziel.setText(text)

    def arbeit_erstellen(self) -> Arbeit:
        grad = DREHEN[self.drehen.currentText()]
        drehen_seiten = self.drehen_seiten.text().strip() or None
        loeschen = self.loeschen.text().strip() or None
        if not grad and not loeschen:
            raise BedienFehler("Bitte drehen oder Seiten zum Löschen angeben.")
        pw, ueber, ordner = dict(self.passwoerter), self.ueberschreiben(), self.ordner_fuer()

        def arbeit(e: Path) -> list[Path]:
            ziel = ordner(e) / pdf.standard_name(e, "bearbeitet")
            return [
                pdf.seiten_aendern(
                    e,
                    ziel,
                    drehen=grad,
                    drehen_seiten=drehen_seiten,
                    loeschen=loeschen,
                    passwort=pw.get(str(e)),
                    overwrite=ueber,
                )
            ]

        return arbeit


class BilderSeite(PdfSeite):
    start_text = "Bilder speichern"

    def optionen_aufbauen(self) -> None:
        self.bildformat = QComboBox()
        self.bildformat.addItem("PNG – verlustfrei", "png")
        self.bildformat.addItem("JPEG – kleiner", "jpeg")
        self.formular.addRow("Format:", self.bildformat)
        self.dpi = _zahl(30, 1200, pdf.STANDARD_DPI, " DPI")
        self.dpi.setSingleStep(50)
        self.formular.addRow("Auflösung:", self.dpi)
        self.seiten = _seiten_feld("leer = alle Seiten")
        self.formular.addRow("Seiten:", self.seiten)

    def aufbau_fertig(self) -> None:
        super().aufbau_fertig()
        self.raster.auswahl_geaendert.connect(
            lambda seiten: self.seiten.setText(",".join(map(str, seiten)))
        )

    def arbeit_erstellen(self) -> Arbeit:
        fmt, dpi = self.bildformat.currentData(), self.dpi.value()
        seiten = self.seiten.text().strip() or None
        pw, ueber, ordner = dict(self.passwoerter), self.ueberschreiben(), self.ordner_fuer()
        return lambda e: pdf.zu_bildern(
            e,
            ordner(e),
            bildformat=fmt,
            dpi=dpi,
            seiten=seiten,
            passwort=pw.get(str(e)),
            overwrite=ueber,
        )


class AusBildernSeite(PdfSeite):
    start_text = "PDF erstellen"
    mit_seiten = False
    dateien_filter = "Bilder ({muster});;Alle Dateien (*)"

    def dateien_muster(self) -> str:
        return WerkzeugSeite.dateien_muster(self)

    def optionen_aufbauen(self) -> None:
        self.seitengroesse = QComboBox()
        self.seitengroesse.addItem("A4 – Bild eingepasst", "a4")
        self.seitengroesse.addItem("Wie das Bild", "bild")
        self.formular.addRow("Seitengrösse:", self.seitengroesse)
        self.dateiname = QLineEdit()
        self.dateiname.setPlaceholderText("wie das erste Bild")
        self.formular.addRow("Dateiname:", self.dateiname)

    def aufbau_fertig(self) -> None:
        super().aufbau_fertig()
        self.liste.sortierbar_machen()

    def vorbereiten(self):
        dateien, fehler = dateien_sammeln(self.pfade(), rekursiv=self.rekursiv())
        bilder = [datei.pfad for datei in dateien]
        if not bilder:
            self._melden(self.werkzeug.titel, "Keine Bilder gefunden.")
            return None
        name = self.dateiname.text().strip() or f"{bilder[0].stem}.pdf"
        ziel = self.ziel_ordner(bilder[0]) / (name if name.endswith(".pdf") else f"{name}.pdf")
        groesse, ueber = self.seitengroesse.currentData(), self.ueberschreiben()

        def aufgabe(rueckmeldung, abbrechen) -> StapelErgebnis:
            ergebnis = StapelErgebnis(fehler=list(fehler))
            try:
                pdf.aus_bildern(bilder, ziel, seitengroesse=groesse, overwrite=ueber)
            except MiksanFehler as fehler_:
                ergebnis.fehler.append((bilder[0], str(fehler_)))
            else:
                ergebnis.ok.extend(Auftrag(b, ziel) for b in bilder)
            rueckmeldung(1, 1, ziel.name)
            return ergebnis

        return aufgabe, f"{len(bilder)} Bilder werden zu einem PDF …"


class VerkleinernSeite(PdfSeite):
    start_text = "Verkleinern"
    mit_seiten = False

    def optionen_aufbauen(self) -> None:
        self.qualitaet = _zahl(1, 100, pdf.STANDARD_QUALITAET)
        self.qualitaet.setToolTip("JPEG-Qualität der eingebetteten Bilder (kleiner = kleiner)")
        self.formular.addRow("Bildqualität:", self.qualitaet)

    def arbeit_erstellen(self) -> Arbeit:
        qualitaet = self.qualitaet.value()
        pw, ueber, ordner = dict(self.passwoerter), self.ueberschreiben(), self.ordner_fuer()

        def arbeit(e: Path) -> list[Path]:
            ziel = ordner(e) / pdf.standard_name(e, "klein")
            ergebnis = pdf.verkleinern(
                e, ziel, qualitaet=qualitaet, passwort=pw.get(str(e)), overwrite=ueber
            )
            return [ergebnis[0]]

        return arbeit

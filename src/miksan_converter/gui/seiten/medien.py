"""Werkzeuge im Bereich „Video & Audio“ (ffmpeg).

Dateien werden nacheinander verarbeitet (ffmpeg nutzt selbst alle Kerne). Der Fortschritt
kommt in Prozent aus ``ffmpeg -progress``; Abbrechen beendet ffmpeg sofort und löscht die
halbfertige Datei. Alle Arbeit machen die Funktionen aus ``miksan_converter.medien``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSpinBox

from ... import medien
from ...fehler import BedienFehler, MiksanFehler
from ...stapel import Auftrag, StapelErgebnis
from ..werkzeuge import AUDIO_ENDUNGEN, VIDEO_ENDUNGEN
from .basis import WerkzeugSeite

# Arbeit(eingabe, ziel_oder_None, fortschritt, abbrechen) -> Ausgabe
Arbeit = Callable[..., Path]


def _auswahl(eintraege) -> QComboBox:
    feld = QComboBox()
    for wert, text in eintraege:
        feld.addItem(text, wert)
    return feld


def _zeitfeld(platzhalter: str) -> QLineEdit:
    feld = QLineEdit()
    feld.setPlaceholderText(platzhalter)
    feld.setToolTip("Zeit wie 1:05, 0:01:05 oder 65 (Sekunden)")
    return feld


QUALITAET = (("klein", "klein"), ("ausgewogen", "ausgewogen"), ("hoch", "hoch"))


class MedienSeite(WerkzeugSeite):
    endungen = VIDEO_ENDUNGEN
    dateien_filter = "Video ({muster});;Alle Dateien (*)"
    endung = "mp4"  # Endung im Ausgabeordner

    def dateien_muster(self) -> str:
        return " ".join(f"*{e}" for e in sorted(self.endungen))

    def arbeit_erstellen(self) -> Arbeit:
        raise NotImplementedError

    def ziel_endung(self, eingabe: Path) -> str:
        return self.endung

    def vorbereiten(self):
        eingaben = [Path(p) for p in self.pfade() if Path(p).is_file()]
        arbeit = self.arbeit_erstellen()
        ordner = self.ausgabe_ordner()
        endungen = {e: self.ziel_endung(e) for e in eingaben}

        def aufgabe(rueckmeldung, abbrechen) -> StapelErgebnis:
            ergebnis = StapelErgebnis()
            gesamt = len(eingaben) * 1000
            for index, eingabe in enumerate(eingaben):
                if abbrechen.is_set():
                    ergebnis.uebersprungen.append(Auftrag(eingabe, eingabe))
                    continue
                ziel = ordner / f"{eingabe.stem}.{endungen[eingabe]}" if ordner else None

                def fortschritt(anteil: float, i=index, name=eingabe.name) -> None:
                    rueckmeldung(int((i + anteil) * 1000), gesamt, name)

                try:
                    ausgabe = arbeit(eingabe, ziel, fortschritt, abbrechen)
                except MiksanFehler as fehler:
                    if abbrechen.is_set():
                        ergebnis.uebersprungen.append(Auftrag(eingabe, eingabe))
                    else:
                        ergebnis.fehler.append((eingabe, str(fehler)))
                else:
                    ergebnis.ok.append(Auftrag(eingabe, ausgabe))
                rueckmeldung((index + 1) * 1000, gesamt, eingabe.name)
            return ergebnis

        return aufgabe, f"{len(eingaben)} Dateien werden nacheinander verarbeitet …"

    def _fortschritt(self, fertig: int, gesamt: int, name: str) -> None:
        self.ablauf.fortschritt.setRange(0, gesamt)
        self.ablauf.fortschritt.setValue(fertig)
        if self._arbeiter is not None and not self._arbeiter.abbrechen.is_set():
            prozent = fertig * 100 // max(gesamt, 1)
            self.ablauf.status.setText(f"{name} – gesamt {prozent} %")

    def abbrechen(self) -> None:
        super().abbrechen()
        if self._arbeiter is not None:
            self.ablauf.status.setText("Wird abgebrochen – ffmpeg wird beendet …")


class VideoUmwandelnSeite(MedienSeite):
    start_text = "Umwandeln"

    def optionen_aufbauen(self) -> None:
        self.ziel = _auswahl(
            (
                ("mp4", "MP4 (H.264 + AAC) – läuft überall"),
                ("webm", "WebM (VP9 + Opus) – für das Web"),
                ("mkv", "MKV (H.264 + AAC)"),
                ("mov", "MOV (H.264 + AAC)"),
                ("gif", "GIF – Animation ohne Ton"),
            )
        )
        self.formular.addRow("Zielformat:", self.ziel)
        self.qualitaet = _auswahl(QUALITAET)
        self.qualitaet.setCurrentIndex(1)
        self.formular.addRow("Qualität:", self.qualitaet)
        self.aufloesung = _auswahl(
            ((None, "Original"), (1080, "1080p"), (720, "720p"), (480, "480p"))
        )
        self.formular.addRow("Auflösung:", self.aufloesung)
        self.ohne_ton = QCheckBox("Ton entfernen")
        self.formular.addRow("", self.ohne_ton)
        self.crf = QSpinBox()
        self.crf.setRange(0, 63)
        self.crf.setSpecialValueText("aus der Qualität")
        self.crf.setToolTip("Kleiner = bessere Qualität und grössere Datei (H.264: 18–28)")
        self.formular_erweitert.addRow("CRF:", self.crf)
        self.fps = QSpinBox()
        self.fps.setRange(0, 240)
        self.fps.setSpecialValueText("wie Original")
        self.formular_erweitert.addRow("Bildrate:", self.fps)

    def ziel_endung(self, eingabe: Path) -> str:
        return self.ziel.currentData()

    def arbeit_erstellen(self) -> Arbeit:
        werte = {
            "ziel": self.ziel.currentData(),
            "qualitaet": self.qualitaet.currentData(),
            "crf": self.crf.value() or None,
            "aufloesung": self.aufloesung.currentData(),
            "fps": self.fps.value() or None,
            "ohne_ton": self.ohne_ton.isChecked(),
            "overwrite": self.ueberschreiben(),
        }
        return lambda e, z, f, a: medien.video_umwandeln(e, z, fortschritt=f, abbrechen=a, **werte)


class KuerzenSeite(MedienSeite):
    start_text = "Kürzen"

    def optionen_aufbauen(self) -> None:
        self.start = _zeitfeld("Anfang")
        self.ende = _zeitfeld("Ende")
        self.formular.addRow("Start:", self.start)
        self.formular.addRow("Ende:", self.ende)
        self.genau = QCheckBox("Bildgenau schneiden (neu kodieren, langsamer)")
        self.genau.setToolTip(
            "Ohne Neukodierung geht es sehr schnell, beginnt aber am nächsten Schlüsselbild."
        )
        self.formular.addRow("", self.genau)

    def ziel_endung(self, eingabe: Path) -> str:
        return eingabe.suffix.lstrip(".") or "mp4"

    def arbeit_erstellen(self) -> Arbeit:
        start, ende = medien.zeit_parsen(self.start.text()), medien.zeit_parsen(self.ende.text())
        genau, ueber = self.genau.isChecked(), self.ueberschreiben()
        if start is None and ende is None:
            raise BedienFehler("Bitte Start und/oder Ende angeben.")
        return lambda e, z, f, a: medien.kuerzen(
            e, z, start=start, ende=ende, neu_kodieren=genau, fortschritt=f, abbrechen=a,
            overwrite=ueber,
        )  # fmt: skip


ZIELGROESSEN = ((8, "8 MB"), (10, "10 MB – Discord"), (25, "25 MB – E-Mail"), (50, "50 MB"))


class VerkleinernSeite(MedienSeite):
    start_text = "Verkleinern"

    def optionen_aufbauen(self) -> None:
        self.zielgroesse = QComboBox()
        for wert, text in ZIELGROESSEN:
            self.zielgroesse.addItem(f"höchstens {text}", wert)
        self.zielgroesse.addItem("eigene Grösse", 0)
        self.zielgroesse.setCurrentIndex(1)
        self.zielgroesse.currentIndexChanged.connect(self._eigene)
        self.formular.addRow("Zielgrösse:", self.zielgroesse)
        self.eigene_mb = QSpinBox()
        self.eigene_mb.setRange(1, 4000)
        self.eigene_mb.setValue(20)
        self.eigene_mb.setSuffix(" MB")
        self.formular.addRow("Eigene:", self.eigene_mb)
        self.aufloesung = _auswahl(
            ((None, "Original"), (1080, "1080p"), (720, "720p"), (480, "480p"))
        )
        self.formular.addRow("Auflösung:", self.aufloesung)
        self._eigene()

    def _eigene(self, *_args) -> None:
        self.formular.setRowVisible(self.eigene_mb, self.zielgroesse.currentData() == 0)

    def arbeit_erstellen(self) -> Arbeit:
        mb = self.zielgroesse.currentData() or self.eigene_mb.value()
        aufloesung, ueber = self.aufloesung.currentData(), self.ueberschreiben()
        return lambda e, z, f, a: medien.verkleinern(
            e, z, ziel_byte=mb * 1_000_000, aufloesung=aufloesung, fortschritt=f, abbrechen=a,
            overwrite=ueber,
        )  # fmt: skip


class GifSeite(MedienSeite):
    start_text = "GIF erstellen"
    endung = "gif"

    def optionen_aufbauen(self) -> None:
        self.breite = QSpinBox()
        self.breite.setRange(16, 1920)
        self.breite.setValue(480)
        self.breite.setSuffix(" px breit")
        self.formular.addRow("Grösse:", self.breite)
        self.fps = QSpinBox()
        self.fps.setRange(1, 50)
        self.fps.setValue(12)
        self.fps.setSuffix(" Bilder/s")
        self.formular.addRow("Bildrate:", self.fps)
        self.start = _zeitfeld("Anfang")
        self.ende = _zeitfeld("Ende")
        self.formular.addRow("Start:", self.start)
        self.formular.addRow("Ende:", self.ende)

    def arbeit_erstellen(self) -> Arbeit:
        werte = {
            "breite": self.breite.value(),
            "fps": self.fps.value(),
            "start": medien.zeit_parsen(self.start.text()),
            "ende": medien.zeit_parsen(self.ende.text()),
            "overwrite": self.ueberschreiben(),
        }
        return lambda e, z, f, a: medien.zu_gif(e, z, fortschritt=f, abbrechen=a, **werte)


TONFORMATE = (
    ("mp3", "MP3"),
    ("m4a", "M4A (AAC)"),
    ("flac", "FLAC – verlustfrei"),
    ("wav", "WAV – unkomprimiert"),
    ("ogg", "OGG (Vorbis)"),
    ("opus", "Opus"),
)


class TonSeite(MedienSeite):
    start_text = "Ton speichern"

    def optionen_aufbauen(self) -> None:
        self.ziel = _auswahl(TONFORMATE)
        self.formular.addRow("Format:", self.ziel)
        self.qualitaet = _auswahl(QUALITAET)
        self.qualitaet.setCurrentIndex(1)
        self.formular.addRow("Qualität:", self.qualitaet)

    def ziel_endung(self, eingabe: Path) -> str:
        return self.ziel.currentData()

    def arbeit_erstellen(self) -> Arbeit:
        werte = {
            "ziel": self.ziel.currentData(),
            "qualitaet": self.qualitaet.currentData(),
            "overwrite": self.ueberschreiben(),
        }
        return lambda e, z, f, a: medien.audio_umwandeln(e, z, fortschritt=f, abbrechen=a, **werte)


class EinzelbildSeite(MedienSeite):
    start_text = "Bild speichern"

    def optionen_aufbauen(self) -> None:
        self.zeit = _zeitfeld("0:00 = erstes Bild")
        self.formular.addRow("Zeitpunkt:", self.zeit)
        self.bildformat = _auswahl((("png", "PNG"), ("jpg", "JPEG")))
        self.formular.addRow("Format:", self.bildformat)

    def ziel_endung(self, eingabe: Path) -> str:
        return self.bildformat.currentData()

    def arbeit_erstellen(self) -> Arbeit:
        zeit = medien.zeit_parsen(self.zeit.text()) or 0.0
        endung, ueber = self.bildformat.currentData(), self.ueberschreiben()

        def arbeit(e: Path, z: Path | None, f, a) -> Path:
            ziel = z or medien.standard_ziel(e, endung, f"bild-{int(zeit)}s")
            return medien.einzelbild(e, ziel, zeit=zeit, overwrite=ueber, abbrechen=a)

        return arbeit


class AudioSeite(TonSeite):
    endungen = AUDIO_ENDUNGEN
    dateien_filter = "Ton ({muster});;Alle Dateien (*)"
    start_text = "Umwandeln"

    def optionen_aufbauen(self) -> None:
        super().optionen_aufbauen()
        self.normalisieren = QCheckBox("Lautstärke angleichen (EBU R128)")
        self.formular.addRow("", self.normalisieren)
        self.start = _zeitfeld("Anfang")
        self.ende = _zeitfeld("Ende")
        self.formular_erweitert.addRow("Start:", self.start)
        self.formular_erweitert.addRow("Ende:", self.ende)
        self.bitrate = QLineEdit()
        self.bitrate.setPlaceholderText("aus der Qualität, z. B. 192k")
        self.formular_erweitert.addRow("Bitrate:", self.bitrate)

    def arbeit_erstellen(self) -> Arbeit:
        werte = {
            "ziel": self.ziel.currentData(),
            "qualitaet": self.qualitaet.currentData(),
            "bitrate": self.bitrate.text().strip() or None,
            "normalisieren": self.normalisieren.isChecked(),
            "start": medien.zeit_parsen(self.start.text()),
            "ende": medien.zeit_parsen(self.ende.text()),
            "overwrite": self.ueberschreiben(),
        }
        return lambda e, z, f, a: medien.audio_umwandeln(e, z, fortschritt=f, abbrechen=a, **werte)

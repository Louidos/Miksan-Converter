"""Werkzeug „Animation“: GIF/WebP aus Bildern erstellen oder Animation in Einzelbilder zerlegen."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QComboBox, QLineEdit, QSpinBox

from ...fehler import MiksanFehler
from ...stapel import Auftrag, StapelErgebnis, dateien_sammeln
from ...werkzeuge import animation
from .bildwerkzeug import BildWerkzeugSeite

ERSTELLEN, ZERLEGEN = "erstellen", "zerlegen"


class AnimationSeite(BildWerkzeugSeite):
    start_text = "Los"

    def optionen_aufbauen(self) -> None:
        f = self.formular
        self.modus = QComboBox()
        self.modus.addItem("Animation aus den Bildern erstellen", ERSTELLEN)
        self.modus.addItem("Animationen in Einzelbilder zerlegen", ZERLEGEN)
        self.modus.currentIndexChanged.connect(self._modus_geaendert)
        f.addRow("Aufgabe:", self.modus)
        self.ziel = QComboBox()
        self.ziel.addItem("GIF – läuft überall", "gif")
        self.ziel.addItem("WebP – kleiner, mehr Farben", "webp")
        f.addRow("Format:", self.ziel)
        self.dauer = QSpinBox()
        self.dauer.setRange(10, 60_000)
        self.dauer.setSingleStep(50)
        self.dauer.setSuffix(" ms pro Bild")
        f.addRow("Dauer:", self.dauer)
        self.schleife = QSpinBox()
        self.schleife.setRange(0, 1000)
        self.schleife.setSpecialValueText("endlos")
        f.addRow("Wiederholen:", self.schleife)
        self.dateiname = QLineEdit()
        self.dateiname.setPlaceholderText("animation")
        f.addRow("Dateiname:", self.dateiname)
        self.einzelformat = QComboBox()
        for name in ("png", "webp", "jpeg"):
            self.einzelformat.addItem(name.upper(), name)
        f.addRow("Einzelbilder als:", self.einzelformat)
        self.hinweis = self.hinweis_label()
        f.addRow("", self.hinweis)

    def aufbau_fertig(self) -> None:
        super().aufbau_fertig()
        self.liste.sortierbar_machen()
        self._modus_geaendert()

    def _modus_geaendert(self, *_args) -> None:
        erstellen = self.modus.currentData() == ERSTELLEN
        for feld in (self.ziel, self.dauer, self.schleife, self.dateiname):
            self.formular.setRowVisible(feld, erstellen)
        self.formular.setRowVisible(self.einzelformat, not erstellen)
        self.hinweis.setText(
            "Reihenfolge = Reihenfolge der Liste (ziehen oder Alt+↑/↓). Alle Bilder werden "
            "auf die Grösse des ersten eingepasst."
            if erstellen
            else "Pro Animation entsteht ein Ordner <name>-bilder mit allen Einzelbildern."
        )
        self.hinweis.setVisible(True)

    def einstellungen_laden(self) -> None:
        super().einstellungen_laden()
        self.modus.setCurrentIndex(max(0, self.modus.findData(self.wert("modus", ERSTELLEN))))
        self.ziel.setCurrentIndex(max(0, self.ziel.findData(self.wert("ziel", "gif"))))
        self.dauer.setValue(self.wert("dauer", animation.STANDARD_DAUER, int))
        self.schleife.setValue(self.wert("schleife", 0, int))

    def einstellungen_speichern(self) -> None:
        self.setzen("modus", self.modus.currentData())
        self.setzen("ziel", self.ziel.currentData())
        self.setzen("dauer", self.dauer.value())
        self.setzen("schleife", self.schleife.value())
        super().einstellungen_speichern()

    def vorbereiten(self):
        dateien, fehler = dateien_sammeln(self.pfade(), rekursiv=self.rekursiv())
        bilder = [d.pfad for d in dateien]
        ueber = self.ueberschreiben()
        ordner = self.ausgabe_ordner()
        if self.modus.currentData() == ZERLEGEN:
            fmt = self.einzelformat.currentData()

            def zerlegen(rueckmeldung, abbrechen) -> StapelErgebnis:
                ergebnis = StapelErgebnis(fehler=list(fehler))
                for nummer, bild in enumerate(bilder, start=1):
                    if abbrechen.is_set():
                        ergebnis.uebersprungen.append(Auftrag(bild, bild))
                        continue
                    ziel = (ordner / f"{bild.stem}-bilder") if ordner else None
                    try:
                        teile = animation.zerlegen(bild, ziel, bildformat=fmt, overwrite=ueber)
                    except MiksanFehler as meldung:
                        ergebnis.fehler.append((bild, str(meldung)))
                    else:
                        ergebnis.ok.extend(Auftrag(bild, teil) for teil in teile)
                    rueckmeldung(nummer, len(bilder), bild.name)
                return ergebnis

            return zerlegen, f"{len(bilder)} Animationen werden zerlegt …"

        if len(bilder) < 2:
            self._melden(self.werkzeug.titel, "Bitte mindestens zwei Bilder hinzufügen.")
            return None
        name = self.dateiname.text().strip() or "animation"
        endung = f".{self.ziel.currentData()}"
        ziel = (ordner or bilder[0].parent) / (name if name.endswith(endung) else name + endung)
        dauer, schleife = self.dauer.value(), self.schleife.value()

        def erstellen(rueckmeldung, abbrechen) -> StapelErgebnis:
            ergebnis = StapelErgebnis(fehler=list(fehler))
            try:
                animation.erstellen(bilder, ziel, dauer=dauer, schleife=schleife, overwrite=ueber)
            except MiksanFehler as meldung:
                ergebnis.fehler.append((bilder[0], str(meldung)))
            else:
                ergebnis.ok.extend(Auftrag(b, Path(ziel)) for b in bilder)
            rueckmeldung(1, 1, ziel.name)
            return ergebnis

        return erstellen, f"Animation aus {len(bilder)} Bildern wird erstellt …"

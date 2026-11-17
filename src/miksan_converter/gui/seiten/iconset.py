"""Werkzeug „Icon-Set“: favicon.ico und PNG-Icons in allen üblichen Grössen."""

from __future__ import annotations

from ...stapel import Auftrag, Datei
from ...werkzeuge import iconset
from .bildwerkzeug import BildWerkzeugSeite


class IconsetSeite(BildWerkzeugSeite):
    start_text = "Icons erstellen"

    def optionen_aufbauen(self) -> None:
        hinweis = self.hinweis_label()
        groessen = ", ".join(str(g) for g in iconset.PNG_GROESSEN)
        hinweis.setText(
            "Pro Bild entsteht ein Ordner <name>-icons mit favicon.ico "
            f"(16–256 px) und PNGs in {groessen} px. Nicht quadratische Bilder werden "
            "zentriert und transparent aufgefüllt."
        )
        hinweis.setVisible(True)
        self.formular.addRow(hinweis)

    def ziel_fuer(self):
        ordner = self.ausgabe_ordner()

        def ziel(datei: Datei):
            basis = ordner if ordner is not None else datei.pfad.parent
            return basis / f"{datei.pfad.stem}-icons" / "favicon.ico"

        return ziel

    def arbeit_erstellen(self):
        ueber = self.ueberschreiben()

        def arbeit(auftrag: Auftrag) -> list[str]:
            iconset.erstellen(auftrag.eingabe, auftrag.ausgabe.parent, overwrite=ueber)
            return []

        return arbeit

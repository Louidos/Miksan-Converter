"""Fehlerarten mit festen Rückgabecodes für die Kommandozeile."""


class MiksanFehler(Exception):
    """Allgemeiner Fehler mit verständlicher Meldung für Nutzer."""

    rueckgabecode = 1


class BedienFehler(MiksanFehler):
    """Falsche Bedienung, z. B. widersprüchliche Optionen."""

    rueckgabecode = 2


class ExtraFehlt(MiksanFehler):
    """Für diese Funktion fehlt ein optionales Extra."""

    rueckgabecode = 3

    def __init__(self, extra: str, wofuer: str):
        self.extra = extra
        super().__init__(
            f"{wofuer} braucht das Extra [{extra}]. "
            f"Bitte `pip install miksan-converter[{extra}]` installieren."
        )

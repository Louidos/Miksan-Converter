"""Fehlerarten mit festen Rückgabecodes für die Kommandozeile."""


class MiksanFehler(Exception):
    """Allgemeiner Fehler mit verständlicher Meldung für Nutzer."""

    rueckgabecode = 1


class BedienFehler(MiksanFehler):
    """Falsche Bedienung, z. B. widersprüchliche Optionen."""

    rueckgabecode = 2

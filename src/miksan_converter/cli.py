"""Kommandozeile für Miksan-Converter."""

from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .convert import umwandeln
from .fehler import MiksanFehler
from .formats import alle_formate, extra_installiert, markdown_tabelle, tabellen_zeilen


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="miksan",
        description="Bilder umwandeln und bearbeiten – lokal und ohne Cloud.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    befehle = parser.add_subparsers(dest="befehl", metavar="<befehl>")

    convert = befehle.add_parser(
        "convert",
        aliases=["umwandeln"],
        help="Bild in ein anderes Format umwandeln",
        description="Wandelt ein Bild in ein anderes Format um. Das Eingabeformat wird am "
        "Dateiinhalt erkannt, das Zielformat an der Endung der Ausgabe oder mit --to.",
    )
    convert.add_argument("eingabe", type=Path, help="Eingabedatei")
    convert.add_argument("ausgabe", type=Path, nargs="?", help="Ausgabedatei (optional mit --to)")
    convert.add_argument(
        "--to", "--nach", dest="to", metavar="FORMAT", help="Zielformat, z. B. jpg"
    )
    convert.add_argument(
        "--overwrite",
        "--ueberschreiben",
        action="store_true",
        help="vorhandene Zieldatei ersetzen",
    )
    convert.add_argument(
        "--background",
        "--hintergrundfarbe",
        dest="background",
        default="#ffffff",
        metavar="FARBE",
        help="Füllfarbe für Transparenz bei Zielen ohne Alpha, z. B. #000000 (Standard: weiss)",
    )
    convert.add_argument(
        "--page",
        "--seite",
        dest="page",
        type=_positive_zahl,
        metavar="N",
        help="nur diese Seite bzw. dieses Einzelbild übernehmen (ab 1)",
    )
    convert.add_argument(
        "-v", "--verbose", "--ausfuehrlich", action="store_true", help="Details anzeigen"
    )
    convert.set_defaults(ausfuehren=_befehl_convert)

    formats = befehle.add_parser(
        "formats", aliases=["formate"], help="unterstützte Formate auflisten"
    )
    formats.add_argument(
        "--markdown", action="store_true", help="Tabelle im Markdown-Format ausgeben"
    )
    formats.add_argument(
        "-v", "--verbose", "--ausfuehrlich", action="store_true", help="Details anzeigen"
    )
    formats.set_defaults(ausfuehren=_befehl_formats)
    return parser


def _positive_zahl(text: str) -> int:
    try:
        zahl = int(text)
    except ValueError:
        zahl = 0
    if zahl < 1:
        raise argparse.ArgumentTypeError(f"'{text}' ist keine Zahl ab 1")
    return zahl


def _hinweise(hinweise: list[str]) -> None:
    for hinweis in hinweise:
        print(f"Hinweis: {hinweis}", file=sys.stderr)


def _befehl_convert(args: argparse.Namespace) -> int:
    ergebnis = umwandeln(
        args.eingabe,
        args.ausgabe,
        to=args.to,
        overwrite=args.overwrite,
        hintergrund=args.background,
        seite=args.page,
    )
    _hinweise(ergebnis.hinweise)
    if args.verbose:
        print(
            f"{ergebnis.eingabe} ({ergebnis.eingabe_format}) -> "
            f"{ergebnis.ausgabe} ({ergebnis.ausgabe_format.name})",
            file=sys.stderr,
        )
    print(f"Gespeichert: {ergebnis.ausgabe}")
    return 0


def _befehl_formats(args: argparse.Namespace) -> int:
    if args.markdown:
        print(markdown_tabelle())
        return 0
    zeilen = tabellen_zeilen()
    breiten = [max(len(z[i]) for z in zeilen) for i in range(len(zeilen[0]))]
    for zeile in zeilen:
        felder = (wert.ljust(breite) for wert, breite in zip(zeile, breiten, strict=True))
        print("  ".join(felder).rstrip())
    extras = {fmt.extra for fmt in alle_formate() if fmt.extra}
    fehlende = sorted(extra for extra in extras if not extra_installiert(extra))
    print()
    print("Weitere Formate, die Pillow lesen kann (z. B. PSD, PCX, ICNS, DDS), werden ebenfalls")
    print("gelesen.")
    for extra in fehlende:
        print(f"Extra [{extra}] ist nicht installiert: pip install miksan-converter[{extra}]")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(errors="replace")
    parser = _parser()
    args = parser.parse_args(argv)
    if not getattr(args, "ausfuehren", None):
        parser.print_help()
        return 2
    try:
        return args.ausfuehren(args)
    except MiksanFehler as fehler:
        print(f"Fehler: {fehler}", file=sys.stderr)
        if getattr(args, "verbose", False) and fehler.__cause__ is not None:
            traceback.print_exception(fehler.__cause__, file=sys.stderr)
        return fehler.rueckgabecode
    except KeyboardInterrupt:
        print("Abgebrochen.", file=sys.stderr)
        return 130
    except Exception as fehler:
        print(f"Unerwarteter Fehler: {fehler}", file=sys.stderr)
        if getattr(args, "verbose", False):
            traceback.print_exc(file=sys.stderr)
        else:
            print("Mit --verbose werden Details angezeigt.", file=sys.stderr)
        return 1

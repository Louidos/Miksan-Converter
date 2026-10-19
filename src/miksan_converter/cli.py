"""Kommandozeile für Miksan-Converter."""

from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .bearbeiten import REIHENFOLGE, Bearbeitung, groesse_parsen, zuschnitt_parsen
from .convert import Ergebnis, bearbeiten, umwandeln
from .fehler import BedienFehler, MiksanFehler
from .formats import alle_formate, extra_installiert, markdown_tabelle, tabellen_zeilen
from .hintergrund import STANDARD_MODELL, hintergrund_entfernen


def _ausfuehrlich(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-v", "--verbose", "--ausfuehrlich", action="store_true", help="Details anzeigen"
    )


def _datei_optionen(parser: argparse.ArgumentParser) -> None:
    """Optionen, die alle Befehle mit Ein- und Ausgabedatei gemeinsam haben."""
    parser.add_argument("eingabe", type=Path, help="Eingabedatei")
    parser.add_argument("ausgabe", type=Path, nargs="?", help="Ausgabedatei (optional)")
    parser.add_argument("--to", "--nach", dest="to", metavar="FORMAT", help="Zielformat, z. B. jpg")
    parser.add_argument(
        "--overwrite",
        "--ueberschreiben",
        action="store_true",
        help="vorhandene Zieldatei ersetzen",
    )
    parser.add_argument(
        "--background",
        "--hintergrundfarbe",
        dest="background",
        default="#ffffff",
        metavar="FARBE",
        help="Füllfarbe für Transparenz bei Zielen ohne Alpha, z. B. #000000 (Standard: weiss)",
    )
    parser.add_argument(
        "--page",
        "--seite",
        dest="page",
        type=_positive_zahl,
        metavar="N",
        help="nur diese Seite bzw. dieses Einzelbild übernehmen (ab 1)",
    )
    _ausfuehrlich(parser)


def _bearbeitungs_optionen(parser: argparse.ArgumentParser) -> None:
    gruppe = parser.add_argument_group("Bearbeiten", "Reihenfolge: " + " -> ".join(REIHENFOLGE))
    gruppe.add_argument(
        "--breite",
        "--width",
        dest="breite",
        type=_positive_zahl,
        metavar="PX",
        help="neue Breite (ohne --hoehe bleibt das Seitenverhältnis)",
    )
    gruppe.add_argument(
        "--hoehe",
        "--height",
        dest="hoehe",
        type=_positive_zahl,
        metavar="PX",
        help="neue Höhe (ohne --breite bleibt das Seitenverhältnis)",
    )
    gruppe.add_argument(
        "--max",
        dest="max_seite",
        type=_positive_zahl,
        metavar="PX",
        help="längste Seite höchstens so lang (verkleinert nur, Seitenverhältnis bleibt)",
    )
    gruppe.add_argument(
        "--zuschneiden",
        "--crop",
        dest="zuschneiden",
        metavar="X,Y,B,H",
        help="Ausschnitt: linke obere Ecke x,y sowie Breite und Höhe in Pixeln",
    )
    gruppe.add_argument(
        "--drehen",
        "--rotate",
        dest="drehen",
        type=int,
        choices=(90, 180, 270),
        help="im Uhrzeigersinn drehen",
    )
    gruppe.add_argument(
        "--spiegeln",
        "--flip",
        dest="spiegeln",
        choices=("h", "v"),
        help="h = waagrecht (links/rechts), v = senkrecht (oben/unten)",
    )
    gruppe.add_argument(
        "--qualitaet",
        "--quality",
        dest="qualitaet",
        type=int,
        metavar="1-100",
        help="Qualität für JPEG, WebP, AVIF, HEIC",
    )
    gruppe.add_argument(
        "--zielgroesse",
        "--target-size",
        dest="zielgroesse",
        metavar="GROESSE",
        help="höchstens so gross, z. B. 500KB oder 2MB (sucht die passende Qualität)",
    )
    gruppe.add_argument(
        "--metadaten-entfernen",
        "--strip",
        dest="metadaten_entfernen",
        action="store_true",
        help="EXIF/GPS/XMP entfernen (Ausrichtung wird vorher angewendet)",
    )


def _bearbeitung(args: argparse.Namespace) -> Bearbeitung:
    return Bearbeitung(
        breite=args.breite,
        hoehe=args.hoehe,
        max_seite=args.max_seite,
        zuschneiden=zuschnitt_parsen(args.zuschneiden) if args.zuschneiden else None,
        drehen=args.drehen,
        spiegeln=args.spiegeln,
        qualitaet=args.qualitaet,
        zielgroesse=groesse_parsen(args.zielgroesse) if args.zielgroesse else None,
        metadaten_entfernen=args.metadaten_entfernen,
    )


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
    _datei_optionen(convert)
    _bearbeitungs_optionen(convert)
    convert.set_defaults(ausfuehren=_befehl_convert)

    bearbeiten_befehl = befehle.add_parser(
        "bearbeiten",
        aliases=["edit"],
        help="Bild skalieren, zuschneiden, drehen, komprimieren, Metadaten entfernen",
        description="Bearbeitet ein Bild. Ohne Ausgabedatei entsteht <name>-bearbeitet im "
        "selben Format neben dem Original.",
    )
    _datei_optionen(bearbeiten_befehl)
    _bearbeitungs_optionen(bearbeiten_befehl)
    bearbeiten_befehl.set_defaults(ausfuehren=_befehl_bearbeiten)

    hintergrund = befehle.add_parser(
        "hintergrund",
        aliases=["bg"],
        help="Hintergrund entfernen (lokales KI-Modell, Extra [ki])",
        description="Entfernt den Hintergrund mit einem lokalen KI-Modell. Ohne Ausgabedatei "
        "entsteht <name>-freigestellt.png neben dem Original. Das Modell wird beim ersten Mal "
        "heruntergeladen und danach offline genutzt.",
    )
    _datei_optionen(hintergrund)
    hintergrund.add_argument(
        "--modell",
        "--model",
        dest="modell",
        default=STANDARD_MODELL,
        metavar="NAME",
        help="klein (Standard, schnell), genau, person, sehr-genau oder ein rembg-Modellname",
    )
    hintergrund.add_argument(
        "--nur-maske",
        "--mask-only",
        dest="nur_maske",
        action="store_true",
        help="nur die Maske ausgeben (weiss = Vordergrund)",
    )
    hintergrund.set_defaults(ausfuehren=_befehl_hintergrund)

    formats = befehle.add_parser(
        "formats", aliases=["formate"], help="unterstützte Formate auflisten"
    )
    formats.add_argument(
        "--markdown", action="store_true", help="Tabelle im Markdown-Format ausgeben"
    )
    _ausfuehrlich(formats)
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
        bearbeitung=_bearbeitung(args),
    )
    return _ergebnis_melden(ergebnis, args)


def _befehl_bearbeiten(args: argparse.Namespace) -> int:
    bearbeitung = _bearbeitung(args)
    if not bearbeitung.veraendert_pixel() and not (
        bearbeitung.qualitaet or bearbeitung.zielgroesse or bearbeitung.metadaten_entfernen
    ):
        raise BedienFehler(
            "Keine Bearbeitung angegeben, z. B. --max 1200, --drehen 90 oder --zielgroesse 500KB."
        )
    ergebnis = bearbeiten(
        args.eingabe,
        args.ausgabe,
        to=args.to,
        overwrite=args.overwrite,
        hintergrund=args.background,
        seite=args.page,
        bearbeitung=bearbeitung,
    )
    return _ergebnis_melden(ergebnis, args)


def _ergebnis_melden(ergebnis: Ergebnis, args: argparse.Namespace) -> int:
    _hinweise(ergebnis.hinweise)
    if args.verbose:
        print(
            f"{ergebnis.eingabe} ({ergebnis.eingabe_format}) -> "
            f"{ergebnis.ausgabe} ({ergebnis.ausgabe_format.name})",
            file=sys.stderr,
        )
    print(f"Gespeichert: {ergebnis.ausgabe}")
    return 0


def _befehl_hintergrund(args: argparse.Namespace) -> int:
    ergebnis = hintergrund_entfernen(
        args.eingabe,
        args.ausgabe,
        to=args.to,
        modell=args.modell,
        nur_maske=args.nur_maske,
        hintergrund=args.background,
        overwrite=args.overwrite,
        seite=args.page,
    )
    _hinweise(ergebnis.hinweise)
    if args.verbose:
        print(f"Modell: {ergebnis.modell}", file=sys.stderr)
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

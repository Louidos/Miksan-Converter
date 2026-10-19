"""Kommandozeile für Miksan-Converter."""

from __future__ import annotations

import argparse
import sys
import traceback
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .bearbeiten import REIHENFOLGE, Bearbeitung, groesse_parsen, zuschnitt_parsen
from .convert import Ergebnis, bearbeiten, quellformat_erkennen, umwandeln
from .fehler import BedienFehler, MiksanFehler
from .formats import (
    Format,
    alle_formate,
    extra_installiert,
    format_aus_name,
    markdown_tabelle,
    tabellen_zeilen,
)
from .hintergrund import (
    STANDARD_MODELL,
    hintergrund_entfernen,
    sitzung_erstellen,
    standard_ausgabe,
)
from .stapel import (
    Auftrag,
    Datei,
    auftraege_planen,
    ausfuehren,
    dateien_sammeln,
    ist_muster,
    zusammenfassung_ausgeben,
)


def _ausfuehrlich(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-v", "--verbose", "--ausfuehrlich", action="store_true", help="Details anzeigen"
    )


def _datei_optionen(parser: argparse.ArgumentParser) -> None:
    """Optionen, die alle Befehle mit Ein- und Ausgabedateien gemeinsam haben."""
    parser.add_argument(
        "pfade",
        nargs="+",
        metavar="PFAD",
        help="Eingabedatei(en), Ordner oder Muster wie *.heic. Genau zwei Dateien ohne -o: "
        "die zweite ist die Ausgabedatei.",
    )
    parser.add_argument(
        "-o",
        "--ausgabe-ordner",
        "--output",
        dest="ausgabe_ordner",
        type=Path,
        metavar="ORDNER",
        help="Ausgabeordner für mehrere Dateien (wird bei Bedarf angelegt)",
    )
    parser.add_argument(
        "-r",
        "--rekursiv",
        "--recursive",
        dest="rekursiv",
        action="store_true",
        help="auch Unterordner verarbeiten (Ordnerstruktur bleibt in der Ausgabe erhalten)",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        dest="jobs",
        type=_positive_zahl,
        metavar="N",
        help="so viele Dateien gleichzeitig verarbeiten (Standard: Anzahl CPU-Kerne)",
    )
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
        description="Wandelt Bilder in ein anderes Format um. Das Eingabeformat wird am "
        "Dateiinhalt erkannt, das Zielformat an der Endung der Ausgabe oder mit --to. "
        "Mehrere Dateien, Ordner oder Muster brauchen --to; mit -o landen die Ergebnisse "
        "in einem Ordner, sonst neben den Originalen.",
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


def _einzeldatei(args: argparse.Namespace) -> tuple[Path, Path | None] | None:
    """Erkennt den Aufruf mit einer Datei (und optional einer Ausgabedatei)."""
    if args.ausgabe_ordner is not None or args.rekursiv:
        return None
    pfade = args.pfade

    def einfach(text: str) -> bool:
        return not ist_muster(text) and not Path(text).is_dir()

    if len(pfade) == 1 and einfach(pfade[0]):
        return Path(pfade[0]), None
    zweite_ist_eingabe = args.to is not None and Path(pfade[-1]).is_file()
    if len(pfade) == 2 and einfach(pfade[0]) and einfach(pfade[1]) and not zweite_ist_eingabe:
        return Path(pfade[0]), Path(pfade[1])
    return None


def _stapel(
    args: argparse.Namespace,
    ziel_fuer,
    arbeit,
    vorbereiten=None,
) -> int:
    """Verarbeitet mehrere Dateien parallel und gibt eine Zusammenfassung aus."""
    ordner = args.ausgabe_ordner
    if ordner is not None and ordner.exists() and not ordner.is_dir():
        raise BedienFehler(f"-o '{ordner}' ist eine Datei, erwartet wird ein Ordner.")
    dateien, fehler = dateien_sammeln(args.pfade, rekursiv=args.rekursiv)
    auftraege, planfehler = auftraege_planen(dateien, ziel_fuer, ordner)
    fehler += planfehler
    if not auftraege and not fehler:
        raise MiksanFehler("Keine Bilddateien gefunden.")
    if auftraege:
        if ordner is not None:
            ordner.mkdir(parents=True, exist_ok=True)
        if vorbereiten is not None:
            vorbereiten()

    def mit_ordner(auftrag: Auftrag) -> list[str]:
        auftrag.ausgabe.parent.mkdir(parents=True, exist_ok=True)
        return arbeit(auftrag)

    ergebnis = ausfuehren(auftraege, mit_ordner, jobs=args.jobs, fortschritt=sys.stderr)
    ergebnis.fehler = fehler + ergebnis.fehler
    if args.verbose:
        for auftrag in ergebnis.ok:
            print(f"{auftrag.eingabe} -> {auftrag.ausgabe}", file=sys.stderr)
    zusammenfassung_ausgeben(ergebnis)
    return ergebnis.rueckgabecode


def _ziel_im_ordner(args: argparse.Namespace, datei: Datei, fmt: Format) -> Path | None:
    if args.ausgabe_ordner is None:
        return None
    return args.ausgabe_ordner / datei.relativ.with_suffix(fmt.endung)


def _befehl_convert(args: argparse.Namespace) -> int:
    bearbeitung = _bearbeitung(args)
    einzeln = _einzeldatei(args)
    if einzeln is not None:
        ergebnis = umwandeln(
            *einzeln,
            to=args.to,
            overwrite=args.overwrite,
            hintergrund=args.background,
            seite=args.page,
            bearbeitung=bearbeitung,
        )
        return _ergebnis_melden(ergebnis, args)

    if not args.to:
        raise BedienFehler("Für mehrere Dateien oder Ordner bitte das Zielformat mit --to angeben.")
    ziel = format_aus_name(args.to)

    def ziel_fuer(datei: Datei) -> Path:
        return _ziel_im_ordner(args, datei, ziel) or datei.pfad.with_suffix(ziel.endung)

    def arbeit(auftrag: Auftrag) -> list[str]:
        return umwandeln(
            auftrag.eingabe,
            auftrag.ausgabe,
            to=args.to,
            overwrite=args.overwrite,
            hintergrund=args.background,
            seite=args.page,
            bearbeitung=bearbeitung,
        ).hinweise

    return _stapel(args, ziel_fuer, arbeit)


def _befehl_bearbeiten(args: argparse.Namespace) -> int:
    bearbeitung = _bearbeitung(args)
    if not bearbeitung.veraendert_pixel() and not (
        bearbeitung.qualitaet or bearbeitung.zielgroesse or bearbeitung.metadaten_entfernen
    ):
        raise BedienFehler(
            "Keine Bearbeitung angegeben, z. B. --max 1200, --drehen 90 oder --zielgroesse 500KB."
        )
    optionen = {
        "to": args.to,
        "overwrite": args.overwrite,
        "hintergrund": args.background,
        "seite": args.page,
        "bearbeitung": bearbeitung,
    }
    einzeln = _einzeldatei(args)
    if einzeln is not None:
        return _ergebnis_melden(bearbeiten(*einzeln, **optionen), args)

    fest = format_aus_name(args.to) if args.to else None

    def ziel_fuer(datei: Datei) -> Path:
        fmt = fest or quellformat_erkennen(datei.pfad)
        if fmt is None or not fmt.schreiben:
            fmt = format_aus_name("png")
        im_ordner = _ziel_im_ordner(args, datei, fmt)
        return im_ordner or datei.pfad.with_name(f"{datei.pfad.stem}-bearbeitet{fmt.endung}")

    def arbeit(auftrag: Auftrag) -> list[str]:
        return bearbeiten(auftrag.eingabe, auftrag.ausgabe, **optionen).hinweise

    return _stapel(args, ziel_fuer, arbeit)


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
    optionen = {
        "to": args.to,
        "modell": args.modell,
        "nur_maske": args.nur_maske,
        "hintergrund": args.background,
        "overwrite": args.overwrite,
        "seite": args.page,
    }
    einzeln = _einzeldatei(args)
    if einzeln is not None:
        ergebnis = hintergrund_entfernen(*einzeln, **optionen)
        _hinweise(ergebnis.hinweise)
        if args.verbose:
            print(f"Modell: {ergebnis.modell}", file=sys.stderr)
        print(f"Gespeichert: {ergebnis.ausgabe}")
        return 0

    ziel = format_aus_name(args.to or "png")
    sitzung = []

    def ziel_fuer(datei: Datei) -> Path:
        im_ordner = _ziel_im_ordner(args, datei, ziel)
        return im_ordner or standard_ausgabe(datei.pfad, ziel, args.nur_maske)

    def vorbereiten() -> None:
        sitzung.append(sitzung_erstellen(args.modell))

    def arbeit(auftrag: Auftrag) -> list[str]:
        return hintergrund_entfernen(
            auftrag.eingabe, auftrag.ausgabe, sitzung=sitzung[0], **optionen
        ).hinweise

    return _stapel(args, ziel_fuer, arbeit, vorbereiten)


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

"""Befehl ``miksan pdf`` (Extra [pdf]): zusammenfügen, teilen, drehen, löschen, PDF ↔ Bilder,
verkleinern. Wird von ``cli.py`` eingebunden."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import pdf
from .fehler import BedienFehler


def _gemeinsam(parser: argparse.ArgumentParser, *, passwort: bool = True) -> None:
    if passwort:
        parser.add_argument(
            "--passwort", "--password", dest="passwort", help="Passwort eines geschützten PDFs"
        )
    parser.add_argument(
        "--overwrite",
        "--ueberschreiben",
        action="store_true",
        help="vorhandene Ausgabedateien ersetzen",
    )
    parser.add_argument(
        "-v", "--verbose", "--ausfuehrlich", action="store_true", help="Details anzeigen"
    )


def _ausgabe(parser: argparse.ArgumentParser, text: str) -> None:
    parser.add_argument("-o", "--ausgabe", "--output", dest="ausgabe", type=Path, help=text)


def befehle_anlegen(befehle) -> None:
    haupt = befehle.add_parser(
        "pdf",
        help="PDF zusammenfügen, teilen, drehen, in Bilder umwandeln … (Extra [pdf])",
        description="PDF-Werkzeuge, lokal und ohne Cloud. Das Original wird nie verändert.",
    )
    unter = haupt.add_subparsers(dest="pdf_befehl", metavar="<aktion>")

    p = unter.add_parser("zusammenfuegen", aliases=["merge"], help="PDFs zu einem zusammenfügen")
    p.add_argument("eingaben", nargs="+", type=Path, metavar="PDF")
    _ausgabe(p, "Ausgabedatei (Standard: <erstes>-zusammengefuegt.pdf)")
    _gemeinsam(p)
    p.set_defaults(ausfuehren=_zusammenfuegen)

    p = unter.add_parser("teilen", aliases=["split"], help="PDF in Teile oder Einzelseiten teilen")
    p.add_argument("eingabe", type=Path, metavar="PDF")
    p.add_argument("--seiten", help="Bereiche wie 1-3,5 (je Bereich eine Datei); leer = jede Seite")
    _ausgabe(p, "Ausgabeordner (Standard: neben dem Original)")
    _gemeinsam(p)
    p.set_defaults(ausfuehren=_teilen)

    p = unter.add_parser("drehen", aliases=["rotate"], help="Seiten drehen")
    p.add_argument("eingabe", type=Path, metavar="PDF")
    p.add_argument("--grad", type=int, choices=(90, 180, 270), default=90, help="im Uhrzeigersinn")
    p.add_argument("--seiten", help="nur diese Seiten, z. B. 1,3-4 (Standard: alle)")
    _ausgabe(p, "Ausgabedatei (Standard: <name>-gedreht.pdf)")
    _gemeinsam(p)
    p.set_defaults(ausfuehren=_drehen)

    p = unter.add_parser("loeschen", aliases=["delete"], help="Seiten löschen")
    p.add_argument("eingabe", type=Path, metavar="PDF")
    p.add_argument("--seiten", required=True, help="zu löschende Seiten, z. B. 2,5-6")
    _ausgabe(p, "Ausgabedatei (Standard: <name>-bearbeitet.pdf)")
    _gemeinsam(p)
    p.set_defaults(ausfuehren=_loeschen)

    p = unter.add_parser("bilder", aliases=["to-images"], help="Seiten als PNG oder JPEG speichern")
    p.add_argument("eingabe", type=Path, metavar="PDF")
    p.add_argument("--format", dest="bildformat", choices=("png", "jpeg", "jpg"), default="png")
    p.add_argument("--dpi", type=int, default=pdf.STANDARD_DPI, help="Auflösung (Standard: 150)")
    p.add_argument("--seiten", help="nur diese Seiten (Standard: alle)")
    _ausgabe(p, "Ausgabeordner (Standard: neben dem Original)")
    _gemeinsam(p)
    p.set_defaults(ausfuehren=_bilder)

    p = unter.add_parser("aus-bildern", aliases=["from-images"], help="Bilder zu einem PDF")
    p.add_argument("eingaben", nargs="+", type=Path, metavar="BILD")
    p.add_argument(
        "--seitengroesse",
        "--page-size",
        dest="seitengroesse",
        choices=pdf.SEITENGROESSEN,
        default="a4",
        help="a4 (Standard, Bild eingepasst) oder bild (Seite so gross wie das Bild)",
    )
    _ausgabe(p, "Ausgabedatei (Standard: <erstes>.pdf)")
    _gemeinsam(p, passwort=False)
    p.set_defaults(ausfuehren=_aus_bildern)

    p = unter.add_parser(
        "verkleinern", aliases=["compress"], help="eingebettete Bilder komprimieren"
    )
    p.add_argument("eingabe", type=Path, metavar="PDF")
    p.add_argument(
        "--qualitaet", type=int, default=pdf.STANDARD_QUALITAET, help="JPEG-Qualität 1–100"
    )
    _ausgabe(p, "Ausgabedatei (Standard: <name>-klein.pdf)")
    _gemeinsam(p)
    p.set_defaults(ausfuehren=_verkleinern)

    haupt.set_defaults(ausfuehren=lambda args: _hilfe(haupt))


def _hilfe(parser: argparse.ArgumentParser) -> int:
    parser.print_help()
    return 2


def _gespeichert(pfade) -> int:
    for pfad in pfade:
        print(f"Gespeichert: {pfad}")
    return 0


def _ziel(args, eingabe: Path, zusatz: str) -> Path:
    return args.ausgabe or eingabe.with_name(pdf.standard_name(eingabe, zusatz))


def _zusammenfuegen(args) -> int:
    ziel = _ziel(args, args.eingaben[0], "zusammengefuegt")
    passwoerter = {str(p): args.passwort for p in args.eingaben} if args.passwort else None
    return _gespeichert(
        [pdf.zusammenfuegen(args.eingaben, ziel, passwoerter=passwoerter, overwrite=args.overwrite)]
    )


def _teilen(args) -> int:
    return _gespeichert(
        pdf.teilen(
            args.eingabe,
            args.ausgabe,
            seiten=args.seiten,
            passwort=args.passwort,
            overwrite=args.overwrite,
        )
    )


def _drehen(args) -> int:
    ziel = _ziel(args, args.eingabe, "gedreht")
    return _gespeichert(
        [
            pdf.seiten_aendern(
                args.eingabe,
                ziel,
                drehen=args.grad,
                drehen_seiten=args.seiten,
                passwort=args.passwort,
                overwrite=args.overwrite,
            )
        ]
    )


def _loeschen(args) -> int:
    ziel = _ziel(args, args.eingabe, "bearbeitet")
    return _gespeichert(
        [
            pdf.seiten_aendern(
                args.eingabe,
                ziel,
                loeschen=args.seiten,
                passwort=args.passwort,
                overwrite=args.overwrite,
            )
        ]
    )


def _bilder(args) -> int:
    return _gespeichert(
        pdf.zu_bildern(
            args.eingabe,
            args.ausgabe,
            bildformat=args.bildformat,
            dpi=args.dpi,
            seiten=args.seiten,
            passwort=args.passwort,
            overwrite=args.overwrite,
        )
    )


def _aus_bildern(args) -> int:
    ziel = args.ausgabe or args.eingaben[0].with_suffix(".pdf")
    if ziel.suffix.lower() != ".pdf":
        raise BedienFehler(f"Die Ausgabe '{ziel}' muss auf .pdf enden.")
    return _gespeichert(
        [
            pdf.aus_bildern(
                args.eingaben, ziel, seitengroesse=args.seitengroesse, overwrite=args.overwrite
            )
        ]
    )


def _verkleinern(args) -> int:
    ziel = _ziel(args, args.eingabe, "klein")
    pfad, vorher, nachher = pdf.verkleinern(
        args.eingabe,
        ziel,
        qualitaet=args.qualitaet,
        passwort=args.passwort,
        overwrite=args.overwrite,
    )
    print(f"Gespeichert: {pfad} ({vorher / 1e6:.2f} MB → {nachher / 1e6:.2f} MB)")
    return 0

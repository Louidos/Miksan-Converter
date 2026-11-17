"""Befehle der weiteren Bild-Werkzeuge: ``wasserzeichen``, ``umbenennen``, ``animation``,
``iconset``, ``zuschneiden``. Wird von ``cli.py`` eingebunden."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .bearbeiten import zuschnitt_parsen
from .fehler import BedienFehler, MiksanFehler
from .stapel import dateien_sammeln
from .werkzeuge import animation, iconset, umbenennen, wasserzeichen, zuschneiden
from .werkzeuge._gemeinsam import ziel_format


def _verbose(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-v", "--verbose", "--ausfuehrlich", action="store_true", help="Details anzeigen"
    )


def _overwrite(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--overwrite", "--ueberschreiben", action="store_true", help="vorhandene Dateien ersetzen"
    )


def _mehrere_dateien(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pfade", nargs="+", metavar="PFAD", help="Bilder, Ordner oder Muster")
    parser.add_argument(
        "-o",
        "--ausgabe",
        "--output",
        dest="ausgabe",
        type=Path,
        help="Ausgabedatei (bei einem Bild mit Endung) oder Ausgabeordner",
    )
    parser.add_argument("--to", metavar="FORMAT", help="Zielformat (Standard: wie das Original)")
    parser.add_argument("-r", "--rekursiv", action="store_true", help="Unterordner einbeziehen")
    _overwrite(parser)
    _verbose(parser)


def befehle_anlegen(befehle) -> None:
    p = befehle.add_parser(
        "wasserzeichen",
        aliases=["watermark"],
        help="Text oder Logo als Wasserzeichen auf Bilder legen",
        description="Legt einen Text oder ein Logo auf Bilder. Ohne -o entsteht "
        "<name>-wasserzeichen neben dem Original.",
    )
    _mehrere_dateien(p)
    art = p.add_mutually_exclusive_group(required=True)
    art.add_argument("--text", help="Text des Wasserzeichens, z. B. '© Miksan 2026'")
    art.add_argument("--logo", type=Path, help="Bild (am besten PNG mit Transparenz)")
    p.add_argument(
        "--position",
        choices=wasserzeichen.POSITIONEN,
        default=wasserzeichen.STANDARD_POSITION,
        help="eine der neun Positionen oder gekachelt (Standard: unten-rechts)",
    )
    p.add_argument(
        "--groesse", type=float, default=20, help="Breite in %% des Bildes (Standard 20)"
    )
    p.add_argument("--deckkraft", type=int, default=50, help="0–100 %% (Standard 50)")
    p.add_argument("--farbe", default="#ffffff", help="Textfarbe (Standard: weiss)")
    p.set_defaults(ausfuehren=_wasserzeichen)

    p = befehle.add_parser(
        "umbenennen",
        aliases=["rename"],
        help="Dateien nach einem Muster umbenennen ({name}, {nr}, {datum}, {breite}, {hoehe})",
        description="Benennt Dateien nach einem Muster um. Vorher werden alle neuen Namen "
        "geprüft; bei einem Konflikt wird abgebrochen und keine Datei verändert.",
    )
    p.add_argument("pfade", nargs="+", metavar="PFAD", help="Dateien, Ordner oder Muster")
    p.add_argument("--muster", required=True, help="z. B. 'urlaub-{datum}-{nr}'")
    p.add_argument("--start", type=int, default=1, help="erste Nummer für {nr} (Standard 1)")
    p.add_argument(
        "-o",
        "--ausgabe",
        dest="ausgabe",
        type=Path,
        help="statt umzubenennen mit neuem Namen in diesen Ordner kopieren",
    )
    p.add_argument(
        "--probe", "--dry-run", action="store_true", help="nur anzeigen, nichts verändern"
    )
    p.add_argument("-r", "--rekursiv", action="store_true", help="Unterordner einbeziehen")
    _verbose(p)
    p.set_defaults(ausfuehren=_umbenennen)

    haupt = befehle.add_parser(
        "animation", help="GIF/WebP aus Bildern erstellen oder in Einzelbilder zerlegen"
    )
    unter = haupt.add_subparsers(dest="animation_befehl", metavar="<aktion>")
    p = unter.add_parser("erstellen", aliases=["create"], help="Animation aus Bildern")
    p.add_argument("bilder", nargs="+", type=Path, metavar="BILD", help="in dieser Reihenfolge")
    p.add_argument(
        "-o", "--ausgabe", dest="ausgabe", type=Path, required=True, help="z. B. anim.gif"
    )
    p.add_argument("--dauer", type=int, default=animation.STANDARD_DAUER, help="ms pro Bild")
    p.add_argument("--schleife", type=int, default=0, help="Wiederholungen, 0 = endlos")
    _overwrite(p)
    _verbose(p)
    p.set_defaults(ausfuehren=_animation_erstellen)
    p = unter.add_parser("zerlegen", aliases=["split"], help="Animation in Einzelbilder")
    p.add_argument("eingabe", type=Path, metavar="ANIMATION")
    p.add_argument("-o", "--ausgabe", dest="ausgabe", type=Path, help="Ausgabeordner")
    p.add_argument("--format", dest="bildformat", default="png", help="Format der Einzelbilder")
    _overwrite(p)
    _verbose(p)
    p.set_defaults(ausfuehren=_animation_zerlegen)
    haupt.set_defaults(ausfuehren=lambda args: _hilfe(haupt))

    p = befehle.add_parser(
        "iconset",
        aliases=["icons"],
        help="favicon.ico und PNG-Icons (16–512 px) aus einem Bild",
    )
    p.add_argument("eingabe", type=Path, metavar="BILD")
    p.add_argument("-o", "--ausgabe", dest="ausgabe", type=Path, help="Ausgabeordner")
    _overwrite(p)
    _verbose(p)
    p.set_defaults(ausfuehren=_iconset)

    p = befehle.add_parser(
        "zuschneiden",
        aliases=["crop"],
        help="mit Seitenverhältnis zuschneiden, z. B. für Profilbilder",
        description="Schneidet Bilder zu – mittig mit festem Verhältnis, mit einem Bereich in "
        "Pixeln und optional auf feste Zielmasse. Ohne -o entsteht <name>-zugeschnitten.",
    )
    _mehrere_dateien(p)
    p.add_argument("--verhaeltnis", help="z. B. 1:1, 4:3, 16:9 (Standard: frei)")
    p.add_argument("--bereich", help="x,y,breite,hoehe in Pixeln (sonst mittig)")
    ziel = p.add_mutually_exclusive_group()
    ziel.add_argument("--ziel", help="feste Zielmasse, z. B. 400x400")
    ziel.add_argument("--vorlage", choices=list(zuschneiden.VORLAGEN), help="Zielmasse-Vorlage")
    p.set_defaults(ausfuehren=_zuschneiden)


def _hilfe(parser: argparse.ArgumentParser) -> int:
    parser.print_help()
    return 2


def _eingaben(args) -> list[Path]:
    dateien, fehler = dateien_sammeln(args.pfade, rekursiv=getattr(args, "rekursiv", False))
    for _pfad, meldung in fehler:
        print(f"Fehler: {meldung}", file=sys.stderr)
    if not dateien and not fehler:
        raise MiksanFehler("Keine Bilddateien gefunden.")
    if fehler and not dateien:
        raise MiksanFehler("Keine verarbeitbaren Dateien.")
    return [datei.pfad for datei in dateien]


def _je_datei(args, zusatz: str, arbeit) -> int:
    """Ein Bild mit Ausgabedatei oder viele Bilder (Ausgabeordner/neben dem Original)."""
    eingaben = _eingaben(args)
    einzeln = len(eingaben) == 1 and args.ausgabe is not None and args.ausgabe.suffix
    fehler = 0
    for eingabe in eingaben:
        if einzeln:
            ziel = args.ausgabe
        elif args.ausgabe is not None:
            args.ausgabe.mkdir(parents=True, exist_ok=True)
            ziel = args.ausgabe / f"{eingabe.stem}{ziel_format(eingabe, None, args.to).endung}"
        else:
            ziel = None
        try:
            ergebnis = arbeit(eingabe, ziel)
        except BedienFehler:
            raise
        except MiksanFehler as meldung:
            print(f"Fehler: {meldung}", file=sys.stderr)
            fehler += 1
            continue
        for hinweis in ergebnis.hinweise:
            print(f"Hinweis: {hinweis}", file=sys.stderr)
        print(f"Gespeichert: {ergebnis.ausgabe}")
    return 1 if fehler else 0


def _wasserzeichen(args) -> int:
    return _je_datei(
        args,
        "wasserzeichen",
        lambda eingabe, ziel: wasserzeichen.wasserzeichen(
            eingabe,
            ziel,
            text=args.text,
            logo=args.logo,
            position=args.position,
            groesse=args.groesse,
            deckkraft=args.deckkraft,
            farbe=args.farbe,
            to=args.to,
            overwrite=args.overwrite,
        ),
    )


def _umbenennen(args) -> int:
    dateien, fehler = dateien_sammeln(args.pfade, rekursiv=args.rekursiv)
    if fehler:
        raise MiksanFehler(fehler[0][1])
    pfade = sorted((d.pfad for d in dateien), key=lambda p: (str(p.parent), p.name.lower()))
    if args.probe:
        paare = umbenennen.neue_namen(
            pfade, args.muster, start=args.start, ziel_ordner=args.ausgabe
        )
        for paar in paare:
            print(f"{paar.alt.name} -> {paar.neu.name}")
        gruende = umbenennen.konflikte(paare)
        for grund in gruende:
            print(f"Konflikt: {grund}", file=sys.stderr)
        return 2 if gruende else 0
    for paar in umbenennen.umbenennen(
        pfade, args.muster, start=args.start, ziel_ordner=args.ausgabe
    ):
        if not paar.unveraendert:
            print(f"{paar.alt.name} -> {paar.neu}")
    return 0


def _animation_erstellen(args) -> int:
    ziel = animation.erstellen(
        args.bilder,
        args.ausgabe,
        dauer=args.dauer,
        schleife=args.schleife,
        overwrite=args.overwrite,
    )
    print(f"Gespeichert: {ziel}")
    return 0


def _animation_zerlegen(args) -> int:
    for ziel in animation.zerlegen(
        args.eingabe, args.ausgabe, bildformat=args.bildformat, overwrite=args.overwrite
    ):
        print(f"Gespeichert: {ziel}")
    return 0


def _iconset(args) -> int:
    for ziel in iconset.erstellen(args.eingabe, args.ausgabe, overwrite=args.overwrite):
        print(f"Gespeichert: {ziel}")
    return 0


def _zuschneiden(args) -> int:
    verhaeltnis = zuschneiden.verhaeltnis_parsen(args.verhaeltnis)
    bereich = zuschnitt_parsen(args.bereich) if args.bereich else None
    ziel = None
    if args.ziel:
        ziel = zuschneiden.masse_parsen(args.ziel)
    elif args.vorlage:
        ziel = zuschneiden.VORLAGEN[args.vorlage][1]
    return _je_datei(
        args,
        "zugeschnitten",
        lambda eingabe, ausgabe: zuschneiden.zuschneiden(
            eingabe,
            ausgabe,
            bereich=bereich,
            verhaeltnis=verhaeltnis,
            ziel=ziel,
            to=args.to,
            overwrite=args.overwrite,
        ),
    )

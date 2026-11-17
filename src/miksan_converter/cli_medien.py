"""Befehle ``miksan video`` und ``miksan audio`` (ffmpeg, Extra [medien]).

Wird von ``cli.py`` eingebunden. Dateien werden nacheinander verarbeitet (ffmpeg nutzt selbst
alle Prozessorkerne); der Fortschritt steht in Prozent auf stderr.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import medien
from .bearbeiten import groesse_parsen
from .fehler import BedienFehler, MiksanFehler


def _fortschritt(name: str):
    if not sys.stderr.isatty():
        return None

    def melden(anteil: float) -> None:
        print(f"\r{name}: {anteil * 100:5.1f} %", end="", file=sys.stderr, flush=True)

    return melden


def _gemeinsam(parser: argparse.ArgumentParser, *, mehrere: bool = True) -> None:
    if mehrere:
        parser.add_argument("eingaben", nargs="+", type=Path, metavar="DATEI")
    else:
        parser.add_argument("eingabe", type=Path, metavar="DATEI")
    parser.add_argument(
        "-o",
        "--ausgabe",
        "--output",
        dest="ausgabe",
        type=Path,
        help="Ausgabedatei (bei einer Datei) oder Ausgabeordner",
    )
    parser.add_argument(
        "--overwrite", "--ueberschreiben", action="store_true", help="vorhandene Dateien ersetzen"
    )
    parser.add_argument(
        "-v", "--verbose", "--ausfuehrlich", action="store_true", help="Details anzeigen"
    )


def _zeiten(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start", help="ab dieser Zeit, z. B. 1:05 oder 65")
    parser.add_argument("--ende", help="bis zu dieser Zeit, z. B. 2:30")


def befehle_anlegen(befehle) -> None:
    video = befehle.add_parser(
        "video",
        help="Video umwandeln, kürzen, verkleinern, in GIF … (ffmpeg, Extra [medien])",
        description="Video-Werkzeuge mit ffmpeg, lokal. Das Original wird nie verändert.",
    )
    unter = video.add_subparsers(dest="video_befehl", metavar="<aktion>")

    p = unter.add_parser("umwandeln", aliases=["convert"], help="in MP4, WebM, MKV, MOV, GIF")
    _gemeinsam(p)
    p.add_argument("--to", choices=medien.VIDEO_ZIELE, help="Zielformat (Standard: mp4)")
    p.add_argument("--qualitaet", choices=medien.QUALITAETEN, default=medien.STANDARD_QUALITAET)
    p.add_argument("--crf", type=int, help="statt Qualität: CRF-Wert (kleiner = besser)")
    p.add_argument("--aufloesung", type=int, choices=medien.AUFLOESUNGEN, help="z. B. 720")
    p.add_argument("--fps", type=float, help="Bildrate, z. B. 30")
    p.add_argument("--ohne-ton", action="store_true", help="Ton entfernen")
    _zeiten(p)
    p.set_defaults(ausfuehren=_video_umwandeln)

    p = unter.add_parser("kuerzen", aliases=["trim"], help="Teil herausschneiden")
    _gemeinsam(p)
    _zeiten(p)
    p.add_argument(
        "--genau",
        action="store_true",
        help="neu kodieren (bildgenau, langsamer); sonst ohne Neukodierung",
    )
    p.set_defaults(ausfuehren=_kuerzen)

    p = unter.add_parser("verkleinern", aliases=["shrink"], help="auf Zielgrösse bringen")
    _gemeinsam(p)
    p.add_argument("--zielgroesse", required=True, help="z. B. 10MB (Discord, Mail)")
    p.add_argument("--aufloesung", type=int, choices=medien.AUFLOESUNGEN)
    p.set_defaults(ausfuehren=_verkleinern)

    p = unter.add_parser("gif", help="Video → GIF mit eigener Farbpalette")
    _gemeinsam(p)
    p.add_argument("--breite", type=int, default=480, help="Breite in Pixeln (Standard 480)")
    p.add_argument("--fps", type=float, default=12, help="Bildrate (Standard 12)")
    _zeiten(p)
    p.set_defaults(ausfuehren=_gif)

    p = unter.add_parser("ton", aliases=["audio"], help="Ton aus dem Video herausziehen")
    _gemeinsam(p)
    p.add_argument("--to", choices=medien.AUDIO_ZIELE, help="Tonformat (Standard: mp3)")
    p.add_argument("--qualitaet", choices=medien.QUALITAETEN, default=medien.STANDARD_QUALITAET)
    p.set_defaults(ausfuehren=_ton)

    p = unter.add_parser("bild", aliases=["frame"], help="Einzelbild als PNG/JPEG speichern")
    _gemeinsam(p, mehrere=False)
    p.add_argument("--zeit", default="0", help="Zeitpunkt, z. B. 0:12 (Standard: Anfang)")
    p.set_defaults(ausfuehren=_bild)
    video.set_defaults(ausfuehren=lambda args: _hilfe(video))

    p = befehle.add_parser(
        "audio",
        help="Ton umwandeln: MP3, WAV, FLAC, OGG, Opus, M4A (ffmpeg, Extra [medien])",
        description="Wandelt Tondateien um (auch den Ton von Videos). Titel, Interpret und "
        "Cover bleiben erhalten (Cover bei MP3, M4A, FLAC).",
    )
    _gemeinsam(p)
    p.add_argument("--to", choices=medien.AUDIO_ZIELE, help="Zielformat (Standard: mp3)")
    p.add_argument("--qualitaet", choices=medien.QUALITAETEN, default=medien.STANDARD_QUALITAET)
    p.add_argument("--bitrate", help="feste Bitrate, z. B. 192k")
    p.add_argument("--normalisieren", action="store_true", help="Lautstärke angleichen (EBU R128)")
    _zeiten(p)
    p.set_defaults(ausfuehren=_audio)


def _hilfe(parser: argparse.ArgumentParser) -> int:
    parser.print_help()
    return 2


def _je_datei(args, endung_fuer, arbeit) -> int:
    """Eine Datei mit Ausgabedatei, sonst nacheinander in den Ausgabeordner/neben das Original."""
    eingaben = args.eingaben
    einzeln = len(eingaben) == 1 and args.ausgabe is not None and args.ausgabe.suffix
    medien.ffmpeg()  # ohne ffmpeg sofort mit Rückgabecode 3
    fehler = 0
    for eingabe in eingaben:
        if einzeln:
            ziel = args.ausgabe
        elif args.ausgabe is not None:
            args.ausgabe.mkdir(parents=True, exist_ok=True)
            ziel = args.ausgabe / f"{eingabe.stem}.{endung_fuer(eingabe)}"
        else:
            ziel = None
        try:
            ergebnis = arbeit(eingabe, ziel, _fortschritt(eingabe.name))
        except BedienFehler:
            raise
        except MiksanFehler as meldung:
            print(f"\nFehler: {meldung}" if sys.stderr.isatty() else f"Fehler: {meldung}",
                  file=sys.stderr)  # fmt: skip
            fehler += 1
            continue
        if sys.stderr.isatty():
            print(file=sys.stderr)
        print(f"Gespeichert: {ergebnis}")
    return 1 if fehler else 0


def _video_umwandeln(args) -> int:
    start, ende = medien.zeit_parsen(args.start), medien.zeit_parsen(args.ende)
    return _je_datei(
        args,
        lambda e: args.to or "mp4",
        lambda e, z, f: medien.video_umwandeln(
            e,
            z,
            ziel=args.to,
            qualitaet=args.qualitaet,
            crf=args.crf,
            aufloesung=args.aufloesung,
            fps=args.fps,
            ohne_ton=args.ohne_ton,
            start=start,
            ende=ende,
            fortschritt=f,
            overwrite=args.overwrite,
        ),
    )


def _kuerzen(args) -> int:
    start, ende = medien.zeit_parsen(args.start), medien.zeit_parsen(args.ende)
    return _je_datei(
        args,
        lambda e: e.suffix.lstrip(".") or "mp4",
        lambda e, z, f: medien.kuerzen(
            e,
            z,
            start=start,
            ende=ende,
            neu_kodieren=args.genau,
            fortschritt=f,
            overwrite=args.overwrite,
        ),
    )


def _verkleinern(args) -> int:
    ziel_byte = groesse_parsen(args.zielgroesse)
    return _je_datei(
        args,
        lambda e: "mp4",
        lambda e, z, f: medien.verkleinern(
            e,
            z,
            ziel_byte=ziel_byte,
            aufloesung=args.aufloesung,
            fortschritt=f,
            overwrite=args.overwrite,
        ),
    )


def _gif(args) -> int:
    start, ende = medien.zeit_parsen(args.start), medien.zeit_parsen(args.ende)
    return _je_datei(
        args,
        lambda e: "gif",
        lambda e, z, f: medien.zu_gif(
            e,
            z,
            breite=args.breite,
            fps=args.fps,
            start=start,
            ende=ende,
            fortschritt=f,
            overwrite=args.overwrite,
        ),
    )


def _ton(args) -> int:
    return _je_datei(
        args,
        lambda e: args.to or "mp3",
        lambda e, z, f: medien.audio_umwandeln(
            e, z, ziel=args.to, qualitaet=args.qualitaet, fortschritt=f, overwrite=args.overwrite
        ),
    )


def _audio(args) -> int:
    start, ende = medien.zeit_parsen(args.start), medien.zeit_parsen(args.ende)
    return _je_datei(
        args,
        lambda e: args.to or "mp3",
        lambda e, z, f: medien.audio_umwandeln(
            e,
            z,
            ziel=args.to,
            qualitaet=args.qualitaet,
            bitrate=args.bitrate,
            normalisieren=args.normalisieren,
            start=start,
            ende=ende,
            fortschritt=f,
            overwrite=args.overwrite,
        ),
    )


def _bild(args) -> int:
    medien.ffmpeg()
    ziel = medien.einzelbild(
        args.eingabe,
        args.ausgabe,
        zeit=medien.zeit_parsen(args.zeit) or 0.0,
        overwrite=args.overwrite,
    )
    print(f"Gespeichert: {ziel}")
    return 0

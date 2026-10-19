"""Eingaben, die optionale Extras brauchen: SVG (resvg) und Kamera-RAW (rawpy)."""

from __future__ import annotations

import io
import zlib
from pathlib import Path

from PIL import Image

from .fehler import ExtraFehlt, MiksanFehler


def svg_laden(pfad: Path) -> Image.Image:
    """Rendert eine SVG- oder SVGZ-Datei in ein RGBA-Rasterbild."""
    try:
        import resvg_py
    except ImportError as fehler:
        raise ExtraFehlt("svg", "SVG-Dateien zu lesen") from fehler

    daten = pfad.read_bytes()
    if daten[:2] == b"\x1f\x8b":
        try:
            daten = zlib.decompress(daten, 31)
        except zlib.error as fehler:
            raise MiksanFehler(f"'{pfad}' ist beschädigt oder unvollständig.") from fehler
    try:
        png = resvg_py.svg_to_bytes(
            svg_string=daten.decode("utf-8-sig"),
            resources_dir=str(pfad.resolve().parent),
        )
    except (ValueError, UnicodeDecodeError) as fehler:
        raise MiksanFehler(f"'{pfad}' ist kein gültiges SVG: {fehler}") from fehler
    bild = Image.open(io.BytesIO(bytes(png)))
    bild.load()
    return bild


def raw_laden(pfad: Path) -> Image.Image:
    """Entwickelt eine Kamera-RAW-Datei mit Kamera-Weissabgleich zu einem 8-Bit-RGB-Bild."""
    try:
        import rawpy
    except ImportError as fehler:
        raise ExtraFehlt("raw", "Kamera-RAW-Dateien zu lesen") from fehler

    try:
        with rawpy.imread(str(pfad)) as raw:
            pixel = raw.postprocess(use_camera_wb=True, output_bps=8)
    except Exception as fehler:  # rawpy hat viele eigene Fehlerklassen
        raise MiksanFehler(f"'{pfad}' konnte als RAW nicht gelesen werden: {fehler}") from fehler
    return Image.fromarray(pixel)

from pathlib import Path

import pytest
from PIL import Image

from miksan_converter.cli import main
from miksan_converter.convert import umwandeln
from miksan_converter.fehler import BedienFehler, MiksanFehler


def test_png_nach_jpeg(png_datei: Path, tmp_path: Path):
    ziel = tmp_path / "foto.jpg"
    assert main(["convert", str(png_datei), str(ziel)]) == 0
    with Image.open(ziel) as bild:
        assert bild.format == "JPEG"
        assert bild.size == (40, 30)
        assert bild.mode == "RGB"
        # Transparenter Bereich wird weiss statt schwarz
        assert bild.getpixel((5, 5)) == pytest.approx((255, 255, 255), abs=3)


def test_zielformat_mit_to(png_datei: Path):
    assert main(["convert", str(png_datei), "--to", "webp"]) == 0
    ziel = png_datei.with_suffix(".webp")
    with Image.open(ziel) as bild:
        assert bild.format == "WEBP"


def test_format_am_inhalt_erkannt(png_datei: Path, tmp_path: Path):
    falsch = tmp_path / "eigentlich_png.jpg"
    falsch.write_bytes(png_datei.read_bytes())
    ergebnis = umwandeln(falsch, tmp_path / "richtig.bmp")
    assert ergebnis.eingabe_format == "png"
    with Image.open(ergebnis.ausgabe) as bild:
        assert bild.format == "BMP"


def test_vorhandene_datei_bleibt_unveraendert(png_datei: Path, tmp_path: Path, capsys):
    ziel = tmp_path / "vorhanden.jpg"
    ziel.write_bytes(b"alt")
    assert main(["convert", str(png_datei), str(ziel)]) == 1
    assert ziel.read_bytes() == b"alt"
    fehler = capsys.readouterr().err
    assert "gibt es schon" in fehler and "--overwrite" in fehler
    assert "Traceback" not in fehler


def test_overwrite_ersetzt_datei(png_datei: Path, tmp_path: Path):
    ziel = tmp_path / "vorhanden.jpg"
    ziel.write_bytes(b"alt")
    assert main(["convert", str(png_datei), str(ziel), "--overwrite"]) == 0
    with Image.open(ziel) as bild:
        assert bild.format == "JPEG"


def test_original_wird_nie_ueberschrieben(png_datei: Path):
    vorher = png_datei.read_bytes()
    with pytest.raises(BedienFehler):
        umwandeln(png_datei, png_datei, overwrite=True)
    assert png_datei.read_bytes() == vorher


def test_fehlende_datei_gibt_meldung(tmp_path: Path, capsys):
    assert main(["convert", str(tmp_path / "gibtsnicht.png"), "--to", "jpg"]) == 1
    assert "nicht gefunden" in capsys.readouterr().err


def test_kein_bild(tmp_path: Path, capsys):
    text = tmp_path / "notiz.png"
    text.write_text("kein Bild")
    assert main(["convert", str(text), "--to", "jpg"]) == 1
    fehler = capsys.readouterr().err
    assert "kein unterstütztes Bild" in fehler
    assert "Traceback" not in fehler


def test_verbose_zeigt_details(tmp_path: Path, capsys):
    text = tmp_path / "notiz.png"
    text.write_text("kein Bild")
    assert main(["convert", str(text), "--to", "jpg", "--verbose"]) == 1
    assert "Traceback" in capsys.readouterr().err


def test_unbekanntes_zielformat(png_datei: Path, capsys):
    assert main(["convert", str(png_datei), "--to", "xyz"]) == 2
    assert "Unbekanntes Format" in capsys.readouterr().err


def test_endung_widerspricht_to(png_datei: Path, tmp_path: Path):
    with pytest.raises(BedienFehler):
        umwandeln(png_datei, tmp_path / "a.png", to="jpg")


def test_ohne_ziel_ist_bedienfehler(png_datei: Path):
    with pytest.raises(BedienFehler):
        umwandeln(png_datei)


def test_unbekannte_endung_ohne_to(png_datei: Path, tmp_path: Path):
    with pytest.raises(MiksanFehler, match="--to"):
        umwandeln(png_datei, tmp_path / "ziel.xyz")

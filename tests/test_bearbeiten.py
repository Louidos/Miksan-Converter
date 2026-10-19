"""Bilder bearbeiten: Grösse, Zuschnitt, Drehen, Spiegeln, Qualität, Zielgrösse, Metadaten."""

from pathlib import Path

import pytest
from PIL import Image

from miksan_converter.bearbeiten import Bearbeitung, groesse_parsen, zuschnitt_parsen
from miksan_converter.cli import main
from miksan_converter.fehler import BedienFehler

ROT, BLAU = (220, 0, 0), (0, 0, 220)


def _nah(farbe, erwartet, toleranz=40) -> bool:
    return all(abs(a - b) <= toleranz for a, b in zip(farbe[:3], erwartet[:3], strict=True))


@pytest.fixture(scope="module")
def gross_jpg(tmp_path_factory) -> Path:
    """Fotoähnliches, grosses JPEG (2400x1600, mehrere MB)."""
    pfad = tmp_path_factory.mktemp("gross") / "gross.jpg"
    kanaele = [Image.effect_noise((2400, 1600), 60 + 20 * i) for i in range(3)]
    verlauf = Image.linear_gradient("L").resize((2400, 1600))
    bild = Image.merge("RGB", [Image.blend(k, verlauf, 0.5) for k in kanaele])
    bild.save(pfad, quality=95)
    return pfad


@pytest.fixture
def rot_blau(tmp_path: Path) -> Path:
    """40x20: links rot, rechts blau."""
    pfad = tmp_path / "rotblau.png"
    bild = Image.new("RGB", (40, 20), ROT)
    bild.paste(BLAU, (20, 0, 40, 20))
    bild.save(pfad)
    return pfad


def _oeffnen(pfad: Path) -> Image.Image:
    bild = Image.open(pfad)
    bild.load()
    return bild


# --- Grösse -------------------------------------------------------------------------


def test_max_1200_laengste_seite_und_verhaeltnis(gross_jpg, tmp_path: Path):
    ziel = tmp_path / "klein.webp"
    assert main(["convert", str(gross_jpg), str(ziel), "--max", "1200"]) == 0
    bild = _oeffnen(ziel)
    assert bild.format == "WEBP"
    assert bild.size == (1200, 800)


def test_max_vergroessert_nicht(rot_blau, tmp_path: Path):
    ziel = tmp_path / "gleich.png"
    assert main(["convert", str(rot_blau), str(ziel), "--max", "1000"]) == 0
    assert _oeffnen(ziel).size == (40, 20)


@pytest.mark.parametrize(
    "optionen, groesse",
    [
        (["--breite", "80"], (80, 40)),
        (["--hoehe", "10"], (20, 10)),
        (["--breite", "30", "--hoehe", "30"], (30, 30)),
        (["--width", "10", "--max", "8"], (8, 4)),
    ],
)
def test_breite_und_hoehe(rot_blau, tmp_path: Path, optionen, groesse):
    ziel = tmp_path / "ergebnis.png"
    assert main(["convert", str(rot_blau), str(ziel), *optionen]) == 0
    assert _oeffnen(ziel).size == groesse


# --- Zuschnitt, Drehen, Spiegeln ------------------------------------------------------


def test_zuschneiden(rot_blau, tmp_path: Path):
    ziel = tmp_path / "ausschnitt.png"
    assert main(["convert", str(rot_blau), str(ziel), "--zuschneiden", "15,5,10,10"]) == 0
    bild = _oeffnen(ziel)
    assert bild.size == (10, 10)
    assert _nah(bild.getpixel((2, 5)), ROT) and _nah(bild.getpixel((8, 5)), BLAU)


def test_zuschneiden_ausserhalb(rot_blau, tmp_path: Path, capsys):
    assert main(["convert", str(rot_blau), str(tmp_path / "x.png"), "--crop", "30,0,20,20"]) == 2
    assert "ausserhalb" in capsys.readouterr().err
    assert not (tmp_path / "x.png").exists()


@pytest.mark.parametrize("text", ["1,2,3", "a,b,c,d", "0,0,0,5", "-1,0,5,5"])
def test_zuschneiden_ungueltig(text):
    with pytest.raises(BedienFehler):
        zuschnitt_parsen(text)


def test_drehen_90_im_uhrzeigersinn(rot_blau, tmp_path: Path):
    ziel = tmp_path / "gedreht.png"
    assert main(["convert", str(rot_blau), str(ziel), "--drehen", "90"]) == 0
    bild = _oeffnen(ziel)
    assert bild.size == (20, 40)
    assert _nah(bild.getpixel((10, 5)), ROT) and _nah(bild.getpixel((10, 35)), BLAU)


def test_drehen_270(rot_blau, tmp_path: Path):
    ziel = tmp_path / "gedreht.png"
    assert main(["convert", str(rot_blau), str(ziel), "--rotate", "270"]) == 0
    bild = _oeffnen(ziel)
    assert _nah(bild.getpixel((10, 5)), BLAU) and _nah(bild.getpixel((10, 35)), ROT)


def test_drehen_ungueltig(rot_blau, tmp_path: Path):
    with pytest.raises(SystemExit):
        main(["convert", str(rot_blau), str(tmp_path / "x.png"), "--drehen", "45"])


@pytest.mark.parametrize("richtung, links_oben", [("h", BLAU), ("v", ROT)])
def test_spiegeln(rot_blau, tmp_path: Path, richtung, links_oben):
    ziel = tmp_path / "gespiegelt.png"
    assert main(["convert", str(rot_blau), str(ziel), "--spiegeln", richtung]) == 0
    assert _nah(_oeffnen(ziel).getpixel((2, 2)), links_oben)


def test_reihenfolge_zuschnitt_vor_drehen_vor_groesse(rot_blau, tmp_path: Path):
    ziel = tmp_path / "ergebnis.png"
    befehl = ["convert", str(rot_blau), str(ziel)]
    befehl += ["--zuschneiden", "0,0,30,20", "--drehen", "90", "--breite", "10"]
    assert main(befehl) == 0
    bild = _oeffnen(ziel)
    # Zuschnitt 30x20 -> gedreht 20x30 -> Breite 10 -> 10x15
    assert bild.size == (10, 15)
    assert _nah(bild.getpixel((5, 2)), ROT) and _nah(bild.getpixel((5, 13)), BLAU)


def test_animation_bleibt_beim_skalieren(testbilder, tmp_path: Path):
    ziel = tmp_path / "klein.gif"
    assert main(["convert", str(testbilder["animiert_gif"]), str(ziel), "--max", "10"]) == 0
    bild = _oeffnen(ziel)
    assert bild.n_frames == 3 and bild.size == (10, 5)


# --- Qualität und Zielgrösse --------------------------------------------------------------


def test_qualitaet_macht_datei_kleiner(gross_jpg, tmp_path: Path):
    hoch, tief = tmp_path / "hoch.jpg", tmp_path / "tief.jpg"
    assert main(["convert", str(gross_jpg), str(hoch), "--max", "600", "--qualitaet", "95"]) == 0
    assert main(["convert", str(gross_jpg), str(tief), "--max", "600", "--quality", "20"]) == 0
    assert tief.stat().st_size < hoch.stat().st_size


@pytest.mark.parametrize("endung", [".jpg", ".webp"])
def test_zielgroesse_300kb(gross_jpg, tmp_path: Path, endung):
    ziel = tmp_path / f"komprimiert{endung}"
    assert main(["convert", str(gross_jpg), str(ziel), "--zielgroesse", "300KB"]) == 0
    assert ziel.stat().st_size <= 300_000
    # Die Qualität wird ausgereizt, nicht unnötig klein gewählt
    assert ziel.stat().st_size > 150_000
    assert _oeffnen(ziel).size == (2400, 1600)


def test_zielgroesse_sehr_klein_verkleinert_das_bild(gross_jpg, tmp_path: Path, capsys):
    ziel = tmp_path / "winzig.jpg"
    assert main(["convert", str(gross_jpg), str(ziel), "--target-size", "20KB"]) == 0
    assert ziel.stat().st_size <= 20_000
    assert _oeffnen(ziel).width < 2400
    assert "verkleinert" in capsys.readouterr().err


def test_zielgroesse_bei_verlustfreiem_format(rot_blau, tmp_path: Path, capsys):
    assert main(["convert", str(rot_blau), str(tmp_path / "x.png"), "--zielgroesse", "1KB"]) == 2
    assert "verlustbehaftet" in capsys.readouterr().err


@pytest.mark.parametrize(
    "text, byte",
    [
        ("500KB", 500_000),
        ("500kb", 500_000),
        ("1.5MB", 1_500_000),
        ("2 MiB", 2 * 1024**2),
        ("1234", 1234),
    ],
)
def test_groesse_parsen(text, byte):
    assert groesse_parsen(text) == byte


@pytest.mark.parametrize("text", ["viel", "5GB", "-3KB", ""])
def test_groesse_parsen_ungueltig(text):
    with pytest.raises(BedienFehler):
        groesse_parsen(text)


@pytest.mark.parametrize("wert", ["0", "101"])
def test_qualitaet_ausserhalb(rot_blau, tmp_path: Path, wert):
    assert main(["convert", str(rot_blau), str(tmp_path / "x.jpg"), "--qualitaet", wert]) == 2


def test_qualitaet_und_zielgroesse_zusammen():
    with pytest.raises(BedienFehler):
        Bearbeitung(qualitaet=80, zielgroesse=1000)


# --- Metadaten ----------------------------------------------------------------------------


@pytest.mark.parametrize("endung", [".jpg", ".png", ".webp", ".tif", ".avif", ".heic"])
def test_metadaten_entfernen(testbilder, tmp_path: Path, endung):
    ziel = tmp_path / f"ohne{endung}"
    befehl = ["convert", str(testbilder["exif_jpg"]), str(ziel), "--metadaten-entfernen"]
    assert main(befehl) == 0
    bild = _oeffnen(ziel)
    exif = bild.getexif()
    assert 0x8825 not in exif
    assert not exif.get_ifd(0x8825)
    assert exif.get(0x010F) is None
    # Ausrichtung wurde vorher angewendet: das Bild steht trotzdem richtig
    assert bild.size == (20, 40)
    assert _nah(bild.convert("RGB").getpixel((10, 5)), ROT)


def test_metadaten_bleiben_standardmaessig(testbilder, tmp_path: Path):
    ziel = tmp_path / "mit.jpg"
    assert main(["convert", str(testbilder["exif_jpg"]), str(ziel)]) == 0
    exif = _oeffnen(ziel).getexif()
    assert exif.get_ifd(0x8825).get(1) == "N"


# --- Befehl bearbeiten --------------------------------------------------------------------


def test_bearbeiten_ohne_ausgabe_gleiches_format(gross_jpg, tmp_path: Path):
    quelle = tmp_path / "foto.jpg"
    quelle.write_bytes(gross_jpg.read_bytes())
    assert main(["bearbeiten", str(quelle), "--max", "300"]) == 0
    ziel = tmp_path / "foto-bearbeitet.jpg"
    bild = _oeffnen(ziel)
    assert bild.format == "JPEG" and bild.size == (300, 200)


def test_bearbeiten_mit_ausgabe(rot_blau, tmp_path: Path):
    ziel = tmp_path / "neu.webp"
    assert main(["edit", str(rot_blau), str(ziel), "--drehen", "180"]) == 0
    assert _nah(_oeffnen(ziel).getpixel((2, 2)), BLAU)


def test_bearbeiten_ohne_option(rot_blau, capsys):
    assert main(["bearbeiten", str(rot_blau)]) == 2
    assert "Keine Bearbeitung" in capsys.readouterr().err


def test_bearbeiten_original_unveraendert(rot_blau):
    vorher = rot_blau.read_bytes()
    assert main(["bearbeiten", str(rot_blau), "--drehen", "90"]) == 0
    assert rot_blau.read_bytes() == vorher

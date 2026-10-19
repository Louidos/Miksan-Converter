"""Zuverlässigkeit: Ausrichtung, Farbprofile, Transparenz, Animation, Seiten, Fehlerfälle."""

import io
import sys
import types
from pathlib import Path

import pytest
from PIL import Image

from miksan_converter.cli import main
from miksan_converter.convert import farbe_parsen, laden, umwandeln
from miksan_converter.fehler import BedienFehler, ExtraFehlt, MiksanFehler
from miksan_converter.formats import (
    alle_formate,
    ist_raw_signatur,
    ist_svg,
    markdown_tabelle,
)

from .conftest import testbilder_erzeugen as tb

ROT, BLAU = (220, 0, 0), (0, 0, 220)


def _nah(farbe, erwartet, toleranz=40) -> bool:
    return all(abs(a - b) <= toleranz for a, b in zip(farbe[:3], erwartet[:3], strict=True))


def _icc(pfad: Path) -> bytes:
    with Image.open(pfad) as bild:
        return bild.info["icc_profile"]


# --- HEIC-Handyfoto -------------------------------------------------------------


def test_heic_handyfoto_gedreht_und_farbtreu(testbilder, tmp_path: Path):
    ziel = tmp_path / "handy.jpg"
    assert main(["convert", str(testbilder["handy_heic"]), str(ziel)]) == 0
    with Image.open(ziel) as bild:
        assert bild.format == "JPEG"
        # quer gespeichert (40x20) mit Ausrichtung 6 -> hochkant
        assert bild.size == (20, 40)
        # 90° im Uhrzeigersinn: die linke (rote) Hälfte liegt jetzt oben
        assert _nah(bild.getpixel((10, 5)), ROT)
        assert _nah(bild.getpixel((10, 35)), BLAU)
        assert bild.info.get("icc_profile") == _icc(testbilder["handy_heic"])
        exif = bild.getexif()
        assert exif.get(0x0112, 1) == 1
        assert exif.get(0x010F) == "Testkamera"


def test_jpeg_exif_ausrichtung_wird_angewendet(testbilder, tmp_path: Path):
    ziel = tmp_path / "gedreht.png"
    umwandeln(testbilder["exif_jpg"], ziel)
    with Image.open(ziel) as bild:
        assert bild.size == (20, 40)
        assert _nah(bild.getpixel((10, 5)), ROT)
        assert bild.getexif().get(0x0112, 1) == 1


@pytest.mark.parametrize("ziel_name", ["jpeg", "png", "webp", "tiff", "avif", "heif"])
def test_icc_und_exif_bleiben_erhalten(testbilder, tmp_path: Path, ziel_name):
    endung = {"jpeg": ".jpg", "tiff": ".tif", "heif": ".heic"}.get(ziel_name, f".{ziel_name}")
    ziel = tmp_path / f"ergebnis{endung}"
    umwandeln(testbilder["exif_jpg"], ziel)
    with Image.open(ziel) as bild:
        assert bild.info.get("icc_profile") == _icc(testbilder["exif_jpg"])
        assert bild.getexif().get(0x010F) == "Testkamera"


# --- Transparenz und Hintergrund ----------------------------------------------------


def test_transparentes_png_nach_jpeg_weiss(testbilder, tmp_path: Path):
    ziel = tmp_path / "weiss.jpg"
    assert main(["convert", str(testbilder["transparent_png"]), str(ziel)]) == 0
    with Image.open(ziel) as bild:
        assert _nah(bild.getpixel((2, 2)), (255, 255, 255), 5)
        assert _nah(bild.getpixel((20, 12)), tb.FARBE)


def test_transparentes_png_nach_jpeg_schwarz(testbilder, tmp_path: Path):
    ziel = tmp_path / "schwarz.jpg"
    befehl = ["convert", str(testbilder["transparent_png"]), str(ziel), "--background", "#000000"]
    assert main(befehl) == 0
    with Image.open(ziel) as bild:
        assert _nah(bild.getpixel((2, 2)), (0, 0, 0), 5)


@pytest.mark.parametrize(
    "text, erwartet",
    [
        ("#ff0000", (255, 0, 0)),
        ("weiss", (255, 255, 255)),
        ("Schwarz", (0, 0, 0)),
        ("blue", (0, 0, 255)),
    ],
)
def test_farbe_parsen(text, erwartet):
    assert farbe_parsen(text) == erwartet


def test_falsche_farbe(testbilder, tmp_path: Path, capsys):
    befehl = ["convert", str(testbilder["png"]), str(tmp_path / "a.jpg"), "--background", "lila?"]
    assert main(befehl) == 2
    assert "Unbekannte Farbe" in capsys.readouterr().err


# --- Animation -------------------------------------------------------------------


@pytest.mark.parametrize(
    "quelle, ziel_endung",
    [
        ("animiert_gif", ".webp"),
        ("animiert_webp", ".gif"),
        ("animiert_gif", ".png"),
        ("animiert_gif", ".gif"),
    ],
)
def test_animation_bleibt_animiert(testbilder, tmp_path: Path, quelle, ziel_endung):
    ziel = tmp_path / f"animiert{ziel_endung}"
    assert main(["convert", str(testbilder[quelle]), str(ziel)]) == 0
    with Image.open(ziel) as bild:
        assert getattr(bild, "is_animated", False)
        assert bild.n_frames == 3
        farben = []
        for index in range(3):
            bild.seek(index)
            farben.append(bild.convert("RGB").getpixel((5, 5)))
            assert bild.info.get("duration") == 120
    assert _nah(farben[0], (255, 0, 0)) and _nah(farben[1], (0, 255, 0))
    assert _nah(farben[2], (0, 0, 255))


def test_animation_nach_jpeg_gibt_hinweis(testbilder, tmp_path: Path, capsys):
    ziel = tmp_path / "erstes.jpg"
    assert main(["convert", str(testbilder["animiert_gif"]), str(ziel)]) == 0
    assert "--page" in capsys.readouterr().err


# --- Mehrseitige TIFF ----------------------------------------------------------------


def test_mehrseitiges_tiff_behaelt_alle_seiten(testbilder, tmp_path: Path):
    ziel = tmp_path / "kopie.tiff"
    umwandeln(testbilder["mehrseitig"], ziel)
    with Image.open(ziel) as bild:
        assert bild.n_frames == 3


def test_mehrseitiges_tiff_nach_pdf(testbilder, tmp_path: Path):
    ziel = tmp_path / "dokument.pdf"
    umwandeln(testbilder["mehrseitig"], ziel)
    assert ziel.read_bytes().count(b"/Type /Page\n") + ziel.read_bytes().count(b"/Type /Page ") >= 3


def test_seite_waehlen(testbilder, tmp_path: Path):
    ziel = tmp_path / "seite2.png"
    assert main(["convert", str(testbilder["mehrseitig"]), str(ziel), "--page", "2"]) == 0
    with Image.open(ziel) as bild:
        assert _nah(bild.convert("RGB").getpixel((5, 5)), (0, 255, 0))
        assert getattr(bild, "n_frames", 1) == 1


def test_seite_gibt_es_nicht(testbilder, tmp_path: Path, capsys):
    befehl = ["convert", str(testbilder["mehrseitig"]), str(tmp_path / "x.png"), "--page", "9"]
    assert main(befehl) == 2
    assert "3 Seite" in capsys.readouterr().err


def test_seite_null_ist_bedienfehler(testbilder, tmp_path: Path):
    with pytest.raises(SystemExit):
        main(["convert", str(testbilder["png"]), str(tmp_path / "x.jpg"), "--page", "0"])


# --- ICO ----------------------------------------------------------------------------


def test_ico_mit_mehreren_groessen_bleibt_erhalten(testbilder, tmp_path: Path):
    ziel = tmp_path / "kopie.ico"
    umwandeln(testbilder["ico_mehrfach"], ziel)
    with Image.open(ziel) as bild:
        assert bild.info["sizes"] == {(16, 16), (32, 32), (48, 48)}


def test_png_nach_ico_erzeugt_mehrere_groessen(tmp_path: Path):
    quelle = tmp_path / "gross.png"
    Image.new("RGBA", (300, 200), (10, 20, 30, 255)).save(quelle)
    ziel = tmp_path / "symbol.ico"
    umwandeln(quelle, ziel)
    with Image.open(ziel) as bild:
        groessen = bild.info["sizes"]
    assert {(16, 16), (32, 32), (48, 48), (256, 256)} <= groessen
    assert all(b == h for b, h in groessen)


# --- Sonderfälle bei Farbtiefe und Farbraum --------------------------------------------


def test_16bit_wird_skaliert_nicht_abgeschnitten(testbilder, tmp_path: Path):
    ziel = tmp_path / "grau.jpg"
    umwandeln(testbilder["png16"], ziel)
    with Image.open(ziel) as bild:
        assert abs(bild.getpixel((4, 4)) - 128) <= 3


def test_16bit_bleibt_in_png_erhalten(testbilder, tmp_path: Path):
    ziel = tmp_path / "grau.png"
    umwandeln(testbilder["png16"], ziel, overwrite=False)
    with Image.open(ziel) as bild:
        assert bild.mode.startswith("I")
        assert bild.getpixel((4, 4)) == 32768


def test_cmyk_nach_png(testbilder, tmp_path: Path):
    ziel = tmp_path / "rgb.png"
    umwandeln(testbilder["cmyk_jpg"], ziel)
    with Image.open(ziel) as bild:
        assert bild.mode == "RGB"
        assert _nah(bild.getpixel((4, 4)), (255, 0, 0), 60)


# --- Fehlerfälle ---------------------------------------------------------------------


@pytest.mark.parametrize("name", ["kaputt_png", "kaputt_jpg"])
def test_kaputte_datei_klare_meldung_ohne_reste(testbilder, tmp_path: Path, capsys, name):
    ziel = tmp_path / "ergebnis.webp"
    assert main(["convert", str(testbilder[name]), str(ziel)]) == 1
    fehler = capsys.readouterr().err
    assert "beschädigt oder unvollständig" in fehler
    assert "Traceback" not in fehler
    assert list(tmp_path.iterdir()) == []


def test_fehler_beim_schreiben_hinterlaesst_keine_datei(testbilder, tmp_path: Path, monkeypatch):
    def kaputt_speichern(*args, **kwargs):
        raise OSError("Platte voll")

    monkeypatch.setattr(Image.Image, "save", kaputt_speichern)
    with pytest.raises(MiksanFehler, match="Platte voll"):
        umwandeln(testbilder["png"], tmp_path / "x.jpg")
    assert list(tmp_path.iterdir()) == []


def test_nur_lesbares_format_als_ziel(tmp_path: Path):
    with pytest.raises(BedienFehler):
        umwandeln(tmp_path / "x.png", tmp_path / "y.svg")


# --- SVG ------------------------------------------------------------------------------


def test_svg_wird_erkannt():
    assert ist_svg(tb.SVG.encode())
    assert ist_svg(b"\xef\xbb\xbf<svg xmlns='http://www.w3.org/2000/svg'/>")
    assert not ist_svg(b"<html><body>kein svg</body></html>")
    assert not ist_svg(b"\x89PNG\r\n")


def test_svgz_wird_erkannt():
    import gzip

    assert ist_svg(gzip.compress(tb.SVG.encode()))


def test_svg_nach_png(testbilder, tmp_path: Path):
    pytest.importorskip("resvg_py")
    ziel = tmp_path / "vektor.png"
    assert main(["convert", str(testbilder["svg"]), str(ziel)]) == 0
    with Image.open(ziel) as bild:
        assert bild.size == (32, 24)
        rgba = bild.convert("RGBA")
        assert rgba.getpixel((2, 12))[3] == 0
        assert _nah(rgba.getpixel((20, 12)), tb.FARBE, 5)


def test_svg_ohne_extra(testbilder, tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "resvg_py", None)
    assert main(["convert", str(testbilder["svg"]), str(tmp_path / "x.png")]) == 3
    assert "pip install miksan-converter[svg]" in capsys.readouterr().err


# --- RAW ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kopf",
    [
        b"FUJIFILMCCD-RAW 0201",
        b"IIRO\x08\x00\x00\x00",
        b"IIU\x00\x08\x00\x00\x00",
        b"II*\x00\x10\x00\x00\x00CR\x02\x00",
        b"\x00\x00\x00\x18ftypcrx \x00\x00\x00\x01",
    ],
)
def test_raw_signaturen(kopf):
    assert ist_raw_signatur(kopf)


def test_normales_tiff_ist_kein_raw():
    puffer = io.BytesIO()
    Image.new("RGB", (4, 4)).save(puffer, "TIFF")
    assert not ist_raw_signatur(puffer.getvalue())


def _falsches_rawpy(farbe=(10, 200, 30)):
    np = pytest.importorskip("numpy")

    class Raw:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def postprocess(self, **kwargs):
            pixel = np.zeros((6, 8, 3), dtype=np.uint8)
            pixel[:, :] = farbe
            return pixel

    return types.SimpleNamespace(imread=lambda pfad: Raw())


def test_raw_wird_mit_rawpy_entwickelt(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(sys.modules, "rawpy", _falsches_rawpy())
    quelle = tmp_path / "foto.raf"
    quelle.write_bytes(b"FUJIFILMCCD-RAW 0201" + b"\x00" * 100)
    ziel = tmp_path / "foto.jpg"
    ergebnis = umwandeln(quelle, ziel)
    assert ergebnis.eingabe_format == "raw"
    with Image.open(ziel) as bild:
        assert bild.size == (8, 6)
        assert _nah(bild.getpixel((3, 3)), (10, 200, 30), 10)


def test_dng_wird_am_tag_erkannt(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(sys.modules, "rawpy", _falsches_rawpy())
    quelle = tmp_path / "foto.tif"  # Endung absichtlich falsch
    Image.new("RGB", (4, 4)).save(quelle, "TIFF", tiffinfo={50706: b"\x01\x04\x00\x00"})
    assert laden(quelle).quelle == "raw"


def test_raw_ohne_extra(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "rawpy", None)
    quelle = tmp_path / "foto.orf"
    quelle.write_bytes(b"IIRO\x08\x00\x00\x00" + b"\x00" * 100)
    assert main(["convert", str(quelle), str(tmp_path / "x.jpg")]) == 3
    assert "pip install miksan-converter[raw]" in capsys.readouterr().err


def test_extra_fehlt_meldung():
    fehler = ExtraFehlt("svg", "SVG-Dateien zu lesen")
    assert fehler.rueckgabecode == 3
    assert "miksan-converter[svg]" in str(fehler)


# --- Formatliste ----------------------------------------------------------------------


def test_docs_formate_entspricht_miksan_formats():
    doku = (Path(__file__).resolve().parent.parent / "docs" / "formate.md").read_text("utf-8")
    assert markdown_tabelle() in doku


def test_formats_zeigt_extras_und_einschraenkungen(capsys):
    assert main(["formats"]) == 0
    ausgabe = capsys.readouterr().out
    assert "[svg]" in ausgabe and "[raw]" in ausgabe
    for fmt in alle_formate():
        if fmt.einschraenkung:
            assert fmt.einschraenkung in ausgabe

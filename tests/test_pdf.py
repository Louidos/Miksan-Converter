"""PDF-Werkzeuge (Extra [pdf]); ohne pypdf/pypdfium2 werden die Tests übersprungen."""

import sys
from pathlib import Path

import pytest
from PIL import Image

from miksan_converter.cli import main
from miksan_converter.fehler import BedienFehler, MiksanFehler

pypdf = pytest.importorskip("pypdf")
pytest.importorskip("pypdfium2")

from miksan_converter import pdf  # noqa: E402

FARBEN = [(220, 40, 40), (40, 160, 60), (30, 111, 224), (240, 200, 30), (120, 60, 200)]


def _pdf(pfad: Path, seiten: int = 5, groesse=(200, 280)) -> Path:
    bilder = [Image.new("RGB", groesse, FARBEN[i % len(FARBEN)]) for i in range(seiten)]
    bilder[0].save(pfad, format="PDF", save_all=True, append_images=bilder[1:], resolution=72)
    return pfad


@pytest.fixture
def fuenf(tmp_path: Path) -> Path:
    return _pdf(tmp_path / "fuenf.pdf", 5)


@pytest.fixture
def geschuetzt(tmp_path: Path) -> Path:
    writer = pypdf.PdfWriter(clone_from=_pdf(tmp_path / "offen.pdf", 2))
    writer.encrypt("geheim")
    ziel = tmp_path / "geschuetzt.pdf"
    with open(ziel, "wb") as datei:
        writer.write(datei)
    return ziel


def _seiten(pfad: Path) -> int:
    return len(pypdf.PdfReader(pfad).pages)


def test_zusammenfuegen_seitenzahl_stimmt(fuenf, tmp_path: Path):
    zwei = _pdf(tmp_path / "zwei.pdf", 2)
    ziel = pdf.zusammenfuegen([fuenf, zwei], tmp_path / "alle.pdf")
    assert _seiten(ziel) == 7
    with pytest.raises(BedienFehler):
        pdf.zusammenfuegen([fuenf], tmp_path / "eins.pdf")


def test_zusammenfuegen_kommandozeile(fuenf, tmp_path: Path, capsys):
    zwei = _pdf(tmp_path / "zwei.pdf", 2)
    ziel = tmp_path / "gesamt.pdf"
    assert main(["pdf", "zusammenfuegen", str(zwei), str(fuenf), "-o", str(ziel)]) == 0
    assert _seiten(ziel) == 7
    assert "Gespeichert" in capsys.readouterr().out
    # Reihenfolge wie angegeben: erste Seite ist die erste von zwei.pdf (rot)
    erste = pdf.seite_rendern(ziel, 0)
    assert erste.getpixel((10, 10))[0] > 200
    assert main(["pdf", "merge", str(zwei), str(fuenf), "-o", str(ziel)]) == 1  # schon da


def test_teilen_jede_seite_einzeln(fuenf, tmp_path: Path):
    teile = pdf.teilen(fuenf, tmp_path / "teile")
    assert len(teile) == 5
    assert [p.name for p in teile][:2] == ["fuenf-seite-1.pdf", "fuenf-seite-2.pdf"]
    assert all(_seiten(p) == 1 for p in teile)


def test_teilen_nach_bereichen(fuenf, tmp_path: Path):
    assert main(["pdf", "teilen", str(fuenf), "--seiten", "1-3,5", "-o", str(tmp_path / "t")]) == 0
    namen = sorted(p.name for p in (tmp_path / "t").iterdir())
    assert namen == ["fuenf-seite-5.pdf", "fuenf-seiten-1-3.pdf"]
    assert _seiten(tmp_path / "t" / "fuenf-seiten-1-3.pdf") == 3


@pytest.mark.parametrize(
    ("text", "erwartet"),
    [
        (None, [[0], [1], [2], [3], [4]]),
        ("1-3,5", [[0, 1, 2], [4]]),
        ("4-", [[3, 4]]),
        ("-2", [[0, 1]]),
        (" 2 ; 3 ", [[1], [2]]),
    ],
)
def test_seiten_parsen(text, erwartet):
    assert pdf.seiten_parsen(text, 5) == erwartet


@pytest.mark.parametrize("text", ["0", "6", "3-1", "a", "1-x"])
def test_seiten_parsen_fehler(text):
    with pytest.raises(BedienFehler):
        pdf.seiten_parsen(text, 5)


def test_drehen_und_loeschen(fuenf, tmp_path: Path):
    gedreht = pdf.seiten_aendern(fuenf, tmp_path / "g.pdf", drehen=90, drehen_seiten="2")
    leser = pypdf.PdfReader(gedreht)
    assert [seite.rotation for seite in leser.pages] == [0, 90, 0, 0, 0]
    ziel = tmp_path / "weniger.pdf"
    assert main(["pdf", "loeschen", str(fuenf), "--seiten", "2,4-5", "-o", str(ziel)]) == 0
    assert _seiten(ziel) == 2
    with pytest.raises(BedienFehler, match="alle Seiten"):
        pdf.seiten_aendern(fuenf, tmp_path / "leer.pdf", loeschen="1-5")
    assert main(["pdf", "drehen", str(fuenf), "--grad", "180", "-o", str(tmp_path / "d.pdf")]) == 0
    assert {s.rotation for s in pypdf.PdfReader(tmp_path / "d.pdf").pages} == {180}


def test_zu_bildern_fuenf_bilder(fuenf, tmp_path: Path):
    bilder = pdf.zu_bildern(fuenf, tmp_path / "bilder", dpi=72)
    assert len(bilder) == 5
    assert bilder[0].name == "fuenf-seite-01.png"
    with Image.open(bilder[2]) as bild:
        assert bild.size == (200, 280)
        assert bild.getpixel((50, 50))[2] > 200  # dritte Seite blau
    assert main(["pdf", "bilder", str(fuenf), "--format", "jpg", "--dpi", "144",
                 "--seiten", "1", "-o", str(tmp_path / "jpg")]) == 0  # fmt: skip
    (jpg,) = (tmp_path / "jpg").iterdir()
    with Image.open(jpg) as bild:
        assert bild.format == "JPEG" and bild.size == (400, 560)


def test_aus_bildern_a4_und_wie_bild(tmp_path: Path):
    quer = tmp_path / "quer.png"
    hoch = tmp_path / "hoch.png"
    Image.new("RGBA", (400, 200), (255, 0, 0, 128)).save(quer)
    Image.new("RGB", (100, 300), (0, 0, 255)).save(hoch)
    a4 = pdf.aus_bildern([quer, hoch], tmp_path / "a4.pdf")
    seiten = pypdf.PdfReader(a4).pages
    assert len(seiten) == 2
    breite, hoehe = float(seiten[0].mediabox.width), float(seiten[0].mediabox.height)
    assert breite == pytest.approx(842, abs=2) and hoehe == pytest.approx(595, abs=2)  # quer
    assert float(seiten[1].mediabox.height) == pytest.approx(842, abs=2)
    ziel = tmp_path / "wie.pdf"
    assert main(["pdf", "aus-bildern", str(hoch), "--seitengroesse", "bild", "-o", str(ziel)]) == 0
    seite = pypdf.PdfReader(ziel).pages[0]
    assert (float(seite.mediabox.width), float(seite.mediabox.height)) == (100, 300)


def test_verkleinern(tmp_path: Path):
    rauschen = Image.effect_noise((1600, 1600), 80).convert("RGB")
    gross = tmp_path / "gross.pdf"
    rauschen.save(gross, format="PDF", resolution=72, quality=100)
    ziel, vorher, nachher = pdf.verkleinern(gross, tmp_path / "klein.pdf", qualitaet=30)
    assert nachher < vorher and ziel.stat().st_size == nachher
    assert _seiten(ziel) == 1


def test_passwort(geschuetzt, tmp_path: Path):
    assert pdf.ist_verschluesselt(geschuetzt)
    with pytest.raises(pdf.PasswortNoetig):
        pdf.teilen(geschuetzt, tmp_path / "a")
    with pytest.raises(pdf.PasswortNoetig, match="falsch"):
        pdf.teilen(geschuetzt, tmp_path / "a", passwort="nein")
    assert len(pdf.teilen(geschuetzt, tmp_path / "a", passwort="geheim")) == 2
    assert pdf.seite_rendern(geschuetzt, 0, passwort="geheim").size == (200, 280)
    with pytest.raises(pdf.PasswortNoetig):
        pdf.seite_rendern(geschuetzt, 0)
    assert main(["pdf", "bilder", str(geschuetzt), "-o", str(tmp_path / "b")]) == 1
    assert main(["pdf", "bilder", str(geschuetzt), "--passwort", "geheim",
                 "-o", str(tmp_path / "b")]) == 0  # fmt: skip


def test_defektes_pdf_klare_meldung(tmp_path: Path, capsys):
    kaputt = tmp_path / "kaputt.pdf"
    kaputt.write_bytes(b"%PDF-1.4\nkaputt kaputt")
    with pytest.raises(MiksanFehler, match="beschädigt"):
        pdf.teilen(kaputt)
    with pytest.raises(MiksanFehler, match="beschädigt"):
        pdf.seite_rendern(kaputt)
    assert main(["pdf", "teilen", str(kaputt)]) == 1
    assert "beschädigt" in capsys.readouterr().err


def test_nacheinander_sammelt_ergebnis(fuenf, tmp_path: Path):
    kaputt = tmp_path / "kaputt.pdf"
    kaputt.write_bytes(b"nix")
    meldungen = []
    ergebnis = pdf.nacheinander(
        [fuenf, kaputt],
        lambda p: pdf.teilen(p, tmp_path / "n"),
        lambda fertig, gesamt, name: meldungen.append((fertig, gesamt)),
    )
    assert len(ergebnis.ok) == 5 and len(ergebnis.fehler) == 1
    assert meldungen == [(1, 2), (2, 2)]


def test_ohne_extra_klare_meldung(monkeypatch, fuenf, capsys):
    monkeypatch.setitem(sys.modules, "pypdf", None)
    assert main(["pdf", "teilen", str(fuenf)]) == 3
    assert "miksan-converter[pdf]" in capsys.readouterr().err

"""Weitere Bild-Werkzeuge: Wasserzeichen, Umbenennen, Animation, Icon-Set, Zuschneiden.

Nutzen die Testbilder aus ``scripts/testbilder_erzeugen.py`` (Fixture ``testbilder``).
"""

import os
import shutil
from pathlib import Path

import pytest
from PIL import Image

from miksan_converter.cli import main
from miksan_converter.fehler import BedienFehler, MiksanFehler
from miksan_converter.werkzeuge import animation, iconset, umbenennen, wasserzeichen, zuschneiden


@pytest.fixture
def arbeitsordner(testbilder, tmp_path: Path) -> Path:
    ordner = tmp_path / "bilder"
    ordner.mkdir()
    for name in ("png", "jpeg", "webp", "heif"):
        shutil.copy(testbilder[name], ordner / testbilder[name].name)
    return ordner


# --- Wasserzeichen ------------------------------------------------------------------------


def test_wasserzeichen_text_unten_rechts(tmp_path: Path):
    Image.new("RGB", (400, 200), (0, 0, 0)).save(tmp_path / "schwarz.png")
    ergebnis = wasserzeichen.wasserzeichen(
        tmp_path / "schwarz.png", text="Miksan", deckkraft=100, groesse=30
    )
    assert ergebnis.ausgabe.name == "schwarz-wasserzeichen.png"
    with Image.open(ergebnis.ausgabe) as bild:
        rechts_unten = bild.crop((260, 120, 400, 200))
        links_oben = bild.crop((0, 0, 140, 80))
        assert rechts_unten.getextrema()[0][1] > 200  # weisser Text unten rechts
        assert links_oben.getextrema()[0][1] == 0


@pytest.mark.parametrize("position", wasserzeichen.POSITIONEN)
def test_wasserzeichen_alle_positionen(position, testbilder):
    with Image.open(testbilder["png"]) as quelle:
        bild = wasserzeichen.anwenden(quelle, text="©", position=position, deckkraft=80)
    assert bild.size == (32, 24) and bild.mode == "RGBA"


def test_wasserzeichen_logo_und_deckkraft(tmp_path: Path):
    Image.new("RGB", (200, 100), (0, 0, 0)).save(tmp_path / "foto.jpg")
    Image.new("RGBA", (50, 50), (255, 0, 0, 255)).save(tmp_path / "logo.png")
    ziel = tmp_path / "mit-logo.png"
    assert main(["wasserzeichen", str(tmp_path / "foto.jpg"), "--logo", str(tmp_path / "logo.png"),
                 "--position", "mitte", "--groesse", "50", "--deckkraft", "50",
                 "-o", str(ziel)]) == 0  # fmt: skip
    with Image.open(ziel) as bild:
        r, g, b = bild.convert("RGB").getpixel((100, 50))
        assert 110 <= r <= 145 and g < 10  # halb deckend rot auf schwarz
        assert bild.convert("RGB").getpixel((10, 10)) == (0, 0, 0)


def test_wasserzeichen_ordner_und_fehler(arbeitsordner, tmp_path: Path):
    assert (
        main(["wasserzeichen", str(arbeitsordner), "--text", "x", "-o", str(tmp_path / "aus")]) == 0
    )
    assert len(list((tmp_path / "aus").iterdir())) == 4
    assert main(["wasserzeichen", str(arbeitsordner), "--text", " "]) == 2
    with pytest.raises(BedienFehler):
        wasserzeichen.anwenden(Image.new("RGB", (10, 10)), text="x", position="irgendwo")


# --- Umbenennen ---------------------------------------------------------------------------


def test_umbenennen_vorschau_und_ausfuehren(arbeitsordner):
    pfade = sorted(arbeitsordner.iterdir())
    paare = umbenennen.neue_namen(pfade, "ferien-{nr}-{breite}x{hoehe}")
    assert [p.neu.name for p in paare] == [
        "ferien-01-32x24.heic",
        "ferien-02-32x24.jpg",
        "ferien-03-32x24.png",
        "ferien-04-32x24.webp",
    ]
    assert sorted(p.name for p in arbeitsordner.iterdir()) == [p.name for p in pfade]  # unverändert
    umbenennen.umbenennen(pfade, "ferien-{nr}")
    assert sorted(p.name for p in arbeitsordner.iterdir())[0] == "ferien-01.heic"


def test_umbenennen_datum_aus_exif(tmp_path: Path):
    bild = Image.new("RGB", (10, 10))
    exif = Image.Exif()
    exif.get_ifd(0x8769)[0x9003] = "2024:07:15 10:00:00"
    bild.save(tmp_path / "a.jpg", exif=exif)
    Image.new("RGB", (10, 10)).save(tmp_path / "b.png")
    os.utime(tmp_path / "b.png", (1_600_000_000, 1_600_000_000))  # 2020-09-13
    paare = umbenennen.neue_namen([tmp_path / "a.jpg", tmp_path / "b.png"], "{datum}_{name}")
    assert [p.neu.name for p in paare] == ["2024-07-15_a.jpg", "2020-09-13_b.png"]


def test_umbenennen_konflikt_bricht_ab_ohne_aenderung(arbeitsordner, capsys):
    (arbeitsordner / "foto.png").write_bytes(b"vorhanden")
    vorher = sorted(p.name for p in arbeitsordner.iterdir())
    pfade = [arbeitsordner / "quelle.jpg", arbeitsordner / "quelle.webp"]
    paare = umbenennen.neue_namen(pfade, "gleich")
    assert umbenennen.konflikte(paare) == []  # andere Endungen: kein Konflikt
    with pytest.raises(BedienFehler, match="keine Datei wurde verändert"):
        umbenennen.umbenennen([arbeitsordner / "quelle.png"], "foto")
    with pytest.raises(BedienFehler, match="doppelt"):
        umbenennen.umbenennen([arbeitsordner / "quelle.png", arbeitsordner / "foto.png"], "x")
    assert sorted(p.name for p in arbeitsordner.iterdir()) == vorher
    assert main(["umbenennen", str(arbeitsordner / "quelle.png"), "--muster", "foto"]) == 2
    assert sorted(p.name for p in arbeitsordner.iterdir()) == vorher


def test_umbenennen_kommandozeile_probe_und_kopie(arbeitsordner, tmp_path: Path, capsys):
    assert main(["umbenennen", str(arbeitsordner), "--muster", "neu-{nr}", "--probe"]) == 0
    assert "quelle.png -> neu-03.png" in capsys.readouterr().out
    assert len(list(arbeitsordner.glob("neu-*"))) == 0
    ziel = tmp_path / "kopien"
    assert main(["umbenennen", str(arbeitsordner), "--muster", "k{nr}", "-o", str(ziel)]) == 0
    assert sorted(p.name for p in ziel.iterdir())[0] == "k01.heic"
    assert (arbeitsordner / "quelle.png").exists()  # Original bleibt beim Kopieren


@pytest.mark.parametrize("muster", ["", "{unbekannt}", "a/b", "{nr"])
def test_umbenennen_ungueltige_muster(muster, arbeitsordner):
    with pytest.raises(BedienFehler):
        umbenennen.neue_namen([arbeitsordner / "quelle.png"], muster)


# --- Animation ----------------------------------------------------------------------------


def test_animation_erstellen_und_zerlegen(testbilder, tmp_path: Path):
    bilder = [testbilder["png"], testbilder["jpeg"], testbilder["webp"]]
    gif = animation.erstellen(bilder, tmp_path / "a.gif", dauer=200, schleife=2)
    with Image.open(gif) as bild:
        assert bild.n_frames == 3 and bild.info["duration"] == 200 and bild.info["loop"] == 2
    ziel = tmp_path / "a.webp"
    args = ["animation", "erstellen", *map(str, bilder), "-o", str(ziel), "--dauer", "100"]
    assert main(args) == 0
    with Image.open(ziel) as bild:
        assert bild.n_frames == 3
    teile = animation.zerlegen(testbilder["animiert_gif"], tmp_path / "teile")
    assert [p.name for p in teile] == [f"animiert-bild-00{i}.png" for i in (1, 2, 3)]
    with Image.open(teile[1]) as bild:
        assert bild.convert("RGB").getpixel((5, 5))[1] > 200  # zweites Bild grün
    assert main(["animation", "zerlegen", str(testbilder["animiert_webp"]),
                 "-o", str(tmp_path / "w"), "--format", "jpg"]) == 0  # fmt: skip
    assert len(list((tmp_path / "w").glob("*.jpg"))) == 3


def test_animation_fehler(testbilder, tmp_path: Path):
    with pytest.raises(BedienFehler):
        animation.erstellen([testbilder["png"]], tmp_path / "a.gif")
    with pytest.raises(BedienFehler):
        animation.erstellen([testbilder["png"]] * 2, tmp_path / "a.png")
    with pytest.raises(MiksanFehler, match="keine Animation"):
        animation.zerlegen(testbilder["png"], tmp_path)


# --- Icon-Set -----------------------------------------------------------------------------


def test_iconset(testbilder, tmp_path: Path):
    dateien = iconset.erstellen(testbilder["png"], tmp_path / "icons")
    namen = sorted(p.name for p in dateien)
    assert "favicon.ico" in namen and "icon-512x512.png" in namen and len(namen) == 7
    with Image.open(tmp_path / "icons" / "favicon.ico") as ico:
        assert set(ico.info["sizes"]) >= {(16, 16), (32, 32), (48, 48), (256, 256)}
    with Image.open(tmp_path / "icons" / "icon-180x180.png") as bild:
        assert bild.size == (180, 180)
        assert bild.getpixel((90, 2))[3] == 0  # quer -> oben transparent aufgefüllt
    assert main(["iconset", str(testbilder["jpeg"])]) == 0
    assert (testbilder["jpeg"].parent / "quelle-icons" / "favicon.ico").exists()


# --- Zuschneiden --------------------------------------------------------------------------


def test_zuschneiden_mittig_und_vorlage(tmp_path: Path):
    bild = Image.new("RGB", (400, 200), (255, 0, 0))
    bild.paste((0, 0, 255), (100, 0, 300, 200))  # blaue Mitte
    bild.save(tmp_path / "quer.png")
    ergebnis = zuschneiden.zuschneiden(tmp_path / "quer.png", verhaeltnis=(1, 1))
    with Image.open(ergebnis.ausgabe) as aus:
        assert aus.size == (200, 200) and aus.getpixel((5, 5)) == (0, 0, 255)
    ziel = tmp_path / "profil.jpg"
    assert main(["zuschneiden", str(tmp_path / "quer.png"), "--vorlage", "profilbild",
                 "-o", str(ziel)]) == 0  # fmt: skip
    with Image.open(ziel) as aus:
        assert aus.size == (400, 400) and aus.format == "JPEG"


def test_zuschneiden_bereich_und_relativ(testbilder, tmp_path: Path):
    ergebnis = zuschneiden.zuschneiden(
        testbilder["png"], tmp_path / "a.png", relativ=(0.5, 0.5, 0.5, 0.5)
    )
    with Image.open(ergebnis.ausgabe) as aus:
        assert aus.size == (16, 12)
    assert main(["zuschneiden", str(testbilder["png"]), "--bereich", "0,0,8,8",
                 "--ziel", "64x64", "-o", str(tmp_path / "b.png")]) == 0  # fmt: skip
    with Image.open(tmp_path / "b.png") as aus:
        assert aus.size == (64, 64)


@pytest.mark.parametrize(
    ("groesse", "verhaeltnis", "erwartet"),
    [
        ((400, 200), (1, 1), (100, 0, 200, 200)),
        ((200, 400), (1, 1), (0, 100, 200, 200)),
        ((1920, 1080), (16, 9), (0, 0, 1920, 1080)),
        ((300, 300), None, (0, 0, 300, 300)),
    ],
)
def test_bereich_mittig(groesse, verhaeltnis, erwartet):
    assert zuschneiden.bereich_mittig(groesse, verhaeltnis) == erwartet


@pytest.mark.parametrize("text", ["0:1", "a:b", "1"])
def test_verhaeltnis_ungueltig(text):
    with pytest.raises(BedienFehler):
        zuschneiden.verhaeltnis_parsen(text)

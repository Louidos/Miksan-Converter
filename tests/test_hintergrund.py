"""Hintergrund entfernen – mit einem Platzhalter statt des echten Modells."""

import socket
import sys
import types
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from miksan_converter.cli import main
from miksan_converter.fehler import BedienFehler, MiksanFehler
from miksan_converter.hintergrund import (
    hintergrund_entfernen,
    modell_name,
    modell_ordner,
)


class FalscheSitzung:
    def __init__(self, name):
        self.name = name


def _falsches_rembg(aufrufe: list | None = None, fehler: Exception | None = None):
    """Platzhalter für rembg: rechte Bildhälfte ist Vordergrund."""

    def new_session(name, *args, **kwargs):
        if fehler is not None:
            raise fehler
        if aufrufe is not None:
            aufrufe.append(name)
        return FalscheSitzung(name)

    def remove(bild, session=None, only_mask=False, **kwargs):
        assert only_mask
        assert isinstance(session, FalscheSitzung)
        maske = Image.new("L", bild.size, 0)
        maske.paste(255, (bild.width // 2, 0, bild.width, bild.height))
        return maske

    sitzungen = types.SimpleNamespace(
        sessions_names=["u2netp", "isnet-general-use", "u2net_human_seg", "birefnet-general"]
    )
    return types.SimpleNamespace(new_session=new_session, remove=remove, sessions=sitzungen)


@pytest.fixture
def rembg(monkeypatch, tmp_path):
    aufrufe: list[str] = []
    monkeypatch.setitem(sys.modules, "rembg", _falsches_rembg(aufrufe))
    monkeypatch.setenv("MIKSAN_MODELL_ORDNER", str(tmp_path / "modelle"))
    return aufrufe


@pytest.fixture
def portrait(tmp_path: Path) -> Path:
    pfad = tmp_path / "portrait.jpg"
    Image.new("RGB", (40, 20), (200, 180, 160)).save(pfad, quality=95)
    return pfad


def test_bg_liefert_transparentes_png(rembg, portrait, tmp_path: Path):
    ziel = tmp_path / "portrait.png"
    assert main(["bg", str(portrait), str(ziel)]) == 0
    with Image.open(ziel) as bild:
        assert bild.mode == "RGBA"
        assert bild.getpixel((5, 10))[3] == 0
        assert bild.getpixel((35, 10))[3] == 255
    assert rembg == ["u2netp"]


def test_ohne_ausgabe_entsteht_freigestellt_png(rembg, portrait):
    assert main(["hintergrund", str(portrait)]) == 0
    assert (portrait.parent / "portrait-freigestellt.png").exists()


def test_ziel_ohne_alpha_nutzt_background(rembg, portrait, tmp_path: Path):
    ziel = tmp_path / "schwarz.jpg"
    assert main(["bg", str(portrait), str(ziel), "--background", "#000000"]) == 0
    with Image.open(ziel) as bild:
        assert max(bild.getpixel((5, 10))) <= 5
        assert bild.getpixel((35, 10))[0] > 150


@pytest.mark.parametrize("endung", [".webp", ".avif"])
def test_weitere_formate_mit_transparenz(rembg, portrait, tmp_path: Path, endung):
    ziel = tmp_path / f"frei{endung}"
    assert main(["bg", str(portrait), str(ziel)]) == 0
    with Image.open(ziel) as bild:
        assert bild.convert("RGBA").getpixel((2, 10))[3] == 0


def test_nur_maske(rembg, portrait, tmp_path: Path):
    ziel = tmp_path / "maske.png"
    assert main(["bg", str(portrait), str(ziel), "--nur-maske"]) == 0
    with Image.open(ziel) as bild:
        assert bild.mode == "L"
        assert bild.getpixel((5, 10)) == 0
        assert bild.getpixel((35, 10)) == 255


def test_modell_waehlen(rembg, portrait, tmp_path: Path):
    assert main(["bg", str(portrait), str(tmp_path / "a.png"), "--modell", "genau"]) == 0
    assert main(["bg", str(portrait), str(tmp_path / "b.png"), "--model", "u2net_human_seg"]) == 0
    assert rembg == ["isnet-general-use", "u2net_human_seg"]


def test_unbekanntes_modell(rembg, portrait, tmp_path: Path):
    with pytest.raises(BedienFehler, match="Unbekanntes Modell"):
        hintergrund_entfernen(portrait, tmp_path / "x.png", modell="gibtsnicht")


def test_modellname_kurzformen():
    assert modell_name("klein") == "u2netp"
    assert modell_name("Genau") == "isnet-general-use"
    assert modell_name("silueta") == "silueta"


def test_modell_ordner_reihenfolge(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("MIKSAN_MODELL_ORDNER", raising=False)
    monkeypatch.delenv("REMBG_HOME", raising=False)
    monkeypatch.delenv("U2NET_HOME", raising=False)
    assert modell_ordner().parts[-2:] == ("miksan-converter", "modelle")
    monkeypatch.setenv("U2NET_HOME", str(tmp_path / "u2net"))
    assert modell_ordner() == tmp_path / "u2net"
    monkeypatch.setenv("MIKSAN_MODELL_ORDNER", str(tmp_path / "eigen"))
    assert modell_ordner() == tmp_path / "eigen"


def test_modell_ordner_wird_an_rembg_weitergegeben(rembg, portrait, tmp_path: Path):
    import os

    hintergrund_entfernen(portrait, tmp_path / "x.png")
    assert os.environ["REMBG_HOME"] == str(tmp_path / "modelle")
    assert (tmp_path / "modelle").is_dir()


def test_download_fehler_klare_meldung(monkeypatch, portrait, tmp_path: Path, capsys):
    monkeypatch.setitem(
        sys.modules, "rembg", _falsches_rembg(fehler=ConnectionError("keine Verbindung"))
    )
    monkeypatch.setenv("MIKSAN_MODELL_ORDNER", str(tmp_path / "modelle"))
    assert main(["bg", str(portrait), str(tmp_path / "x.png")]) == 1
    fehler = capsys.readouterr().err
    assert "Internet" in fehler and "keine Verbindung" in fehler
    assert not (tmp_path / "x.png").exists()


def test_ohne_extra_installationsmeldung(monkeypatch, portrait, tmp_path: Path, capsys):
    monkeypatch.setitem(sys.modules, "rembg", None)
    assert main(["bg", str(portrait), str(tmp_path / "x.png")]) == 3
    fehler = capsys.readouterr().err
    assert "Bitte `pip install miksan-converter[ki]` installieren" in fehler
    assert "Traceback" not in fehler


def test_original_bleibt_unveraendert(rembg, portrait):
    vorher = portrait.read_bytes()
    with pytest.raises(MiksanFehler):
        hintergrund_entfernen(portrait, portrait, overwrite=True)
    assert portrait.read_bytes() == vorher


# --- Echtes Modell (langsam, lädt beim ersten Mal ca. 5 MB herunter) -------------------


@pytest.mark.slow
def test_echtes_modell_und_danach_offline(tmp_path: Path, monkeypatch):
    pytest.importorskip("rembg")
    monkeypatch.setenv("MIKSAN_MODELL_ORDNER", str(tmp_path / "modelle"))
    quelle = tmp_path / "kreis.png"
    bild = Image.new("RGB", (320, 320), (255, 255, 255))
    ImageDraw.Draw(bild).ellipse((80, 80, 240, 240), fill=(200, 30, 30))
    bild.save(quelle)

    assert main(["bg", str(quelle), str(tmp_path / "erster.png")]) == 0

    def kein_netz(*args, **kwargs):
        raise OSError("Netzwerk im Test gesperrt")

    monkeypatch.setattr(socket, "socket", kein_netz)
    monkeypatch.setattr(socket, "create_connection", kein_netz)
    assert main(["bg", str(quelle), str(tmp_path / "zweiter.png")]) == 0
    with Image.open(tmp_path / "zweiter.png") as ergebnis:
        assert ergebnis.getpixel((160, 160))[3] > 200
        assert ergebnis.getpixel((5, 5))[3] < 50


# --- Neuer Hintergrund, weiche Kante, Modelle --------------------------------------------


def test_neue_farbe_fuellt_hintergrund(rembg, portrait, tmp_path: Path):
    ziel = tmp_path / "blau.png"
    assert main(["bg", str(portrait), str(ziel), "--neue-farbe", "#1e6fe0"]) == 0
    with Image.open(ziel) as bild:
        assert bild.convert("RGBA").getpixel((5, 10)) == (30, 111, 224, 255)
        r, g, b, a = bild.convert("RGBA").getpixel((35, 10))
        assert abs(r - 200) <= 3 and abs(g - 180) <= 3 and abs(b - 160) <= 3 and a == 255


def test_neues_bild_und_weichzeichnen(rembg, portrait, tmp_path: Path):
    hinten = tmp_path / "strand.png"
    Image.new("RGB", (300, 300), (10, 200, 10)).save(hinten)
    ziel = tmp_path / "strand-ergebnis.png"
    assert main(["bg", str(portrait), str(ziel), "--neues-bild", str(hinten)]) == 0
    with Image.open(ziel) as bild:
        assert bild.size == (40, 20)
        assert bild.convert("RGBA").getpixel((5, 10)) == (10, 200, 10, 255)
    weich = tmp_path / "weich.png"
    assert main(["bg", str(portrait), str(weich), "--weichzeichnen"]) == 0
    with Image.open(weich) as bild:
        assert bild.convert("RGBA").getpixel((5, 10))[3] == 255


def test_kante_weicher_macht_uebergang(rembg, portrait, tmp_path: Path):
    hart, weich = tmp_path / "hart.png", tmp_path / "weich.png"
    assert main(["bg", str(portrait), str(hart)]) == 0
    assert main(["bg", str(portrait), str(weich), "--kante", "6"]) == 0
    with Image.open(hart) as a, Image.open(weich) as b:
        assert a.getpixel((19, 10))[3] == 0 and a.getpixel((20, 10))[3] == 255
        assert 0 < b.getpixel((19, 10))[3] < 255


def test_neue_optionen_bedienfehler(rembg, portrait, tmp_path: Path, capsys):
    assert main(["bg", str(portrait), "--nur-maske", "--neue-farbe", "weiss"]) == 2
    assert main(["bg", str(portrait), "--neue-farbe", "keinefarbe"]) == 2
    with pytest.raises(SystemExit):
        main(["bg", str(portrait), "--kante", "99"])
    with pytest.raises(SystemExit):
        main(["bg", str(portrait), "--neue-farbe", "weiss", "--weichzeichnen"])


def test_ohne_neue_optionen_wie_bisher(rembg, portrait, tmp_path: Path):
    from miksan_converter.hintergrund import freistellen

    ziel = tmp_path / "a.png"
    assert main(["bg", str(portrait), str(ziel)]) == 0
    maske = Image.new("L", (40, 20), 0)
    maske.paste(255, (20, 0, 40, 20))
    with Image.open(portrait) as quelle, Image.open(ziel) as bild:
        assert bild.tobytes() == freistellen(quelle, maske).tobytes()


def test_zusammensetzen_arten():
    from miksan_converter import hintergrund as hg

    bild = Image.new("RGB", (10, 10), (255, 0, 0))
    maske = Image.new("L", (10, 10), 0)
    assert hg.zusammensetzen(bild, maske).getpixel((0, 0))[3] == 0
    farbig = hg.zusammensetzen(bild, maske, neuer_hintergrund=hg.FARBE, farbe=(0, 0, 255))
    assert farbig.getpixel((0, 0)) == (0, 0, 255, 255)
    with pytest.raises(BedienFehler):
        hg.zusammensetzen(bild, maske, neuer_hintergrund=hg.BILD)
    with pytest.raises(BedienFehler):
        hg.zusammensetzen(bild, maske, neuer_hintergrund="gibtsnicht")
    assert hg.kante_weicher(maske, 0) is maske


def test_modell_herunterladen_prueft_summe(monkeypatch, tmp_path: Path):
    import hashlib
    import io

    from miksan_converter import hintergrund as hg

    daten = b"onnx" * 1000
    info = hg.ModellInfo("Test", 1, "", "https://beispiel.invalid/m.onnx", "falsch", "MIT")
    monkeypatch.setitem(hg.MODELL_INFOS, "klein", info)
    monkeypatch.setenv("MIKSAN_MODELL_ORDNER", str(tmp_path / "modelle"))

    class Antwort(io.BytesIO):
        headers = {"Content-Length": str(len(daten))}

    monkeypatch.setattr(hg.urllib.request, "urlopen", lambda url, timeout: Antwort(daten))
    with pytest.raises(MiksanFehler, match="beschädigt"):
        hg.modell_herunterladen("klein")
    assert not list((tmp_path / "modelle").iterdir())  # keine halbe Datei

    md5 = hashlib.md5(daten, usedforsecurity=False).hexdigest()
    monkeypatch.setitem(hg.MODELL_INFOS, "klein", hg.ModellInfo("T", 1, "", info.url, md5, "MIT"))
    schritte = []
    pfad = hg.modell_herunterladen("klein", lambda fertig, gesamt: schritte.append(fertig))
    assert pfad == tmp_path / "modelle" / "u2netp.onnx" and pfad.read_bytes() == daten
    assert schritte[-1] == len(daten)
    assert hg.modell_vorhanden("klein")


def test_mitgeliefertes_modell_wird_genutzt(rembg, monkeypatch, tmp_path: Path):
    from miksan_converter import hintergrund as hg

    paket = tmp_path / "paket"
    (paket / "miksan_modelle").mkdir(parents=True)
    (paket / "miksan_modelle" / "u2netp.onnx").write_bytes(b"modell")
    monkeypatch.setattr(sys, "_MEIPASS", str(paket), raising=False)
    monkeypatch.setenv("MIKSAN_KEIN_DOWNLOAD", "1")
    assert hg.modell_vorhanden("klein")
    assert not hg.modell_vorhanden("genau")
    hg.sitzung_erstellen("klein")
    assert (hg.modell_ordner() / "u2netp.onnx").read_bytes() == b"modell"
    with pytest.raises(MiksanFehler, match="MIKSAN_KEIN_DOWNLOAD"):
        hg.sitzung_erstellen("genau")

"""Ganze Ordner, mehrere Dateien und Muster verarbeiten."""

import io
import sys
import threading
from pathlib import Path

import pytest
from PIL import Image

from miksan_converter.cli import main
from miksan_converter.fehler import MiksanFehler
from miksan_converter.stapel import Auftrag, ausfuehren, dateien_sammeln

from .test_hintergrund import _falsches_rembg


@pytest.fixture
def fotos(tmp_path: Path) -> Path:
    """Ordner mit drei Bildern, einer kaputten Datei, Text, versteckter Datei und Unterordner."""
    ordner = tmp_path / "fotos"
    (ordner / "unter").mkdir(parents=True)
    Image.new("RGB", (30, 20), (200, 0, 0)).save(ordner / "a.png")
    Image.new("RGB", (30, 20), (0, 200, 0)).save(ordner / "b.gif")
    Image.new("RGBA", (30, 20), (0, 0, 200, 128)).save(ordner / "c.webp")
    Image.new("RGB", (30, 20), (9, 9, 9)).save(ordner / "unter" / "d.png")
    gut = io.BytesIO()
    Image.effect_noise((64, 64), 40).save(gut, "PNG")
    (ordner / "kaputt.png").write_bytes(gut.getvalue()[:200])
    (ordner / "notiz.txt").write_text("kein Bild")
    Image.new("RGB", (4, 4)).save(ordner / ".versteckt.png")
    return ordner


def _namen(ordner: Path) -> set[str]:
    return {p.relative_to(ordner).as_posix() for p in ordner.rglob("*") if p.is_file()}


def test_ordner_nach_jpg(fotos: Path, tmp_path: Path, capsys):
    fertig = tmp_path / "fertig"
    assert main(["convert", str(fotos), "--to", "jpg", "-o", str(fertig)]) == 1
    assert _namen(fertig) == {"a.jpg", "b.jpg", "c.jpg"}
    for datei in fertig.iterdir():
        with Image.open(datei) as bild:
            assert bild.format == "JPEG"
    ausgabe = capsys.readouterr()
    assert "3 ok, 1 Fehler" in ausgabe.out
    assert "kaputt.png" in ausgabe.err and "beschädigt" in ausgabe.err


def test_ohne_fehler_rueckgabecode_null(tmp_path: Path, capsys):
    ordner = tmp_path / "gut"
    ordner.mkdir()
    for name in ("x.png", "y.png"):
        Image.new("RGB", (8, 8)).save(ordner / name)
    assert main(["convert", str(ordner), "--to", "webp", "-o", str(tmp_path / "aus")]) == 0
    assert "2 ok, 0 Fehler" in capsys.readouterr().out


def test_rekursiv_behaelt_struktur(fotos: Path, tmp_path: Path):
    fertig = tmp_path / "fertig"
    main(["convert", str(fotos), "--to", "png", "-o", str(fertig), "--rekursiv"])
    assert _namen(fertig) == {"a.png", "b.png", "c.png", "unter/d.png"}


def test_ausgabeordner_wird_angelegt(fotos: Path, tmp_path: Path):
    fertig = tmp_path / "neu" / "tief" / "verschachtelt"
    main(["convert", str(fotos / "a.png"), "--to", "jpg", "-o", str(fertig)])
    assert (fertig / "a.jpg").is_file()


def test_muster(fotos: Path, tmp_path: Path, capsys):
    fertig = tmp_path / "fertig"
    muster = str(fotos / "*.png")  # wie unter Windows: nicht von der Shell aufgelöst
    assert main(["convert", muster, "--to", "jpg", "-o", str(fertig)]) == 1  # kaputt.png
    assert _namen(fertig) == {"a.jpg"}
    assert "1 ok, 1 Fehler" in capsys.readouterr().out


def test_muster_ohne_treffer(tmp_path: Path, capsys):
    assert main(["convert", str(tmp_path / "*.heic"), "--to", "jpg", "-o", str(tmp_path)]) == 1
    assert "keine Datei passt" in capsys.readouterr().err


def test_mehrere_dateien_ohne_ordner_landen_neben_dem_original(fotos: Path, capsys):
    befehl = ["convert", str(fotos / "a.png"), str(fotos / "b.gif"), "--to", "webp"]
    assert main(befehl) == 0
    assert (fotos / "a.webp").is_file() and (fotos / "b.webp").is_file()
    assert "2 ok, 0 Fehler" in capsys.readouterr().out


def test_zwei_dateien_ohne_to_sind_eingabe_und_ausgabe(fotos: Path, tmp_path: Path):
    ziel = tmp_path / "einzeln.jpg"
    assert main(["convert", str(fotos / "a.png"), str(ziel)]) == 0
    assert ziel.is_file()


def test_ordner_ohne_to(fotos: Path, tmp_path: Path, capsys):
    assert main(["convert", str(fotos), "-o", str(tmp_path / "x")]) == 2
    assert "--to" in capsys.readouterr().err


def test_doppelte_ziele(tmp_path: Path, capsys):
    ordner = tmp_path / "doppelt"
    ordner.mkdir()
    Image.new("RGB", (8, 8)).save(ordner / "bild.png")
    Image.new("RGB", (8, 8)).save(ordner / "bild.gif")
    assert main(["convert", str(ordner), "--to", "jpg", "-o", str(tmp_path / "aus")]) == 1
    fehler = capsys.readouterr().err
    assert "entsteht schon aus" in fehler


def test_leerer_ordner(tmp_path: Path, capsys):
    (tmp_path / "leer").mkdir()
    assert main(["convert", str(tmp_path / "leer"), "--to", "jpg", "-o", str(tmp_path)]) == 1
    assert "Keine Bilddateien" in capsys.readouterr().err


def test_vorhandene_ziele_bleiben_ohne_overwrite(fotos: Path, tmp_path: Path, capsys):
    fertig = tmp_path / "fertig"
    fertig.mkdir()
    (fertig / "a.jpg").write_bytes(b"alt")
    main(["convert", str(fotos), "--to", "jpg", "-o", str(fertig)])
    assert (fertig / "a.jpg").read_bytes() == b"alt"
    assert "gibt es schon" in capsys.readouterr().err
    assert (
        main(["convert", str(fotos / "a.png"), "--to", "jpg", "-o", str(fertig), "--overwrite"])
        == 0
    )
    assert (fertig / "a.jpg").read_bytes() != b"alt"


def test_ausgabeordner_im_eingabeordner_wird_nicht_erneut_verarbeitet(fotos: Path):
    fertig = fotos / "fertig"
    main(["convert", str(fotos), "--to", "png", "-o", str(fertig), "-r"])
    vorher = _namen(fertig)
    main(["convert", str(fotos), "--to", "png", "-o", str(fertig), "-r", "--overwrite"])
    assert _namen(fertig) == vorher
    assert not any(name.startswith("fertig/") for name in vorher)


@pytest.mark.parametrize("jobs", ["1", "4"])
def test_jobs(fotos: Path, tmp_path: Path, jobs):
    fertig = tmp_path / "fertig"
    main(["convert", str(fotos), "--to", "bmp", "-o", str(fertig), "--jobs", jobs])
    assert _namen(fertig) == {"a.bmp", "b.bmp", "c.bmp"}


def test_bearbeiten_ordner(fotos: Path, tmp_path: Path):
    kleiner = tmp_path / "kleiner"
    main(["bearbeiten", str(fotos), "-o", str(kleiner), "--max", "15"])
    assert _namen(kleiner) == {"a.png", "b.gif", "c.webp"}
    with Image.open(kleiner / "b.gif") as bild:
        assert bild.format == "GIF" and bild.size == (15, 10)


def test_bearbeiten_ohne_ordner_haengt_namen_an(fotos: Path):
    main(["bearbeiten", str(fotos / "[ab].*"), "--drehen", "90"])
    assert (fotos / "a-bearbeitet.png").is_file() and (fotos / "b-bearbeitet.gif").is_file()


def test_bg_ordner(fotos: Path, tmp_path: Path, monkeypatch, capsys):
    aufrufe: list[str] = []
    monkeypatch.setitem(sys.modules, "rembg", _falsches_rembg(aufrufe))
    monkeypatch.setenv("MIKSAN_MODELL_ORDNER", str(tmp_path / "modelle"))
    freigestellt = tmp_path / "freigestellt"
    assert main(["bg", str(fotos), "-o", str(freigestellt)]) == 1  # kaputt.png
    assert _namen(freigestellt) == {"a.png", "b.png", "c.png"}
    with Image.open(freigestellt / "a.png") as bild:
        assert bild.getpixel((2, 10))[3] == 0 and bild.getpixel((28, 10))[3] == 255
    assert aufrufe == ["u2netp"]  # Modell nur einmal geladen
    assert "3 ok, 1 Fehler" in capsys.readouterr().out


def test_dateien_sammeln_filtert(fotos: Path):
    dateien, fehler = dateien_sammeln([fotos, fotos / "notiz.txt", fotos / "fehlt.png"])
    namen = sorted(d.pfad.name for d in dateien)
    # Im Ordner nur Bild-Endungen; ausdrücklich genannte Dateien immer
    assert namen == ["a.png", "b.gif", "c.webp", "kaputt.png", "notiz.txt"]
    assert [p.name for p, _ in fehler] == ["fehlt.png"]


class _Terminal(io.StringIO):
    def isatty(self):
        return True


def test_fortschritt_und_fehler_brechen_nicht_ab(tmp_path: Path):
    def arbeit(auftrag: Auftrag) -> list[str]:
        if auftrag.eingabe.name == "2":
            raise RuntimeError("kaputt")
        return []

    auftraege = [Auftrag(tmp_path / str(i), tmp_path / f"{i}.out") for i in range(5)]
    terminal = _Terminal()
    ergebnis = ausfuehren(auftraege, arbeit, jobs=2, fortschritt=terminal)
    assert len(ergebnis.ok) == 4 and len(ergebnis.fehler) == 1
    assert ergebnis.rueckgabecode == 1
    assert "[5/5]" in terminal.getvalue()


def test_rueckmeldung_nach_jedem_auftrag(tmp_path: Path):
    auftraege = [Auftrag(tmp_path / str(i), tmp_path / f"{i}.out") for i in range(4)]
    meldungen = []
    aufrufer = threading.get_ident()

    def rueckmeldung(fertig: int, gesamt: int, auftrag: Auftrag) -> None:
        assert threading.get_ident() == aufrufer  # im aufrufenden Thread
        meldungen.append((fertig, gesamt, auftrag))

    ergebnis = ausfuehren(auftraege, lambda a: [], jobs=3, rueckmeldung=rueckmeldung)
    assert [(f, g) for f, g, _ in meldungen] == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert {id(a) for _, _, a in meldungen} == {id(a) for a in auftraege}
    assert len(ergebnis.ok) == 4 and ergebnis.uebersprungen == []


def test_rueckmeldung_auch_bei_fehlern(tmp_path: Path):
    def arbeit(auftrag: Auftrag) -> list[str]:
        raise MiksanFehler("geht nicht")

    meldungen = []
    auftraege = [Auftrag(tmp_path / "a", tmp_path / "a.out")]
    ergebnis = ausfuehren(auftraege, arbeit, rueckmeldung=lambda *m: meldungen.append(m))
    assert len(meldungen) == 1 and len(ergebnis.fehler) == 1


def test_abbrechen_ueberspringt_nicht_gestartete(tmp_path: Path):
    abbrechen = threading.Event()
    gestartet = []

    def arbeit(auftrag: Auftrag) -> list[str]:
        gestartet.append(auftrag)
        return []

    def rueckmeldung(fertig: int, gesamt: int, auftrag: Auftrag) -> None:
        abbrechen.set()  # nach dem ersten fertigen Auftrag abbrechen

    # mit einem Job kann höchstens der zweite Auftrag schon gestartet sein
    auftraege = [Auftrag(tmp_path / str(i), tmp_path / f"{i}.out") for i in range(10)]
    ergebnis = ausfuehren(auftraege, arbeit, jobs=1, rueckmeldung=rueckmeldung, abbrechen=abbrechen)
    assert 1 <= len(ergebnis.ok) <= 2
    assert len(ergebnis.ok) + len(ergebnis.uebersprungen) == 10
    assert len(gestartet) == len(ergebnis.ok)
    assert ergebnis.fehler == [] and ergebnis.rueckgabecode == 0


def test_abbrechen_vor_dem_start(tmp_path: Path):
    abbrechen = threading.Event()
    abbrechen.set()
    auftraege = [Auftrag(tmp_path / str(i), tmp_path / f"{i}.out") for i in range(3)]
    ergebnis = ausfuehren(auftraege, lambda a: pytest.fail("läuft"), abbrechen=abbrechen)
    assert ergebnis.ok == [] and len(ergebnis.uebersprungen) == 3


def test_ohne_abbrechen_alles_wie_bisher(tmp_path: Path):
    auftraege = [Auftrag(tmp_path / str(i), tmp_path / f"{i}.out") for i in range(3)]
    ergebnis = ausfuehren(auftraege, lambda a: None)
    assert len(ergebnis.ok) == 3 and ergebnis.uebersprungen == [] and ergebnis.hinweise == []

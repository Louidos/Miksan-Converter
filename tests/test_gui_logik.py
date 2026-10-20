"""Logik der Oberfläche ohne Fenster (kein Qt nötig)."""

import sys
import threading
from pathlib import Path

import pytest
from PIL import Image

from miksan_converter.bearbeiten import Bearbeitung
from miksan_converter.fehler import BedienFehler
from miksan_converter.gui import logik
from miksan_converter.gui.logik import Einstellungen

from .test_hintergrund import _falsches_rembg


@pytest.fixture
def ordner(tmp_path: Path) -> Path:
    ordner = tmp_path / "bilder"
    (ordner / "unter").mkdir(parents=True)
    Image.new("RGBA", (40, 30), (200, 0, 0, 128)).save(ordner / "a.png")
    Image.new("RGB", (40, 30), (0, 200, 0)).save(ordner / "b.jpg")
    Image.new("RGB", (40, 30), (0, 0, 200)).save(ordner / "unter" / "c.png")
    return ordner


def test_bearbeitung_aus_feldern():
    einstellungen = Einstellungen(
        max_seite=800, drehen=90, spiegeln="h", zielgroesse=" 500KB ", metadaten_entfernen=True
    )
    assert logik.bearbeitung_aus(einstellungen) == Bearbeitung(
        max_seite=800, drehen=90, spiegeln="h", zielgroesse=500_000, metadaten_entfernen=True
    )


def test_leere_felder_bedeuten_unveraendert():
    bearbeitung = logik.bearbeitung_aus(Einstellungen(max_seite=0, qualitaet=0, zielgroesse=""))
    assert bearbeitung == Bearbeitung()


@pytest.mark.parametrize(
    ("felder", "meldung"),
    [
        ({"qualitaet": 80, "zielgroesse": "1MB"}, "nur --qualitaet oder --zielgroesse"),
        ({"zielgroesse": "viel"}, "ungültig"),
        ({"hintergrundfarbe": "keinefarbe"}, "keinefarbe"),
        ({"aktion": logik.BEARBEITEN, "ziel_format": ""}, "Keine Bearbeitung"),
        ({"ziel_format": "svg"}, "nur gelesen"),
    ],
)
def test_einstellungen_pruefen_meldet_fehler(felder, meldung):
    with pytest.raises(BedienFehler, match=meldung):
        logik.einstellungen_pruefen(Einstellungen(**felder))


def test_formatliste_nur_schreibbare():
    namen = [eintrag.name for eintrag in logik.formate_fuer_auswahl()]
    assert "jpeg" in namen and "png" in namen and "heif" in namen
    assert "svg" not in namen and "raw" not in namen
    assert logik.formate_fuer_auswahl(wie_original=True)[0].name == logik.WIE_ORIGINAL


def test_format_ohne_extra_ist_ausgegraut(monkeypatch):
    from miksan_converter.formats import Format

    neu = Format("test", "Testformat", (".tst",), "PNG", extra="svg")
    monkeypatch.setattr(logik, "alle_formate", lambda: (neu,))
    monkeypatch.setattr(logik, "extra_installiert", lambda extra: False)
    (eintrag,) = logik.formate_fuer_auswahl()
    assert not eintrag.verfuegbar
    assert "[svg]" in eintrag.hinweis


def test_hintergrund_ohne_ki_ausgegraut(monkeypatch):
    monkeypatch.setattr(logik, "extra_installiert", lambda extra: False)
    aktionen = {eintrag.name: eintrag for eintrag in logik.aktionen_fuer_auswahl()}
    assert aktionen[logik.UMWANDELN].verfuegbar
    assert not aktionen[logik.HINTERGRUND].verfuegbar
    assert "[ki]" in aktionen[logik.HINTERGRUND].hinweis


def test_hintergrund_mit_ki_verfuegbar(monkeypatch):
    monkeypatch.setattr(logik, "extra_installiert", lambda extra: True)
    assert all(eintrag.verfuegbar for eintrag in logik.aktionen_fuer_auswahl())


def test_modell_vorhanden(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MIKSAN_MODELL_ORDNER", str(tmp_path))
    assert not logik.modell_vorhanden("klein")
    (tmp_path / "u2netp.onnx").write_bytes(b"x")
    assert logik.modell_vorhanden("klein")


def test_planen_neben_dem_original(ordner: Path):
    plan = logik.planen([ordner], Einstellungen(ziel_format="webp"))
    assert {a.ausgabe for a in plan.auftraege} == {ordner / "a.webp", ordner / "b.webp"}
    assert plan.fehler == []


def test_planen_rekursiv_mit_ausgabeordner(ordner: Path, tmp_path: Path):
    aus = tmp_path / "aus"
    einstellungen = Einstellungen(ziel_format="png", rekursiv=True, ausgabe_ordner=aus)
    plan = logik.planen([ordner], einstellungen)
    assert {a.ausgabe for a in plan.auftraege} == {
        aus / "a.png",
        aus / "b.png",
        aus / "unter" / "c.png",
    }


def test_planen_bearbeiten_behaelt_format(ordner: Path):
    einstellungen = Einstellungen(aktion=logik.BEARBEITEN, ziel_format="", max_seite=10)
    plan = logik.planen([ordner / "b.jpg"], einstellungen)
    assert plan.auftraege[0].ausgabe == ordner / "b-bearbeitet.jpg"


def test_planen_hintergrund_wie_cli(ordner: Path):
    einstellungen = Einstellungen(aktion=logik.HINTERGRUND, ziel_format="png")
    plan = logik.planen([ordner / "b.jpg"], einstellungen)
    assert plan.auftraege[0].ausgabe == ordner / "b-freigestellt.png"


def test_planen_meldet_fehlende_datei(tmp_path: Path):
    plan = logik.planen([tmp_path / "gibtsnicht.png"], Einstellungen())
    assert plan.auftraege == []
    assert "nicht gefunden" in plan.fehler[0][1]


def test_umwandeln_mit_bearbeitung(ordner: Path, tmp_path: Path):
    aus = tmp_path / "aus"
    einstellungen = Einstellungen(
        ziel_format="jpeg", ausgabe_ordner=aus, max_seite=20, hintergrundfarbe="#000000"
    )
    plan = logik.planen([ordner], einstellungen)
    meldungen = []
    ergebnis = logik.plan_ausfuehren(
        plan, einstellungen, rueckmeldung=lambda f, g, a: meldungen.append((f, g))
    )
    assert len(ergebnis.ok) == 2 and not ergebnis.fehler
    assert sorted(meldungen) == [(1, 2), (2, 2)]
    with Image.open(aus / "a.jpg") as bild:
        assert bild.format == "JPEG" and max(bild.size) == 20
        assert bild.getpixel((0, 0))[0] < 120  # halbtransparent auf Schwarz
    assert logik.zusammenfassung(ergebnis) == "2 ok, 0 Fehler"
    assert logik.ausgabe_ordner_von(ergebnis, einstellungen) == aus


def test_fehler_und_hinweise_pro_datei(ordner: Path):
    (ordner / "kaputt.png").write_bytes(b"\x89PNG\r\n\x1a\nkaputt")
    einstellungen = Einstellungen(ziel_format="webp")
    plan = logik.planen([ordner, ordner / "fehlt.png"], einstellungen)
    ergebnis = logik.plan_ausfuehren(plan, einstellungen)
    assert len(ergebnis.ok) == 2
    assert len(ergebnis.fehler) == 2
    zeilen = logik.meldungen(ergebnis)
    assert any("fehlt.png" in z and z.startswith("Fehler") for z in zeilen)
    assert any("kaputt.png" in z for z in zeilen)
    assert logik.zusammenfassung(ergebnis) == "2 ok, 2 Fehler"
    assert logik.ausgabe_ordner_von(ergebnis, einstellungen) == ordner


def test_abbrechen_ueberspringt_alles(ordner: Path, tmp_path: Path):
    einstellungen = Einstellungen(ziel_format="webp", ausgabe_ordner=tmp_path / "aus")
    plan = logik.planen([ordner], einstellungen)
    abbrechen = threading.Event()
    abbrechen.set()
    ergebnis = logik.plan_ausfuehren(plan, einstellungen, abbrechen=abbrechen)
    assert ergebnis.ok == [] and len(ergebnis.uebersprungen) == 2
    assert "2 abgebrochen" in logik.zusammenfassung(ergebnis)
    assert not list((tmp_path / "aus").glob("*.webp"))


def test_hintergrund_nutzt_eine_sitzung(ordner: Path, tmp_path: Path, monkeypatch):
    aufrufe: list[str] = []
    monkeypatch.setitem(sys.modules, "rembg", _falsches_rembg(aufrufe))
    monkeypatch.setenv("MIKSAN_MODELL_ORDNER", str(tmp_path / "modelle"))
    einstellungen = Einstellungen(aktion=logik.HINTERGRUND, ziel_format="png", modell="genau")
    plan = logik.planen([ordner], einstellungen)
    ergebnis = logik.plan_ausfuehren(plan, einstellungen)
    assert len(ergebnis.ok) == 2 and not ergebnis.fehler
    assert aufrufe == ["isnet-general-use"]
    with Image.open(ordner / "a-freigestellt.png") as bild:
        assert bild.mode == "RGBA" and bild.getpixel((0, 0))[3] == 0

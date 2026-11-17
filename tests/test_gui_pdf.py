"""PDF-Seiten der Oberfläche (brauchen [gui] und [pdf])."""

from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("PySide6")
pypdf = pytest.importorskip("pypdf")
pytest.importorskip("pypdfium2")

from PySide6.QtCore import QSettings, Qt  # noqa: E402

from miksan_converter.gui import app, werkzeuge  # noqa: E402
from miksan_converter.gui.seiten.einstellungen import NichtVerfuegbarSeite  # noqa: E402

from .test_pdf import _pdf  # noqa: E402


@pytest.fixture
def fenster(qtbot, tmp_path: Path):
    settings = QSettings(str(tmp_path / "e.ini"), QSettings.Format.IniFormat)
    fenster = app.Hauptfenster(settings)
    qtbot.addWidget(fenster)
    fenster.show()
    return fenster


def _warten(qtbot, seite) -> None:
    qtbot.waitUntil(
        lambda: seite.letztes_ergebnis is not None and not seite.laeuft(), timeout=30_000
    )


def test_bereich_pdf_in_seitenleiste_und_start(fenster, tmp_path: Path):
    texte = [fenster.navigation.item(i).text() for i in range(fenster.navigation.count())]
    assert "PDF" in texte and "PDF zusammenfügen" in texte
    fenster.startseite.dateien_ablegen([str(_pdf(tmp_path / "a.pdf", 2))])
    assert "pdf_teilen" in fenster.startseite.knoepfe
    assert "umwandeln" not in fenster.startseite.knoepfe


def test_zusammenfuegen_in_der_app(qtbot, fenster, tmp_path: Path):
    a, b = _pdf(tmp_path / "a.pdf", 2), _pdf(tmp_path / "b.pdf", 3)
    seite = fenster.werkzeug_oeffnen("pdf_zusammenfuegen", [str(a), str(b)])
    zeile = seite.liste.zeile(str(a))
    qtbot.waitUntil(lambda: "2 Seiten" in zeile.angaben.text(), timeout=10_000)
    seite.liste.verschieben(1, 0)  # b vor a
    assert seite.pfade() == [str(b), str(a)]
    assert seite.liste.zeile(str(b)) is not None
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "aus"))
    seite.dateiname.setText("gesamt")
    seite.starten()
    _warten(qtbot, seite)
    ziel = tmp_path / "aus" / "gesamt.pdf"
    assert len(pypdf.PdfReader(ziel).pages) == 5
    assert seite.status.text() == "Fertig: 2 ok, 0 Fehler"


def test_teilen_jede_seite_und_miniaturen(qtbot, fenster, tmp_path: Path):
    fuenf = _pdf(tmp_path / "fuenf.pdf", 5)
    seite = fenster.werkzeug_oeffnen("pdf_teilen", [str(fuenf)])
    qtbot.waitUntil(lambda: seite.raster.liste.count() == 5, timeout=10_000)
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "teile"))
    seite.starten()
    _warten(qtbot, seite)
    assert len(list((tmp_path / "teile").glob("*.pdf"))) == 5


def test_seiten_markieren_und_bilder(qtbot, fenster, tmp_path: Path):
    fuenf = _pdf(tmp_path / "fuenf.pdf", 5)
    seite = fenster.werkzeug_oeffnen("pdf_bilder", [str(fuenf)])
    qtbot.waitUntil(lambda: seite.raster.liste.count() == 5, timeout=10_000)
    seite.raster.liste.item(1).setSelected(True)
    seite.raster.liste.item(3).setSelected(True)
    assert seite.seiten.text() == "2,4"
    seite.seiten.clear()
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "bilder"))
    seite.starten()
    _warten(qtbot, seite)
    assert len(list((tmp_path / "bilder").glob("*.png"))) == 5


def test_passwort_wird_gefragt(qtbot, fenster, tmp_path: Path, monkeypatch):
    writer = pypdf.PdfWriter(clone_from=_pdf(tmp_path / "offen.pdf", 2))
    writer.encrypt("geheim")
    geschuetzt = tmp_path / "geschuetzt.pdf"
    with open(geschuetzt, "wb") as datei:
        writer.write(datei)
    seite = fenster.werkzeug_oeffnen("pdf_seiten", [str(geschuetzt)])
    antworten = iter(["falsch", "geheim"])
    gefragt = []

    def fragen(pfad, falsch):
        gefragt.append(falsch)
        return next(antworten)

    monkeypatch.setattr(seite, "passwort_fragen", fragen)
    seite.loeschen.setText("1")
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "aus"))
    seite.starten()
    _warten(qtbot, seite)
    assert gefragt == [False, True]
    assert len(pypdf.PdfReader(tmp_path / "aus" / "geschuetzt-bearbeitet.pdf").pages) == 1


def test_defektes_pdf_zeigt_fehler_statt_absturz(qtbot, fenster, tmp_path: Path):
    kaputt = tmp_path / "kaputt.pdf"
    kaputt.write_bytes(b"%PDF-1.4 kaputt")
    seite = fenster.werkzeug_oeffnen("pdf_verkleinern", [str(kaputt)])
    seite.starten()
    _warten(qtbot, seite)
    assert seite.status.text() == "Fertig: 0 ok, 1 Fehler"
    assert "beschädigt" in seite.liste.zeile(str(kaputt)).status.text()


def test_bilder_zu_pdf_in_der_app(qtbot, fenster, tmp_path: Path):
    for i in range(3):
        Image.new("RGB", (60, 40), (80 * i, 0, 0)).save(tmp_path / f"b{i}.png")
    pfade = [str(tmp_path / f"b{i}.png") for i in range(3)]
    seite = fenster.werkzeug_oeffnen("bilder_pdf", pfade)
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "aus"))
    qtbot.keyClick(fenster, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    _warten(qtbot, seite)
    assert len(pypdf.PdfReader(tmp_path / "aus" / "b0.pdf").pages) == 3


def test_ohne_pdf_extra_ausgegraut(qtbot, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(werkzeuge, "extra_installiert", lambda extra: extra != "pdf")
    fenster = app.Hauptfenster(QSettings(str(tmp_path / "x.ini"), QSettings.Format.IniFormat))
    qtbot.addWidget(fenster)
    seite = fenster.seite_zeigen("pdf_teilen")
    assert isinstance(seite, NichtVerfuegbarSeite)
    assert "[pdf]" in seite.hinweis.text()
    assert fenster.seite("umwandeln").werkzeug.verfuegbar()

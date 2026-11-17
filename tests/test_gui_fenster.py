"""Fenster-Tests (brauchen das Extra [gui] und pytest-qt, laufen ohne Bildschirm)."""

import os
import threading
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("PySide6")

from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDropEvent  # noqa: E402

from miksan_converter.gui import app, logik, werkzeuge  # noqa: E402
from miksan_converter.gui.seiten.basis import WerkzeugSeite  # noqa: E402
from miksan_converter.gui.seiten.einstellungen import NichtVerfuegbarSeite  # noqa: E402


def _settings(tmp_path: Path, name: str = "einstellungen.ini") -> QSettings:
    return QSettings(str(tmp_path / name), QSettings.Format.IniFormat)


@pytest.fixture
def fenster(qtbot, tmp_path: Path):
    fenster = app.Hauptfenster(_settings(tmp_path))
    qtbot.addWidget(fenster)
    fenster.show()
    return fenster


@pytest.fixture
def bilder(tmp_path: Path) -> Path:
    ordner = tmp_path / "bilder"
    ordner.mkdir()
    for i in range(3):
        Image.new("RGBA", (60, 40), (50 * i, 100, 0, 255)).save(ordner / f"bild{i}.png")
    return ordner


def _ablegen(ziel, pfade: list[Path]) -> None:
    daten = QMimeData()
    daten.setUrls([QUrl.fromLocalFile(str(pfad)) for pfad in pfade])
    ereignis = QDropEvent(
        QPointF(5, 5),
        Qt.DropAction.CopyAction,
        daten,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    ziel.dropEvent(ereignis)


def _warten(qtbot, seite) -> None:
    qtbot.waitUntil(
        lambda: seite.letztes_ergebnis is not None and not seite.laeuft(), timeout=30_000
    )


def test_seitenleiste_und_startseite_zeigen_alle_werkzeuge(fenster):
    namen = [
        fenster.navigation.item(i).data(Qt.ItemDataRole.UserRole)
        for i in range(fenster.navigation.count())
    ]
    for w in werkzeuge.WERKZEUGE:
        assert w.name in namen
        assert w.name in fenster.startseite.karten
    assert fenster.stapel.currentWidget() is fenster.startseite
    assert fenster.minimumWidth() >= 900 and fenster.minimumHeight() >= 600


def test_jedes_werkzeug_hat_eigene_seite(fenster):
    for w in werkzeuge.WERKZEUGE:
        if not w.verfuegbar():
            continue
        fenster.navigation.setCurrentRow(
            next(
                i
                for i in range(fenster.navigation.count())
                if fenster.navigation.item(i).data(Qt.ItemDataRole.UserRole) == w.name
            )
        )
        seite = fenster.stapel.currentWidget()
        assert isinstance(seite, WerkzeugSeite) and seite.werkzeug is w
    umwandeln = fenster.seite("umwandeln")
    bearbeiten = fenster.seite("bearbeiten")
    assert hasattr(bearbeiten, "zielgroesse") and not hasattr(umwandeln, "zielgroesse")
    assert hasattr(bearbeiten, "drehen") and not hasattr(umwandeln, "drehen")


def test_startseite_bietet_passende_werkzeuge(qtbot, fenster, bilder: Path):
    _ablegen(fenster.startseite.ablage, [bilder / "bild0.png"])
    assert fenster.startseite.auswahl.isVisible()
    assert "umwandeln" in fenster.startseite.knoepfe
    qtbot.mouseClick(fenster.startseite.knoepfe["umwandeln"], Qt.MouseButton.LeftButton)
    seite = fenster.aktuelle_seite()
    assert seite.werkzeug.name == "umwandeln"
    assert seite.pfade() == [str(bilder / "bild0.png")]


def test_fenster_wandelt_um(qtbot, fenster, bilder: Path, tmp_path: Path):
    seite = fenster.werkzeug_oeffnen("umwandeln")
    assert not seite.knopf_start.isEnabled()
    _ablegen(seite.liste, [bilder / "bild0.png", bilder / "bild1.png"])
    assert seite.liste.count() == 2
    seite.format_waehlen("jpeg")
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "aus"))
    seite.max_seite.setValue(30)

    qtbot.mouseClick(seite.knopf_start, Qt.MouseButton.LeftButton)
    _warten(qtbot, seite)

    assert sorted(p.name for p in (tmp_path / "aus").iterdir()) == ["bild0.jpg", "bild1.jpg"]
    with Image.open(tmp_path / "aus" / "bild0.jpg") as bild:
        assert bild.format == "JPEG" and bild.size == (30, 20)
    assert seite.status.text() == "Fertig: 2 ok, 0 Fehler"
    assert seite.ablauf.knopf_oeffnen.isEnabled()
    assert seite.knopf_start.isEnabled()
    zeile = seite.liste.zeile(str(bilder / "bild0.png"))
    assert zeile.status_symbol.pixmap() is not None and not zeile.status.isVisible()


def test_miniaturen_und_angaben(qtbot, fenster, bilder: Path):
    seite = fenster.werkzeug_oeffnen("umwandeln", [str(bilder / "bild1.png")])
    zeile = seite.liste.zeile(str(bilder / "bild1.png"))
    assert zeile.name.text() == "bild1.png"
    assert zeile.toolTip() == str(bilder / "bild1.png")
    qtbot.waitUntil(lambda: "60 × 40" in zeile.angaben.text(), timeout=10_000)
    assert zeile.angaben.text().startswith("PNG")
    qtbot.mouseClick(zeile.knopf_entfernen, Qt.MouseButton.LeftButton)
    assert seite.pfade() == []
    assert seite.dateien_stapel.currentIndex() == 0  # wieder die Ablagefläche


def test_ordner_ablegen_und_fehler_anzeigen(qtbot, fenster, bilder: Path):
    (bilder / "kaputt.png").write_bytes(b"\x89PNG\r\n\x1a\nkaputt")
    seite = fenster.werkzeug_oeffnen("umwandeln")
    _ablegen(fenster, [bilder])  # auf das ganze Fenster
    _ablegen(seite.liste, [bilder])  # doppelt wird ignoriert
    assert seite.pfade() == [str(bilder)]
    seite.format_waehlen("webp")

    seite.starten()
    _warten(qtbot, seite)

    assert len(list(bilder.glob("*.webp"))) == 3
    assert seite.status.text() == "Fertig: 3 ok, 1 Fehler"
    assert seite.ablauf.meldungen.isVisible()
    assert "kaputt.png" in seite.ablauf.meldungen.item(0).text()
    zeile = seite.liste.zeile(str(bilder))
    assert zeile.status.text() == "3 ok, 1 Fehler"


def test_dateien_bleiben_beim_werkzeugwechsel(fenster, bilder: Path, tmp_path: Path):
    andere = tmp_path / "notiz.txt"
    andere.write_text("x")
    umwandeln = fenster.werkzeug_oeffnen("umwandeln", [str(bilder / "bild0.png"), str(andere)])
    assert umwandeln.pfade() == [str(bilder / "bild0.png")]  # .txt passt nicht
    bearbeiten = fenster.seite_zeigen("bearbeiten")
    assert bearbeiten.pfade() == [str(bilder / "bild0.png")]


def test_abbrechen(qtbot, fenster, bilder: Path, tmp_path: Path, monkeypatch):
    weiter = threading.Event()
    original = logik.umwandeln

    def langsam(*args, **kwargs):
        weiter.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(logik, "umwandeln", langsam)
    monkeypatch.setattr(os, "cpu_count", lambda: 1)  # eine Datei nach der anderen
    seite = fenster.werkzeug_oeffnen("umwandeln", [bilder])
    seite.format_waehlen("png")
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "aus"))
    seite.starten()
    assert seite.laeuft() and seite.ablauf.knopf_abbrechen.isEnabled()
    assert fenster.laeuft()
    assert not seite.knopf_start.isEnabled()
    assert not seite.optionen.isEnabled()

    qtbot.keyClick(fenster, Qt.Key.Key_Escape)  # Esc = Abbrechen
    weiter.set()
    _warten(qtbot, seite)

    ergebnis = seite.letztes_ergebnis
    assert len(ergebnis.ok) + len(ergebnis.uebersprungen) == 3
    assert ergebnis.uebersprungen  # mindestens eine Datei wurde nicht mehr gestartet
    assert "abgebrochen" in seite.status.text()
    assert seite.optionen.isEnabled()


def test_tastenkuerzel_starten_und_entfernen(qtbot, fenster, bilder: Path, tmp_path: Path):
    seite = fenster.werkzeug_oeffnen("umwandeln", [str(bilder / "bild0.png")])
    seite.ablauf.ausgabe_ordner.setText(str(tmp_path / "aus"))
    seite.liste.setCurrentRow(0)
    qtbot.keyClick(fenster, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    _warten(qtbot, seite)
    assert seite.letztes_ergebnis.ok
    seite.liste.item(0).setSelected(True)
    qtbot.keyClick(fenster, Qt.Key.Key_Delete)
    assert seite.pfade() == []


def test_einstellungen_werden_gemerkt(qtbot, tmp_path: Path):
    erstes = app.Hauptfenster(_settings(tmp_path))
    qtbot.addWidget(erstes)
    seite = erstes.werkzeug_oeffnen("bearbeiten")
    seite.format_waehlen("webp")
    seite.qualitaet.setValue(70)
    seite.farbe_setzen("#112233")
    erstes.seite("einstellungen").rekursiv.setChecked(True)
    seite.einstellungen_speichern()

    zweites = app.Hauptfenster(_settings(tmp_path))
    qtbot.addWidget(zweites)
    einstellungen = zweites.seite("bearbeiten").einstellungen()
    assert einstellungen.aktion == logik.BEARBEITEN
    assert einstellungen.ziel_format == "webp"
    assert einstellungen.qualitaet == 70
    assert einstellungen.rekursiv
    assert einstellungen.hintergrundfarbe == "#112233"
    # andere Werkzeuge haben eigene Einstellungen
    assert zweites.seite("umwandeln").einstellungen().qualitaet is None


def test_alte_einstellungen_werden_weiter_gelesen(qtbot, tmp_path: Path):
    alt = _settings(tmp_path)
    alt.setValue("ziel_format/umwandeln", "avif")
    alt.setValue("qualitaet", 55)
    alt.setValue("ausgabe_ordner", str(tmp_path / "fertig"))
    alt.setValue("hintergrundfarbe", "#abcdef")
    alt.sync()
    fenster = app.Hauptfenster(_settings(tmp_path))
    qtbot.addWidget(fenster)
    e = fenster.seite("umwandeln").einstellungen()
    assert e.ziel_format == "avif" and e.qualitaet == 55
    assert e.ausgabe_ordner == tmp_path / "fertig"
    assert e.hintergrundfarbe == "#abcdef"
    assert fenster.seite("bearbeiten").einstellungen().ziel_format == logik.WIE_ORIGINAL


def test_ohne_ki_ist_hintergrund_ausgegraut(qtbot, tmp_path: Path, monkeypatch):
    monkeypatch.setattr(werkzeuge, "extra_installiert", lambda extra: False)
    fenster = app.Hauptfenster(_settings(tmp_path, "e.ini"))
    qtbot.addWidget(fenster)
    eintrag = next(
        fenster.navigation.item(i)
        for i in range(fenster.navigation.count())
        if fenster.navigation.item(i).data(Qt.ItemDataRole.UserRole) == "hintergrund"
    )
    assert "[ki]" in eintrag.toolTip()
    seite = fenster.seite_zeigen("hintergrund")
    assert isinstance(seite, NichtVerfuegbarSeite)
    assert "[ki]" in seite.hinweis.text()
    assert fenster.seite("umwandeln").werkzeug.verfuegbar()


def test_fehlerhafte_eingabe_zeigt_meldung(fenster, bilder: Path, monkeypatch):
    meldungen = []
    seite = fenster.werkzeug_oeffnen("bearbeiten", [bilder])
    monkeypatch.setattr(seite, "_melden", lambda titel, text: meldungen.append(text))
    seite.zielgroesse.setText("riesig")
    seite.starten()
    assert not seite.laeuft()
    assert "ungültig" in meldungen[0]


def test_hintergrund_fragt_vor_dem_download(fenster, bilder: Path, monkeypatch, tmp_path):
    monkeypatch.setattr(werkzeuge, "extra_installiert", lambda extra: True)
    monkeypatch.setenv("MIKSAN_MODELL_ORDNER", str(tmp_path / "modelle"))
    gefragt = []

    seite = fenster.werkzeug_oeffnen("hintergrund", [bilder])

    def ablehnen(modell):
        gefragt.append(modell)
        return False

    monkeypatch.setattr(seite, "_modell_download_bestaetigen", ablehnen)
    seite.starten()
    assert gefragt == ["klein"]
    assert not seite.laeuft()


def test_einstellungen_seite_loescht_modelle(fenster, tmp_path: Path, monkeypatch):
    modelle = tmp_path / "modelle"
    (modelle / "models" / "u2netp").mkdir(parents=True)
    (modelle / "models" / "u2netp" / "u2netp.onnx").write_bytes(b"x" * 10)
    monkeypatch.setenv("MIKSAN_MODELL_ORDNER", str(modelle))
    seite = fenster.seite_zeigen("einstellungen")
    assert "1 Modelle" in seite.modell_groesse.text()
    monkeypatch.setattr(seite, "_bestaetigen", lambda text: True)
    seite.modelle_loeschen()
    assert not modelle.exists()
    assert not seite.knopf_loeschen.isEnabled()


def test_info_seite(fenster):
    from PySide6.QtWidgets import QLabel

    from miksan_converter import __version__

    seite = fenster.seite_zeigen("info")
    texte = " ".join(label.text() for label in seite.findChildren(QLabel))
    assert __version__ in texte
    assert "ohne Telemetrie" in texte and "LGPL-3.0" in texte
    assert "github.com/Louidos/Miksan-Converter" in texte


def test_keine_datei_in_gui_zu_lang():
    from miksan_converter import gui

    for datei in Path(gui.__file__).parent.rglob("*.py"):
        zeilen = len(datei.read_text(encoding="utf-8").splitlines())
        assert zeilen <= 430, (datei, zeilen)


def test_programm_icon():
    assert not app.programm_icon().isNull()


def test_selbsttest_fenster(qtbot):
    from miksan_converter.gui import selbsttest

    zeilen: list[str] = []
    assert selbsttest._fenster_pruefen(zeilen)
    assert zeilen == ["ok      Fenster: Fertig: 1 ok, 0 Fehler"]


def test_selbsttest_bericht(qtbot, tmp_path: Path, monkeypatch):
    from miksan_converter import gui
    from miksan_converter.gui import selbsttest

    monkeypatch.setattr(selbsttest, "MODULE", ("PIL", "gibt_es_nicht_123"))
    bericht = tmp_path / "bericht.txt"
    monkeypatch.setattr("sys.argv", ["miksan-gui", "--selbsttest", str(bericht)])
    assert gui.main() == 1
    text = bericht.read_text(encoding="utf-8")
    assert "ok      PIL" in text
    assert "FEHLER  gibt_es_nicht_123" in text
    assert "ok      Design" in text
    assert "Ergebnis: FEHLER" in text


def test_design_kontrast_und_masse():
    from miksan_converter.gui import design

    for vorne, hinten in (
        (design.TEXT, design.HINTERGRUND),
        (design.TEXT, design.FLAECHE),
        (design.NEBENTEXT, design.HINTERGRUND),
        (design.NEBENTEXT, design.FLAECHE),
        (design.AUF_AKZENT, design.AKZENT),
        (design.AKZENT, design.HINTERGRUND),
        (design.FEHLER, design.HINTERGRUND),
        (design.ERFOLG, design.HINTERGRUND),
    ):
        assert design.kontrast(vorne, hinten) >= 4.5, (vorne, hinten)
    assert design.RADIUS == 8 and design.abstand(2) == 16


def test_design_angewendet(qtbot):
    from PySide6.QtWidgets import QApplication

    from miksan_converter.gui import design

    app = QApplication.instance()
    design.anwenden(app)
    try:
        assert app.property("miksan_design")
        assert app.palette().window().color().name().upper() == design.HINTERGRUND
        assert design.AKZENT in app.styleSheet()
        assert len(design.icon_namen()) >= 20
        for name in design.icon_namen():
            assert not design.icon(name).pixmap(24, 24).isNull(), name
    finally:
        app.setStyleSheet("")


def test_keine_verstreuten_farben():
    """Farben stehen nur in gui/design.py, nicht als setStyleSheet in anderen Dateien."""
    from miksan_converter import gui

    ordner = Path(gui.__file__).parent
    for datei in ordner.rglob("*.py"):
        if datei.name == "design.py":
            continue
        text = datei.read_text(encoding="utf-8")
        assert "setStyleSheet(" not in text, datei
        assert "color:" not in text, datei

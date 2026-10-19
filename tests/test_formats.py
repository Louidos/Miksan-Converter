import pytest

from miksan_converter.cli import main
from miksan_converter.fehler import BedienFehler
from miksan_converter.formats import alle_formate, format_aus_name, pil_kann_schreiben


def test_formats_listet_alle(capsys):
    assert main(["formats"]) == 0
    ausgabe = capsys.readouterr().out
    assert "Lesen" in ausgabe and "Schreiben" in ausgabe
    for fmt in alle_formate():
        assert fmt.name in ausgabe


@pytest.mark.parametrize("name, erwartet", [("jpg", "jpeg"), (".TIF", "tiff"), ("png", "png")])
def test_format_aus_name(name, erwartet):
    assert format_aus_name(name).name == erwartet


def test_unbekannter_name():
    with pytest.raises(BedienFehler):
        format_aus_name("abc")


def test_schreibbare_formate_kann_pillow_schreiben():
    for fmt in alle_formate():
        if fmt.schreiben:
            assert pil_kann_schreiben(fmt), fmt.name

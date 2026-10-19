"""Jedes Paar aus Quell- und Zielformat umwandeln und das Ergebnis wieder öffnen."""

from pathlib import Path

import pytest
from PIL import Image

from miksan_converter.convert import umwandeln
from miksan_converter.formats import alle_formate, format_nach_name

from .conftest import testbilder_erzeugen as tb

QUELLEN = list(tb.QUELLEN)
ZIELE = [fmt.name for fmt in alle_formate() if fmt.schreiben]
TOLERANZ = 40


def _nah(farbe, erwartet, toleranz=TOLERANZ) -> bool:
    return all(abs(a - b) <= toleranz for a, b in zip(farbe[:3], erwartet[:3], strict=True))


@pytest.mark.parametrize("ziel_name", ZIELE)
@pytest.mark.parametrize("quelle_name", QUELLEN)
def test_umwandeln_und_wieder_oeffnen(testbilder, tmp_path: Path, quelle_name, ziel_name):
    ziel = format_nach_name(ziel_name)
    ausgabe = tmp_path / f"ergebnis{ziel.endung}"

    ergebnis = umwandeln(testbilder[quelle_name], ausgabe)

    assert ergebnis.eingabe_format == quelle_name
    assert ausgabe.exists()
    if ziel_name == "pdf":
        assert ausgabe.read_bytes().startswith(b"%PDF")
        return

    with Image.open(ausgabe) as bild:
        bild.load()
        assert bild.format == ziel.pil_name
        # ICO wird quadratisch aufgefüllt (oben und unten je 4 Pixel)
        versatz = 4 if ziel_name == "ico" or quelle_name == "ico" else 0
        if ziel_name == "ico":
            assert bild.size == (32, 32)
        elif quelle_name == "ico":
            assert bild.size == (32, 32)
        else:
            assert bild.size == (tb.BREITE, tb.HOEHE)
        rgba = bild.convert("RGBA")

    deckend = rgba.getpixel((20, 12 + versatz))
    assert deckend[3] == 255
    assert _nah(deckend, tb.FARBE), deckend

    quelle_transparent = tb.QUELLEN[quelle_name][2]
    if not quelle_transparent:
        return
    durchsichtig = rgba.getpixel((2, 12 + versatz))
    if ziel.alpha:
        assert durchsichtig[3] == 0, durchsichtig
    else:
        assert _nah(durchsichtig, (255, 255, 255), 10), durchsichtig

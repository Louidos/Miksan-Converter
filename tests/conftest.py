from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def png_datei(tmp_path: Path) -> Path:
    """Kleines, halbtransparentes PNG."""
    pfad = tmp_path / "foto.png"
    bild = Image.new("RGBA", (40, 30), (200, 30, 30, 255))
    bild.paste((0, 0, 0, 0), (0, 0, 20, 30))
    bild.save(pfad)
    return pfad

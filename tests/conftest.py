import importlib.util
import os
from pathlib import Path

import pytest
from PIL import Image

# Fenster-Tests brauchen das Extra [gui]; ohne PySide6 wird pytest-qt gar nicht erst geladen
QT_VORHANDEN = importlib.util.find_spec("PySide6") is not None
pytest_plugins = ["pytestqt.plugin"] if QT_VORHANDEN else []
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_SKRIPT = Path(__file__).resolve().parent.parent / "scripts" / "testbilder_erzeugen.py"
_spec = importlib.util.spec_from_file_location("testbilder_erzeugen", _SKRIPT)
testbilder_erzeugen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(testbilder_erzeugen)


@pytest.fixture(scope="session")
def testbilder(tmp_path_factory) -> dict[str, Path]:
    """Alle Testbilder aus scripts/testbilder_erzeugen.py (einmal pro Testlauf erzeugt)."""
    return testbilder_erzeugen.erzeugen(tmp_path_factory.mktemp("testbilder"))


@pytest.fixture
def png_datei(tmp_path: Path) -> Path:
    """Kleines, halbtransparentes PNG."""
    pfad = tmp_path / "foto.png"
    bild = Image.new("RGBA", (40, 30), (200, 30, 30, 255))
    bild.paste((0, 0, 0, 0), (0, 0, 20, 30))
    bild.save(pfad)
    return pfad


def pytest_addoption(parser):
    parser.addoption("--slow", action="store_true", help="auch langsame Tests mit echtem Modell")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--slow"):
        return
    ueberspringen = pytest.mark.skip(reason="langsamer Test, nur mit --slow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(ueberspringen)

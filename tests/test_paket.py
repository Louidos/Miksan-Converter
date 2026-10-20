import miksan_converter


def test_paket_hat_version():
    assert isinstance(miksan_converter.__version__, str)


def test_version_wie_in_pyproject():
    """Der Windows-Installer liest die Version aus pyproject.toml, das Programm aus __init__."""
    import tomllib
    from pathlib import Path

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject, "rb") as datei:
        assert tomllib.load(datei)["project"]["version"] == miksan_converter.__version__

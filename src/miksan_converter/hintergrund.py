"""Hintergrund entfernen mit einem lokalen KI-Modell (rembg, ONNX auf der CPU)."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops

from .convert import (
    STANDARD_HINTERGRUND,
    Bild,
    farbe_parsen,
    hinweise_zum_laden,
    laden,
    speichern,
    ziel_bestimmen,
    ziel_pruefen,
)
from .fehler import BedienFehler, ExtraFehlt, MiksanFehler
from .formats import Format, format_aus_name

# Kurznamen -> rembg-Modell
MODELLE = {
    "klein": "u2netp",
    "genau": "isnet-general-use",
    "person": "u2net_human_seg",
    "sehr-genau": "birefnet-general",
}
STANDARD_MODELL = "klein"


@dataclass
class HintergrundErgebnis:
    eingabe: Path
    ausgabe: Path
    ausgabe_format: Format
    modell: str
    hinweise: list[str] = field(default_factory=list)


def modell_ordner() -> Path:
    """Ordner, in dem die Modelle nach dem ersten Herunterladen liegen.

    Reihenfolge: ``MIKSAN_MODELL_ORDNER``, dann ein bereits gesetztes ``REMBG_HOME`` bzw.
    ``U2NET_HOME`` (von rembg), sonst der übliche Cache-Ordner des Betriebssystems.
    """
    eigener = os.environ.get("MIKSAN_MODELL_ORDNER")
    if eigener:
        return Path(eigener).expanduser()
    for variable in ("REMBG_HOME", "U2NET_HOME"):
        if os.environ.get(variable):
            return Path(os.environ[variable]).expanduser()
    if sys.platform == "win32":
        basis = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        basis = Path.home() / "Library" / "Caches"
    else:
        basis = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return basis / "miksan-converter" / "modelle"


def _rembg():
    try:
        import rembg
    except ImportError as fehler:
        raise ExtraFehlt("ki", "Das Entfernen des Hintergrunds") from fehler
    return rembg


def modell_name(modell: str) -> str:
    return MODELLE.get(modell.lower(), modell)


def sitzung_erstellen(modell: str = STANDARD_MODELL):
    """Lädt das Modell (beim ersten Mal aus dem Internet, danach aus dem lokalen Ordner)."""
    rembg = _rembg()
    name = modell_name(modell)
    bekannte = getattr(getattr(rembg, "sessions", None), "sessions_names", None)
    if bekannte is not None and name not in bekannte:
        auswahl = ", ".join(MODELLE)
        raise BedienFehler(
            f"Unbekanntes Modell '{modell}'. Möglich sind: {auswahl} oder ein rembg-Modellname."
        )
    ordner = modell_ordner()
    ordner.mkdir(parents=True, exist_ok=True)
    os.environ["REMBG_HOME"] = str(ordner)
    os.environ["U2NET_HOME"] = str(ordner)
    try:
        return rembg.new_session(name)
    except Exception as fehler:  # Download- und ONNX-Fehler haben viele Klassen
        raise MiksanFehler(
            f"Das Modell '{name}' konnte nicht geladen werden. Beim ersten Mal wird es aus dem "
            f"Internet geladen und in '{ordner}' gespeichert. Ursache: {fehler}"
        ) from fehler


def maske_berechnen(bild: Image.Image, sitzung) -> Image.Image:
    """Gibt die Vordergrundmaske (Modus L, 255 = Vordergrund) zurück."""
    rembg = _rembg()
    maske = rembg.remove(bild.convert("RGB"), session=sitzung, only_mask=True)
    if not isinstance(maske, Image.Image):
        raise MiksanFehler("Das Modell hat keine gültige Maske geliefert.")
    maske = maske.convert("L")
    if maske.size != bild.size:
        maske = maske.resize(bild.size, Image.Resampling.LANCZOS)
    return maske


def freistellen(bild: Image.Image, maske: Image.Image) -> Image.Image:
    """Legt die Maske als Transparenz auf das Bild (vorhandene Transparenz bleibt erhalten)."""
    rgba = bild.convert("RGBA")
    alpha = ImageChops.multiply(rgba.getchannel("A"), maske)
    rgba.putalpha(alpha)
    return rgba


def standard_ausgabe(eingabe: Path, ziel: Format, nur_maske: bool) -> Path:
    zusatz = "-maske" if nur_maske else "-freigestellt"
    return eingabe.with_name(f"{eingabe.stem}{zusatz}{ziel.endung}")


def hintergrund_entfernen(
    eingabe: Path,
    ausgabe: Path | None = None,
    *,
    to: str | None = None,
    modell: str = STANDARD_MODELL,
    nur_maske: bool = False,
    hintergrund: tuple[int, int, int] | str = STANDARD_HINTERGRUND,
    overwrite: bool = False,
    seite: int | None = None,
    sitzung=None,
) -> HintergrundErgebnis:
    """Entfernt den Hintergrund von ``eingabe`` und speichert das Ergebnis als neue Datei.

    Ohne Ausgabe entsteht ``<name>-freigestellt.png`` (bzw. ``-maske``) neben dem Original.
    """
    eingabe = Path(eingabe)
    if isinstance(hintergrund, str):
        hintergrund = farbe_parsen(hintergrund)
    if ausgabe is None:
        ziel_format = format_aus_name(to or "png")
        ziel_pfad = standard_ausgabe(eingabe, ziel_format, nur_maske)
    else:
        ziel_pfad, ziel_format = ziel_bestimmen(eingabe, Path(ausgabe), to)
    ziel_pruefen(eingabe, ziel_pfad, overwrite)

    quelle = laden(eingabe, seite=seite)
    hinweise = hinweise_zum_laden(eingabe, quelle, seite)
    if sitzung is None:
        sitzung = sitzung_erstellen(modell)

    maske = maske_berechnen(quelle.frames[0], sitzung)
    ergebnis_bild = maske if nur_maske else freistellen(quelle.frames[0], maske)
    ausgabe_bild = Bild(
        frames=[ergebnis_bild],
        quelle=quelle.quelle,
        dauern=[0],
        icc=None if nur_maske else quelle.icc,
        exif=quelle.exif,
        xmp=quelle.xmp,
        verlustfrei=True,
    )
    speichern(ausgabe_bild, ziel_pfad, ziel_format, overwrite=overwrite, hintergrund=hintergrund)
    return HintergrundErgebnis(eingabe, ziel_pfad, ziel_format, modell_name(modell), hinweise)

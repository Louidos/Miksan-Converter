"""Hintergrund entfernen mit einem lokalen KI-Modell (rembg, ONNX auf der CPU)."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
import threading
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps

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


@dataclass(frozen=True)
class ModellInfo:
    titel: str
    groesse_mb: int
    text: str
    url: str
    md5: str
    lizenz: str


_RELEASE = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/"
MODELL_INFOS = {
    "klein": ModellInfo(
        "Klein",
        5,
        "schnell, gut für die meisten Motive",
        _RELEASE + "u2netp.onnx",
        "8e83ca70e441ab06c318d82300c84806",
        "Apache-2.0",
    ),
    "genau": ModellInfo(
        "Genau",
        180,
        "genauere Kanten, etwas langsamer",
        _RELEASE + "isnet-general-use.onnx",
        "fc16ebd8b0c10d971d3513d564d01e29",
        "Apache-2.0",
    ),
    "person": ModellInfo(
        "Person",
        170,
        "für Personen und Porträts",
        _RELEASE + "u2net_human_seg.onnx",
        "c09ddc2e0104f800e3e1bb4652583d1f",
        "Apache-2.0",
    ),
    "sehr-genau": ModellInfo(
        "Sehr genau",
        970,
        "am genauesten, langsam und gross",
        _RELEASE + "BiRefNet-general-epoch_244.onnx",
        "7a35a0141cbbc80de11d9c9a28f52697",
        "MIT",
    ),
}

# Neuer Hintergrund nach dem Freistellen
TRANSPARENT = "transparent"
FARBE = "farbe"
BILD = "bild"
WEICH = "weich"
NEUE_HINTERGRUENDE = (TRANSPARENT, FARBE, BILD, WEICH)
STANDARD_UNSCHAERFE = 20
MAX_KANTE = 50


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


def mitgelieferte_modelle() -> Path | None:
    """Ordner mit Modellen, die der Windows-Installer mitbringt (sonst ``None``)."""
    basis = getattr(sys, "_MEIPASS", None)
    if basis is None:
        return None
    ordner = Path(basis) / "miksan_modelle"
    return ordner if ordner.is_dir() else None


def _mitgelieferte_bereitstellen(ordner: Path) -> None:
    """Kopiert mitgelieferte Modelle einmal in den Modellordner (dort sucht rembg)."""
    quelle = mitgelieferte_modelle()
    if quelle is None:
        return
    for datei in quelle.glob("*.onnx"):
        ziel = ordner / datei.name
        if not ziel.exists():
            ordner.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(datei, ziel)


def modell_vorhanden(modell: str) -> bool:
    """Liegt das Modell schon lokal (auch mitgeliefert)? Sonst wird es heruntergeladen.

    Neuere rembg-Versionen legen Modelle unter ``models/<name>/`` ab, ältere direkt im Ordner.
    """
    ordner = modell_ordner()
    name = modell_name(modell)
    if (ordner / f"{name}.onnx").is_file():
        return True
    unterordner = ordner / "models" / name
    if unterordner.is_dir() and any(unterordner.glob("*.onnx")):
        return True
    quelle = mitgelieferte_modelle()
    return quelle is not None and (quelle / f"{name}.onnx").is_file()


def modell_herunterladen(
    modell: str,
    fortschritt: Callable[[int, int], None] | None = None,
    abbrechen: threading.Event | None = None,
) -> Path:
    """Lädt ein Modell (nur nach Bestätigung im Fenster) in den Modellordner.

    Die Prüfsumme muss stimmen; eine halbe Datei bleibt nie liegen.
    """
    info = MODELL_INFOS.get(modell)
    if info is None:
        raise BedienFehler(f"Für '{modell}' gibt es keinen Download-Knopf; bitte über rembg laden.")
    ordner = modell_ordner()
    ordner.mkdir(parents=True, exist_ok=True)
    ziel = ordner / f"{modell_name(modell)}.onnx"
    teil = ziel.with_suffix(".onnx.teil")
    pruefsumme = hashlib.md5(usedforsecurity=False)
    try:
        with urllib.request.urlopen(info.url, timeout=30) as antwort, open(teil, "wb") as datei:
            gesamt = int(antwort.headers.get("Content-Length") or 0)
            fertig = 0
            while block := antwort.read(1 << 16):
                if abbrechen is not None and abbrechen.is_set():
                    raise MiksanFehler("Download abgebrochen.")
                datei.write(block)
                pruefsumme.update(block)
                fertig += len(block)
                if fortschritt is not None:
                    fortschritt(fertig, gesamt)
        if pruefsumme.hexdigest() != info.md5:
            raise MiksanFehler(f"Das Modell '{modell}' ist beim Herunterladen beschädigt worden.")
        teil.replace(ziel)
    except MiksanFehler:
        teil.unlink(missing_ok=True)
        raise
    except OSError as fehler:
        teil.unlink(missing_ok=True)
        raise MiksanFehler(
            f"Das Modell '{modell}' konnte nicht geladen werden (Internet?): {fehler}"
        ) from fehler
    return ziel


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
    _mitgelieferte_bereitstellen(ordner)
    if os.environ.get("MIKSAN_KEIN_DOWNLOAD") and not modell_vorhanden(modell):
        raise MiksanFehler(
            f"Das Modell '{name}' liegt nicht in '{ordner}' und darf nicht geladen werden "
            "(MIKSAN_KEIN_DOWNLOAD ist gesetzt)."
        )
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


def kante_weicher(maske: Image.Image, pixel: float) -> Image.Image:
    """Macht den Rand der Maske um etwa ``pixel`` Pixel weich (0 = unverändert)."""
    if pixel <= 0:
        return maske
    return maske.filter(ImageFilter.GaussianBlur(pixel / 2))


def zusammensetzen(
    bild: Image.Image,
    maske: Image.Image,
    *,
    neuer_hintergrund: str = TRANSPARENT,
    farbe: tuple[int, int, int] = (255, 255, 255),
    ersatz: Image.Image | None = None,
    unschaerfe: int = STANDARD_UNSCHAERFE,
) -> Image.Image:
    """Legt das freigestellte Motiv auf den neuen Hintergrund (Ergebnis RGBA)."""
    vorne = freistellen(bild, maske)
    if neuer_hintergrund == TRANSPARENT:
        return vorne
    if neuer_hintergrund == FARBE:
        hinten = Image.new("RGBA", vorne.size, (*farbe, 255))
    elif neuer_hintergrund == BILD:
        if ersatz is None:
            raise BedienFehler("Für einen neuen Hintergrund als Bild fehlt das Bild.")
        hinten = ImageOps.fit(ersatz.convert("RGBA"), vorne.size, Image.Resampling.LANCZOS)
        hinten.putalpha(255)
    elif neuer_hintergrund == WEICH:
        hinten = bild.convert("RGBA").filter(ImageFilter.GaussianBlur(max(1, unschaerfe)))
        hinten.putalpha(255)
    else:
        raise BedienFehler(
            f"Unbekannter Hintergrund '{neuer_hintergrund}'. Möglich: "
            + ", ".join(NEUE_HINTERGRUENDE)
        )
    return Image.alpha_composite(hinten, vorne)


def ersatz_laden(pfad: str | Path) -> Image.Image:
    """Lädt das Bild für einen neuen Hintergrund (alle Formate wie beim Umwandeln)."""
    return laden(Path(pfad)).frames[0]


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
    kante: float = 0,
    neuer_hintergrund: str = TRANSPARENT,
    ersatz_farbe: tuple[int, int, int] | str = (255, 255, 255),
    ersatz_bild: str | Path | Image.Image | None = None,
    unschaerfe: int = STANDARD_UNSCHAERFE,
    maske: Image.Image | None = None,
) -> HintergrundErgebnis:
    """Entfernt den Hintergrund von ``eingabe`` und speichert das Ergebnis als neue Datei.

    Ohne Ausgabe entsteht ``<name>-freigestellt.png`` (bzw. ``-maske``) neben dem Original.
    ``kante`` macht den Rand weicher, ``neuer_hintergrund`` (``farbe``, ``bild``, ``weich``)
    legt das Motiv auf einen neuen Hintergrund statt auf Transparenz.
    """
    eingabe = Path(eingabe)
    if not 0 <= kante <= MAX_KANTE:
        raise BedienFehler(f"--kante muss zwischen 0 und {MAX_KANTE} Pixel liegen.")
    if neuer_hintergrund not in NEUE_HINTERGRUENDE:
        raise BedienFehler(f"Unbekannter Hintergrund '{neuer_hintergrund}'.")
    if nur_maske and neuer_hintergrund != TRANSPARENT:
        raise BedienFehler("--nur-maske lässt sich nicht mit einem neuen Hintergrund verbinden.")
    if isinstance(ersatz_farbe, str):
        ersatz_farbe = farbe_parsen(ersatz_farbe)
    ersatz = None
    if neuer_hintergrund == BILD:
        if ersatz_bild is None:
            raise BedienFehler("Für einen neuen Hintergrund als Bild fehlt das Bild.")
        ersatz = ersatz_bild if isinstance(ersatz_bild, Image.Image) else ersatz_laden(ersatz_bild)
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
    if maske is None:
        if sitzung is None:
            sitzung = sitzung_erstellen(modell)
        maske = maske_berechnen(quelle.frames[0], sitzung)
    maske = kante_weicher(maske, kante)
    if nur_maske:
        ergebnis_bild = maske
    else:
        ergebnis_bild = zusammensetzen(
            quelle.frames[0],
            maske,
            neuer_hintergrund=neuer_hintergrund,
            farbe=ersatz_farbe,
            ersatz=ersatz,
            unschaerfe=unschaerfe,
        )
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

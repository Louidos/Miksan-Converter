"""Bilder laden, für das Zielformat vorbereiten und sicher speichern."""

from __future__ import annotations

import io
import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pillow_heif
from PIL import Image, ImageCms, ImageColor, ImageSequence, UnidentifiedImageError

from . import extras
from .fehler import BedienFehler, MiksanFehler
from .formats import (
    Format,
    format_aus_endung,
    format_aus_name,
    format_aus_pil,
    ist_raw_signatur,
    ist_raw_tiff,
    ist_svg,
    kopf_lesen,
)

pillow_heif.register_heif_opener()

STANDARD_HINTERGRUND = (255, 255, 255)
ICO_GROESSEN = (16, 24, 32, 48, 64, 128, 256)

_DEUTSCHE_FARBEN = {
    "weiss": "white",
    "weiß": "white",
    "schwarz": "black",
    "rot": "red",
    "gruen": "green",
    "grün": "green",
    "blau": "blue",
    "gelb": "yellow",
    "grau": "gray",
}

_ANIMIERTE_QUELLEN = {"GIF", "WEBP", "PNG", "APNG", "AVIF", "HEIF"}
# Ziele, die Transparenz in Palettenbildern speichern können
_PALETTE_TRANSPARENZ = {"png", "gif"}
_GRAU_MODI = {"1", "L", "LA", "I", "I;16", "I;16B", "I;16L", "I;16N", "F"}
_SRGB = ImageCms.createProfile("sRGB")


@dataclass
class Bild:
    """Ein geladenes Bild mit allen Einzelbildern und Metadaten."""

    frames: list[Image.Image]
    quelle: str
    dauern: list[int] = field(default_factory=list)
    loop: int = 0
    animation: bool = False
    seiten_gesamt: int = 1
    icc: bytes | None = None
    exif: bytes | None = None
    xmp: bytes | None = None
    ico_bilder: list[Image.Image] = field(default_factory=list)
    verlustfrei: bool = True


@dataclass
class Ergebnis:
    eingabe: Path
    ausgabe: Path
    eingabe_format: str
    ausgabe_format: Format
    hinweise: list[str] = field(default_factory=list)


# --- Hilfen -------------------------------------------------------------------


def farbe_parsen(text: str) -> tuple[int, int, int]:
    """Liest eine Farbe wie ``#ffffff``, ``white`` oder ``weiss``."""
    wert = _DEUTSCHE_FARBEN.get(text.strip().lower(), text.strip())
    try:
        farbe = ImageColor.getrgb(wert)
    except ValueError as fehler:
        raise BedienFehler(
            f"Unbekannte Farbe '{text}'. Beispiele: #ffffff, #000000, weiss, schwarz."
        ) from fehler
    return farbe[0], farbe[1], farbe[2]


def ziel_bestimmen(eingabe: Path, ausgabe: Path | None, to: str | None) -> tuple[Path, Format]:
    """Ermittelt Zieldatei und Zielformat aus Ausgabepfad und/oder ``--to``."""
    ziel_format = format_aus_name(to) if to else None
    if ausgabe is None:
        if ziel_format is None:
            raise BedienFehler("Bitte eine Ausgabedatei oder ein Zielformat mit --to angeben.")
        return eingabe.with_suffix(ziel_format.endung), ziel_format

    endungs_format = format_aus_endung(ausgabe)
    if ziel_format is None:
        if endungs_format is None:
            raise BedienFehler(
                f"Zielformat von '{ausgabe}' ist unbekannt. Bitte eine bekannte Endung "
                "verwenden oder das Format mit --to angeben."
            )
        if not endungs_format.schreiben:
            raise BedienFehler(
                f"Das Format '{endungs_format.name}' kann nur gelesen, nicht geschrieben werden."
            )
        ziel_format = endungs_format
    elif endungs_format is not None and endungs_format != ziel_format:
        raise BedienFehler(
            f"Die Endung von '{ausgabe}' passt nicht zu --to {to}. "
            "Bitte nur eines angeben oder beides passend wählen."
        )
    return ausgabe, ziel_format


def _icc_farbraum(icc: bytes | None) -> bytes | None:
    if not icc or len(icc) < 20:
        return None
    return icc[16:20]


def _hat_transparenz(bild: Image.Image) -> bool:
    return bild.mode in ("RGBA", "LA", "PA", "RGBa", "La") or "transparency" in bild.info


def _auf_8bit(bild: Image.Image) -> Image.Image:
    """Wandelt 16-Bit- und Fliesskomma-Graustufen sauber in 8 Bit um (statt abzuschneiden)."""
    if bild.mode == "F":
        _, hoch = bild.getextrema()
        faktor = 255.0 if hoch <= 1.0 else 1.0
        return bild.point(lambda v: v * faktor).convert("L")
    ganz = bild.convert("I")
    _, hoch = ganz.getextrema()
    if bild.mode.startswith("I;16") or hoch > 255:
        ganz = ganz.point(lambda v: v * (1 / 256))
    return ganz.convert("L")


# --- Laden --------------------------------------------------------------------


def _pillow_oeffnen(pfad: Path) -> Image.Image:
    try:
        return Image.open(pfad)
    except UnidentifiedImageError as fehler:
        raise MiksanFehler(f"'{pfad}' ist kein unterstütztes Bild.") from fehler
    except Image.DecompressionBombError as fehler:
        raise MiksanFehler(f"'{pfad}' ist ungewöhnlich gross und wurde nicht geöffnet.") from fehler
    except OSError as fehler:
        raise MiksanFehler(f"'{pfad}' ist beschädigt oder unvollständig.") from fehler


def _ausrichten(frame: Image.Image, methode: Image.Transpose | None) -> Image.Image:
    return frame.transpose(methode) if methode is not None else frame


_AUSRICHTUNG = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}


def laden(pfad: Path, *, seite: int | None = None, ziel: Format | None = None) -> Bild:
    """Lädt ein Bild. Das Format wird am Inhalt erkannt, die EXIF-Ausrichtung angewendet.

    ``seite`` (ab 1) wählt eine Seite bzw. ein Einzelbild. Ohne ``seite`` werden alle
    Einzelbilder geladen, wenn ``ziel`` sie aufnehmen kann (mehrseitig oder Animation),
    sonst nur das erste.
    """
    pfad = Path(pfad)
    if not pfad.exists():
        raise MiksanFehler(f"Datei nicht gefunden: {pfad}")
    if pfad.is_dir():
        raise MiksanFehler(f"'{pfad}' ist ein Ordner, keine Bilddatei.")
    try:
        kopf = kopf_lesen(pfad)
    except OSError as fehler:
        raise MiksanFehler(f"'{pfad}' kann nicht gelesen werden: {fehler}") from fehler

    if ist_svg(kopf):
        return _einzelbild(extras.svg_laden(pfad), "svg", seite)
    if ist_raw_signatur(kopf):
        return _einzelbild(extras.raw_laden(pfad), "raw", seite, verlustfrei=False)

    bild = _pillow_oeffnen(pfad)
    if bild.format == "TIFF" and ist_raw_tiff(bild):
        bild.close()
        return _einzelbild(extras.raw_laden(pfad), "raw", seite, verlustfrei=False)

    try:
        return _pillow_laden(bild, pfad, seite, ziel)
    except Image.DecompressionBombError as fehler:
        raise MiksanFehler(f"'{pfad}' ist ungewöhnlich gross und wurde nicht geöffnet.") from fehler
    except (OSError, SyntaxError, ValueError, EOFError) as fehler:
        raise MiksanFehler(f"'{pfad}' ist beschädigt oder unvollständig.") from fehler
    finally:
        bild.close()


def _einzelbild(bild: Image.Image, quelle: str, seite: int | None, verlustfrei=True) -> Bild:
    if seite not in (None, 1):
        raise BedienFehler(f"Die Eingabe hat nur 1 Seite, --page {seite} gibt es nicht.")
    return Bild(frames=[bild], quelle=quelle, dauern=[0], verlustfrei=verlustfrei)


def _pillow_laden(bild: Image.Image, pfad: Path, seite: int | None, ziel: Format | None) -> Bild:
    fmt = format_aus_pil(bild.format)
    quelle = fmt.name if fmt else (bild.format or "unbekannt").lower()
    anzahl = getattr(bild, "n_frames", 1)
    animation = anzahl > 1 and bild.format in _ANIMIERTE_QUELLEN

    exif = bild.getexif()
    methode = _AUSRICHTUNG.get(exif.get(0x0112, 1))

    if seite is not None:
        if not 1 <= seite <= anzahl:
            raise BedienFehler(f"'{pfad}' hat {anzahl} Seite(n), --page {seite} gibt es nicht.")
        indizes = [seite - 1]
    elif ziel is not None and (ziel.mehrseitig or (ziel.animation and animation)):
        indizes = list(range(anzahl))
    else:
        indizes = [0]

    frames: list[Image.Image] = []
    dauern: list[int] = []
    for index, frame in enumerate(ImageSequence.Iterator(bild)):
        if index not in indizes:
            if index > max(indizes):
                break
            continue
        frame.load()
        kopie = frame.copy()
        kopie.info = dict(frame.info)
        frames.append(_ausrichten(kopie, methode))
        dauern.append(int(frame.info.get("duration") or 100))

    erstes = bild
    erstes.seek(0)
    ergebnis = Bild(
        frames=frames,
        quelle=quelle,
        dauern=dauern,
        loop=int(erstes.info.get("loop", 0) or 0),
        animation=animation and len(frames) > 1,
        seiten_gesamt=anzahl,
        icc=erstes.info.get("icc_profile") or None,
        xmp=_xmp_lesen(erstes),
        verlustfrei=not (fmt and fmt.verlustbehaftet),
    )
    if methode is not None:
        exif[0x0112] = 1
    ergebnis.exif = exif.tobytes() if len(exif) else None
    if ergebnis.xmp and methode is not None:
        ergebnis.xmp = _xmp_ohne_ausrichtung(ergebnis.xmp)
    if quelle == "ico" and len(indizes) == 1 and indizes[0] == 0:
        ergebnis.ico_bilder = _ico_bilder(bild)
    return ergebnis


def _xmp_lesen(bild: Image.Image) -> bytes | None:
    xmp = bild.info.get("xmp") or bild.info.get("XML:com.adobe.xmp")
    if isinstance(xmp, str):
        xmp = xmp.encode("utf-8")
    return xmp or None


def _xmp_ohne_ausrichtung(xmp: bytes) -> bytes:
    xmp = re.sub(rb'tiff:Orientation="[0-9]"', b'tiff:Orientation="1"', xmp)
    return re.sub(rb"<tiff:Orientation>[0-9]</tiff:Orientation>", b"", xmp)


def _ico_bilder(bild: Image.Image) -> list[Image.Image]:
    ico = getattr(bild, "ico", None)
    if ico is None:
        return []
    bilder = []
    for groesse in sorted(bild.info.get("sizes", ())):
        try:
            bilder.append(ico.getimage(groesse).convert("RGBA"))
        except (OSError, ValueError):
            continue
    return bilder


# --- Für das Ziel vorbereiten -------------------------------------------------


def auf_hintergrund(bild: Image.Image, farbe: tuple[int, int, int]) -> Image.Image:
    rgba = bild.convert("RGBA")
    flach = Image.new("RGB", rgba.size, farbe)
    flach.paste(rgba, mask=rgba.getchannel("A"))
    return flach


def _farbprofil_anwenden(
    bild: Image.Image, icc: bytes | None, ziel: Format
) -> tuple[Image.Image, bytes | None]:
    """Behält das ICC-Profil, wenn das Ziel es speichern kann, sonst wird nach sRGB umgerechnet."""
    if not icc:
        return bild, None
    farbraum = _icc_farbraum(icc)
    passend = (farbraum == b"RGB " and bild.mode in ("RGB", "RGBA", "P")) or (
        farbraum == b"GRAY" and bild.mode in ("L", "LA")
    )
    if farbraum == b"CMYK" and bild.mode == "CMYK":
        passend = True
    if ziel.icc:
        return bild, (icc if passend else None)
    if farbraum == b"RGB " and bild.mode in ("RGB", "RGBA"):
        try:
            quelle = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            bild = ImageCms.profileToProfile(bild, quelle, _SRGB, outputMode=bild.mode)
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass
    return bild, None


def _cmyk_nach_rgb(bild: Image.Image, icc: bytes | None) -> tuple[Image.Image, bytes | None]:
    if icc and _icc_farbraum(icc) == b"CMYK":
        try:
            quelle = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            return ImageCms.profileToProfile(bild, quelle, _SRGB, outputMode="RGB"), None
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass
    return bild.convert("RGB"), None


def vorbereiten(
    bild: Image.Image,
    ziel: Format,
    *,
    hintergrund: tuple[int, int, int] = STANDARD_HINTERGRUND,
    icc: bytes | None = None,
) -> tuple[Image.Image, bytes | None]:
    """Bringt ein Einzelbild in einen Modus, den das Zielformat speichern kann.

    Transparenz wird bei Zielen ohne Alpha auf ``hintergrund`` gelegt. Gibt das Bild und das
    passende ICC-Profil (oder ``None``) zurück.
    """
    transparent = _hat_transparenz(bild)
    palette_ok = not (bild.mode == "P" and transparent and ziel.name not in _PALETTE_TRANSPARENZ)
    if bild.mode in ziel.modi and palette_ok and not (transparent and not ziel.alpha):
        return _farbprofil_anwenden(bild, icc, ziel)

    grau = bild.mode in _GRAU_MODI
    if bild.mode in ("I", "I;16", "I;16B", "I;16L", "I;16N", "F"):
        bild = _auf_8bit(bild)
    elif bild.mode == "CMYK":
        bild, icc = _cmyk_nach_rgb(bild, icc)

    if transparent:
        if ziel.alpha:
            modus = "LA" if grau and "LA" in ziel.modi else "RGBA"
            bild = bild.convert(modus)
        else:
            bild = auf_hintergrund(bild, hintergrund)
    elif bild.mode not in ziel.modi:
        bild = bild.convert("L" if grau and "L" in ziel.modi else "RGB")

    if bild.mode not in ziel.modi:
        bild = bild.convert("RGBA" if "RGBA" in ziel.modi else ziel.modi[0])
    return _farbprofil_anwenden(bild, icc, ziel)


def _quadratisch(bild: Image.Image) -> Image.Image:
    breite, hoehe = bild.size
    if breite == hoehe:
        return bild
    seite = max(breite, hoehe)
    leinwand = Image.new("RGBA", (seite, seite), (0, 0, 0, 0))
    leinwand.paste(bild, ((seite - breite) // 2, (seite - hoehe) // 2))
    return leinwand


# --- Speichern ----------------------------------------------------------------


def speicher_optionen(
    ziel: Format,
    bild: Bild,
    frame: Image.Image,
    *,
    qualitaet: int | None = None,
    ico_bilder: list[Image.Image] | None = None,
) -> dict:
    optionen: dict = {}
    if ziel.name == "jpeg":
        optionen.update(quality=qualitaet or 92, optimize=True)
        if qualitaet is None or qualitaet >= 90:
            optionen["subsampling"] = "4:4:4"
    elif ziel.name == "webp":
        if qualitaet is None and bild.verlustfrei:
            optionen.update(lossless=True, quality=100, method=4)
        else:
            optionen.update(quality=qualitaet or 90, method=4)
    elif ziel.name == "avif":
        optionen["quality"] = qualitaet or 85
    elif ziel.name == "heif":
        optionen["quality"] = qualitaet or 90
    elif ziel.name == "tiff":
        optionen["compression"] = "tiff_adobe_deflate"
    elif ziel.name == "pdf":
        optionen.update(quality=qualitaet or 95, resolution=72.0)
    elif ziel.name == "ico":
        groesste = max(frame.size)
        groessen = [(g, g) for g in ICO_GROESSEN if g <= groesste] or [(groesste, groesste)]
        if ico_bilder:
            groessen = [b.size for b in ico_bilder]
            optionen["append_images"] = ico_bilder
        optionen["sizes"] = groessen
    return optionen


def _hat_exif_unterbereiche(exif_daten: bytes | None) -> bool:
    if not exif_daten:
        return False
    exif = Image.Exif()
    exif.load(exif_daten)
    return 0x8769 in exif or 0x8825 in exif


def _datei_schreiben(ziel_pfad: Path, schreiben, overwrite: bool) -> None:
    """Schreibt erst in eine temporäre Datei und benennt sie dann um.

    So bleibt bei einem Fehler nie eine halb geschriebene Zieldatei zurück, und ohne
    ``overwrite`` wird eine inzwischen entstandene Zieldatei nicht ersetzt.
    """
    ordner = ziel_pfad.parent
    griff, temp_name = tempfile.mkstemp(prefix=f".{ziel_pfad.name}.", suffix=".tmp", dir=ordner)
    temp = Path(temp_name)
    try:
        with os.fdopen(griff, "w+b") as datei:
            schreiben(datei)
        if overwrite:
            os.replace(temp, ziel_pfad)
        elif sys.platform == "win32":
            os.rename(temp, ziel_pfad)  # schlägt fehl, wenn das Ziel existiert
        else:
            try:
                os.link(temp, ziel_pfad)  # schlägt fehl, wenn das Ziel existiert
            except FileExistsError:
                raise
            except OSError:  # Dateisystem ohne harte Links
                if ziel_pfad.exists():
                    raise FileExistsError(ziel_pfad) from None
                os.replace(temp, ziel_pfad)
    except FileExistsError as fehler:
        raise _ziel_vorhanden(ziel_pfad) from fehler
    finally:
        temp.unlink(missing_ok=True)


def _ziel_vorhanden(ziel_pfad: Path) -> MiksanFehler:
    return MiksanFehler(
        f"'{ziel_pfad}' gibt es schon und bleibt unverändert. "
        "Mit --overwrite wird die Datei ersetzt."
    )


def speichern(
    bild: Bild,
    ziel_pfad: Path,
    ziel: Format,
    *,
    overwrite: bool = False,
    hintergrund: tuple[int, int, int] = STANDARD_HINTERGRUND,
    qualitaet: int | None = None,
    metadaten: bool = True,
) -> None:
    """Speichert ``bild`` sicher als ``ziel`` nach ``ziel_pfad``."""
    frames = []
    icc = None
    for index, frame in enumerate(bild.frames):
        vorbereitet, frame_icc = vorbereiten(frame, ziel, hintergrund=hintergrund, icc=bild.icc)
        if index == 0:
            icc = frame_icc
        frames.append(vorbereitet)
    if len(frames) > 1 and len({f.mode for f in frames}) > 1:
        # Einheitlicher Modus für alle Einzelbilder; ältere Pillow-Versionen scheitern sonst
        # z. B. bei APNG mit gemischten Paletten- und RGB-Bildern.
        modus = "RGBA" if any(_hat_transparenz(f) for f in frames) else "RGB"
        if modus not in ziel.modi:
            modus = ziel.modi[-1]
        frames = [f.convert(modus) for f in frames]

    ico_bilder = None
    if ziel.name == "ico":
        frames = [_quadratisch(f) for f in frames]
        ico_bilder = [_quadratisch(b) for b in bild.ico_bilder]

    erstes = frames[0]
    optionen = speicher_optionen(ziel, bild, erstes, qualitaet=qualitaet, ico_bilder=ico_bilder)
    if icc and ziel.icc:
        optionen["icc_profile"] = icc
    if metadaten and ziel.exif and bild.exif:
        optionen["exif"] = bild.exif
    if metadaten and ziel.exif and bild.xmp:
        optionen["xmp"] = bild.xmp
    if ziel.name == "tiff" and "exif" in optionen and _hat_exif_unterbereiche(bild.exif):
        # libtiff kann EXIF-Unterbereiche (Aufnahmedaten, GPS) nicht schreiben; unkomprimiert
        # schreibt Pillow selbst und behält sie.
        optionen.pop("compression", None)

    if len(frames) > 1:
        optionen.update(save_all=True, append_images=frames[1:])
        if ziel.animation:
            optionen.update(duration=bild.dauern[: len(frames)], loop=bild.loop)
            if ziel.name == "gif" and any(_hat_transparenz(f) for f in frames):
                optionen["disposal"] = 2

    def schreiben(datei):
        erstes.save(datei, format=ziel.pil_name, **optionen)

    try:
        _datei_schreiben(ziel_pfad, schreiben, overwrite)
    except MiksanFehler:
        raise
    except (OSError, ValueError, TypeError, KeyError) as fehler:
        raise MiksanFehler(f"'{ziel_pfad}' konnte nicht geschrieben werden: {fehler}") from fehler


# --- Umwandeln ----------------------------------------------------------------


def ziel_pruefen(eingabe: Path, ziel_pfad: Path, overwrite: bool) -> None:
    if ziel_pfad.exists() and ziel_pfad.resolve() == eingabe.resolve():
        raise BedienFehler(
            f"Ausgabe und Eingabe sind dieselbe Datei ({ziel_pfad}). "
            "Originaldateien werden nie verändert."
        )
    if ziel_pfad.exists() and not overwrite:
        raise _ziel_vorhanden(ziel_pfad)
    if not ziel_pfad.parent.is_dir():
        raise MiksanFehler(f"Der Ordner '{ziel_pfad.parent}' existiert nicht.")


def hinweise_zum_laden(eingabe: Path, bild: Bild, seite: int | None) -> list[str]:
    if seite is None and len(bild.frames) < bild.seiten_gesamt and bild.quelle != "ico":
        return [
            f"'{eingabe}' enthält {bild.seiten_gesamt} Seiten/Einzelbilder; übernommen "
            "wird nur das erste. Mit --page N lässt sich ein anderes wählen."
        ]
    return []


def umwandeln(
    eingabe: Path,
    ausgabe: Path | None = None,
    *,
    to: str | None = None,
    overwrite: bool = False,
    hintergrund: tuple[int, int, int] | str = STANDARD_HINTERGRUND,
    seite: int | None = None,
) -> Ergebnis:
    """Wandelt ``eingabe`` in das Zielformat um und schreibt eine neue Datei."""
    eingabe = Path(eingabe)
    if isinstance(hintergrund, str):
        hintergrund = farbe_parsen(hintergrund)
    ziel_pfad, ziel_format = ziel_bestimmen(eingabe, Path(ausgabe) if ausgabe else None, to)
    ziel_pruefen(eingabe, ziel_pfad, overwrite)

    bild = laden(eingabe, seite=seite, ziel=ziel_format)
    speichern(bild, ziel_pfad, ziel_format, overwrite=overwrite, hintergrund=hintergrund)
    return Ergebnis(
        eingabe, ziel_pfad, bild.quelle, ziel_format, hinweise_zum_laden(eingabe, bild, seite)
    )


__all__ = [
    "Bild",
    "Ergebnis",
    "farbe_parsen",
    "laden",
    "speichern",
    "umwandeln",
    "vorbereiten",
]

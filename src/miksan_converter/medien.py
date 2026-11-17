"""Video und Audio mit ffmpeg (eigenes, getrennt gestartetes Programm).

ffmpeg wird gesucht in dieser Reihenfolge: Pfad aus den Einstellungen (bzw. Umgebungsvariable
``MIKSAN_FFMPEG``), ``ffmpeg`` im PATH, mitgeliefertes ffmpeg aus dem Extra ``[medien]``
(Paket ``imageio-ffmpeg``). Es wird nur per ``subprocess`` aufgerufen, nicht eingebunden.

Die ``*_befehl``-Funktionen bauen nur Argumentlisten (ohne Programm und Ein-/Ausgabe) und
sind ohne ffmpeg testbar. ``ausfuehren`` startet ffmpeg, liest den Fortschritt aus
``-progress`` und schreibt erst in eine Zwischendatei; bei Abbruch oder Fehler bleibt nichts
Halbfertiges liegen.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .fehler import BedienFehler, ExtraFehlt, MiksanFehler

VIDEO_ZIELE = ("mp4", "webm", "mkv", "mov", "gif")
AUDIO_ZIELE = ("mp3", "wav", "flac", "ogg", "opus", "m4a")
QUALITAETEN = ("klein", "ausgewogen", "hoch")
STANDARD_QUALITAET = "ausgewogen"
AUFLOESUNGEN = (1080, 720, 480)

_CRF_X264 = {"klein": 28, "ausgewogen": 23, "hoch": 18}
_CRF_VP9 = {"klein": 38, "ausgewogen": 32, "hoch": 26}
_AAC = {"klein": "96k", "ausgewogen": "160k", "hoch": "256k"}
_OPUS = {"klein": "64k", "ausgewogen": "128k", "hoch": "192k"}
_MP3_Q = {"klein": "6", "ausgewogen": "4", "hoch": "0"}  # VBR, 0 = beste
_VORBIS_Q = {"klein": "3", "ausgewogen": "5", "hoch": "8"}
_LAUTHEIT = "loudnorm=I=-16:TP=-1.5:LRA=11"

_eigener_pfad: str | None = None


# --- ffmpeg finden ---------------------------------------------------------------------------


def pfad_setzen(pfad: str | None) -> None:
    """Pfad aus den Einstellungen der Oberfläche (leer = automatisch suchen)."""
    global _eigener_pfad
    _eigener_pfad = pfad.strip() if pfad and pfad.strip() else None


def ffmpeg_finden() -> Path | None:
    for kandidat in (_eigener_pfad, os.environ.get("MIKSAN_FFMPEG")):
        if kandidat and Path(kandidat).is_file():
            return Path(kandidat)
    gefunden = shutil.which("ffmpeg")
    if gefunden:
        return Path(gefunden)
    try:
        import imageio_ffmpeg

        return Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:  # Extra fehlt oder Paket ohne passendes Programm
        return None


def ffmpeg_vorhanden() -> bool:
    """Schnelle Prüfung für die Seitenleiste: lädt ``imageio_ffmpeg`` noch nicht."""
    import importlib.util

    for kandidat in (_eigener_pfad, os.environ.get("MIKSAN_FFMPEG")):
        if kandidat and Path(kandidat).is_file():
            return True
    if shutil.which("ffmpeg"):
        return True
    try:
        return importlib.util.find_spec("imageio_ffmpeg") is not None
    except (ImportError, ValueError):  # z. B. Eintrag in sys.modules ist None
        return False


def ffmpeg() -> Path:
    pfad = ffmpeg_finden()
    if pfad is None:
        raise ExtraFehlt("medien", "Video und Audio (ffmpeg)")
    return pfad


def _startoptionen() -> dict:
    """Unter Windows kein schwarzes Konsolenfenster für ffmpeg öffnen."""
    if sys.platform == "win32":
        return {"creationflags": subprocess.CREATE_NO_WINDOW}
    return {}


def version() -> str:
    ergebnis = subprocess.run(
        [str(ffmpeg()), "-hide_banner", "-version"],
        capture_output=True,
        text=True,
        errors="replace",
        **_startoptionen(),
    )
    return ergebnis.stdout.splitlines()[0] if ergebnis.stdout else ""


# --- Zeiten ----------------------------------------------------------------------------------


def zeit_parsen(text: str | float | None) -> float | None:
    """Liest ``83``, ``83.5``, ``1:23`` oder ``0:01:23.5`` als Sekunden."""
    if text is None or (isinstance(text, str) and not text.strip()):
        return None
    if isinstance(text, int | float):
        sekunden = float(text)
    else:
        teile = text.strip().replace(",", ".").split(":")
        if len(teile) > 3 or not all(re.fullmatch(r"\d+(\.\d+)?", t) for t in teile):
            raise BedienFehler(f"Zeit '{text}' ist ungültig, z. B. 1:23 oder 83.5")
        sekunden = 0.0
        for teil in teile:
            sekunden = sekunden * 60 + float(teil)
    if sekunden < 0:
        raise BedienFehler("Zeiten dürfen nicht negativ sein.")
    return sekunden


def zeit_text(sekunden: float | None) -> str:
    if sekunden is None:
        return ""
    minuten, rest = divmod(round(sekunden), 60)
    stunden, minuten = divmod(minuten, 60)
    return f"{stunden}:{minuten:02d}:{rest:02d}" if stunden else f"{minuten}:{rest:02d}"


# --- Untersuchen -----------------------------------------------------------------------------


@dataclass
class MedienInfo:
    dauer: float | None = None
    breite: int | None = None
    hoehe: int | None = None
    fps: float | None = None
    video: str | None = None  # Codec
    audio: str | None = None
    cover: bool = False  # Titelbild (attached pic) in Tondateien
    metadaten: dict[str, str] = field(default_factory=dict)

    @property
    def hat_video(self) -> bool:
        return self.video is not None and not self.cover


def untersuchen(pfad: str | Path) -> MedienInfo:
    """Liest Dauer, Auflösung, Bildrate und Codecs aus der Ausgabe von ``ffmpeg -i``."""
    pfad = Path(pfad)
    if not pfad.is_file():
        raise MiksanFehler(f"Datei nicht gefunden: {pfad}")
    ergebnis = subprocess.run(
        [str(ffmpeg()), "-hide_banner", "-i", str(pfad)],
        capture_output=True,
        text=True,
        errors="replace",
        **_startoptionen(),
    )
    text = ergebnis.stderr
    if "Invalid data found" in text or "Stream #" not in text:
        raise MiksanFehler(f"'{pfad}' ist keine lesbare Video- oder Tondatei.")
    info = MedienInfo()
    treffer = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if treffer:
        h, m, s = treffer.groups()
        info.dauer = int(h) * 3600 + int(m) * 60 + float(s)
    for zeile in text.splitlines():
        stream = re.search(r"Stream #\S+.*?: (Video|Audio): (\w+)", zeile)
        if stream is None:
            meta = re.match(r"\s{4}(title|artist|album)\s*: (.*)", zeile)
            if meta and meta.group(1) not in info.metadaten:
                info.metadaten[meta.group(1)] = meta.group(2).strip()
            continue
        art, codec = stream.groups()
        if art == "Video" and info.video is None:
            info.video = codec
            info.cover = "attached pic" in zeile
            masse = re.search(r", (\d{2,5})x(\d{2,5})", zeile)
            if masse:
                info.breite, info.hoehe = int(masse.group(1)), int(masse.group(2))
            fps = re.search(r"(\d+(?:\.\d+)?) fps", zeile)
            if fps:
                info.fps = float(fps.group(1))
        elif art == "Audio" and info.audio is None:
            info.audio = codec
    return info


# --- Befehle bauen (ohne ffmpeg testbar) ------------------------------------------------------


def _zeitbereich(start: float | None, ende: float | None) -> list[str]:
    if start is not None and ende is not None and ende <= start:
        raise BedienFehler("Das Ende muss nach dem Start liegen.")
    argumente = []
    if start:
        argumente += ["-ss", f"{start:.3f}"]
    if ende is not None:
        argumente += ["-to", f"{ende:.3f}"]
    return argumente


def _skalieren(aufloesung: int | None) -> list[str]:
    if aufloesung is None:
        return []
    if aufloesung not in AUFLOESUNGEN:
        raise BedienFehler(f"Auflösung {aufloesung}p gibt es nicht: 1080, 720 oder 480.")
    # nur verkleinern, Breite gerade halten
    return ["-vf", f"scale=-2:'min(ih,{aufloesung})'"]


def _qualitaet(qualitaet: str) -> str:
    if qualitaet not in QUALITAETEN:
        raise BedienFehler(f"Qualität '{qualitaet}' gibt es nicht: klein, ausgewogen oder hoch.")
    return qualitaet


def video_befehl(
    ziel: str = "mp4",
    *,
    qualitaet: str = STANDARD_QUALITAET,
    crf: int | None = None,
    aufloesung: int | None = None,
    fps: float | None = None,
    ohne_ton: bool = False,
) -> list[str]:
    """Kodier-Optionen für ein Video (ohne Ein-/Ausgabe)."""
    qualitaet = _qualitaet(qualitaet)
    if ziel == "gif":
        return gif_befehl()
    if ziel not in VIDEO_ZIELE:
        raise BedienFehler(f"Videoformat '{ziel}' gibt es nicht. Möglich: {', '.join(VIDEO_ZIELE)}")
    if crf is not None and not 0 <= crf <= 63:
        raise BedienFehler("CRF muss zwischen 0 und 63 liegen.")
    argumente = ["-map", "0:v:0", "-map", "0:a?"] if not ohne_ton else ["-map", "0:v:0"]
    if ziel == "webm":
        argumente += [
            "-c:v",
            "libvpx-vp9",
            "-crf",
            str(crf if crf is not None else _CRF_VP9[qualitaet]),
        ]
        argumente += ["-b:v", "0", "-row-mt", "1", "-deadline", "good", "-cpu-used", "4"]
        ton = ["-c:a", "libopus", "-b:a", _OPUS[qualitaet]]
    else:
        argumente += ["-c:v", "libx264", "-preset", "medium"]
        argumente += ["-crf", str(crf if crf is not None else _CRF_X264[qualitaet])]
        argumente += ["-pix_fmt", "yuv420p"]
        ton = ["-c:a", "aac", "-b:a", _AAC[qualitaet]]
        if ziel in ("mp4", "mov"):
            argumente += ["-movflags", "+faststart"]
    argumente += _skalieren(aufloesung)
    if fps is not None:
        if not 1 <= fps <= 240:
            raise BedienFehler("Die Bildrate muss zwischen 1 und 240 liegen.")
        argumente += ["-r", f"{fps:g}"]
    argumente += ["-an"] if ohne_ton else ton
    return argumente


def gif_befehl(breite: int = 480, fps: float = 12) -> list[str]:
    """Video → GIF mit eigener Farbpalette (deutlich schöner als die Standardpalette)."""
    if not 16 <= breite <= 1920 or not 1 <= fps <= 50:
        raise BedienFehler("GIF: Breite 16–1920 Pixel, Bildrate 1–50.")
    filter_ = (
        f"fps={fps:g},scale={breite}:-1:flags=lanczos,split[a][b];"
        "[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4"
    )
    return ["-filter_complex", filter_, "-loop", "0"]


def audio_befehl(
    ziel: str = "mp3",
    *,
    qualitaet: str = STANDARD_QUALITAET,
    bitrate: str | None = None,
    normalisieren: bool = False,
    cover: bool = False,
) -> list[str]:
    """Kodier-Optionen für Ton. Titel/Interpret bleiben, das Cover bei MP3, M4A und FLAC."""
    qualitaet = _qualitaet(qualitaet)
    if ziel not in AUDIO_ZIELE:
        raise BedienFehler(f"Tonformat '{ziel}' gibt es nicht. Möglich: {', '.join(AUDIO_ZIELE)}")
    if bitrate is not None and not re.fullmatch(r"\d{2,3}k", bitrate):
        raise BedienFehler(f"Bitrate '{bitrate}' ist ungültig, z. B. 192k.")
    mit_cover = cover and ziel in ("mp3", "m4a", "flac")
    argumente = ["-map", "0:a:0"] + (["-map", "0:v:0", "-c:v", "copy"] if mit_cover else ["-vn"])
    argumente += ["-map_metadata", "0"]
    codec = {
        "mp3": ["-c:a", "libmp3lame"]
        + (["-b:a", bitrate] if bitrate else ["-q:a", _MP3_Q[qualitaet]]),
        "wav": ["-c:a", "pcm_s16le"],
        "flac": ["-c:a", "flac"],
        "ogg": ["-c:a", "libvorbis"]
        + (["-b:a", bitrate] if bitrate else ["-q:a", _VORBIS_Q[qualitaet]]),
        "opus": ["-c:a", "libopus", "-b:a", bitrate or _OPUS[qualitaet]],
        "m4a": ["-c:a", "aac", "-b:a", bitrate or _AAC[qualitaet]],
    }[ziel]
    argumente += codec
    if mit_cover:
        argumente += ["-disposition:v:0", "attached_pic"]
    if ziel == "mp3":
        argumente += ["-id3v2_version", "3"]
    if normalisieren:
        argumente += ["-af", _LAUTHEIT]
    return argumente


def einzelbild_befehl() -> list[str]:
    return ["-frames:v", "1", "-update", "1"]


def zielgroesse_bitraten(ziel_byte: int, dauer: float, mit_ton: bool) -> tuple[int, int]:
    """(Video-, Audio-Bitrate in kbit/s), damit die Datei höchstens ``ziel_byte`` gross wird.

    5 % Reserve für Container und Schwankungen.
    """
    if dauer <= 0:
        raise MiksanFehler("Die Dauer des Videos ist unbekannt.")
    gesamt = ziel_byte * 8 * 0.95 / dauer / 1000
    audio = 0
    if mit_ton:
        audio = 128 if gesamt > 1500 else 96 if gesamt > 600 else 64 if gesamt > 200 else 32
    video = int(gesamt - audio)
    if video < 30:
        raise MiksanFehler(
            f"Die Zielgrösse ist für {zeit_text(dauer)} Video zu klein "
            f"(mindestens etwa {(30 + audio) * dauer * 1000 / 8 / 0.95 / 1e6:.1f} MB)."
        )
    return video, audio


# --- Ausführen -------------------------------------------------------------------------------

Fortschritt = Callable[[float], None]  # Anteil 0..1


def _zwischendatei(ziel: Path) -> Path:
    return ziel.with_name(f".{ziel.stem}.miksan-teil{ziel.suffix}")


def ausfuehren(
    eingabe: Path,
    ausgabe: Path,
    argumente: list[str],
    *,
    vor_eingabe: list[str] | None = None,
    dauer: float | None = None,
    fortschritt: Fortschritt | None = None,
    abbrechen: threading.Event | None = None,
    overwrite: bool = False,
    format: str | None = None,
) -> Path:
    """Startet ffmpeg; schreibt erst in eine Zwischendatei und benennt sie am Ende um."""
    eingabe, ausgabe = Path(eingabe), Path(ausgabe)
    if ausgabe.exists() and not overwrite:
        raise MiksanFehler(
            f"'{ausgabe}' gibt es schon und bleibt unverändert. Mit --overwrite wird sie ersetzt."
        )
    if ausgabe.resolve() == eingabe.resolve():
        raise BedienFehler("Ausgabe und Eingabe sind dieselbe Datei.")
    ausgabe.parent.mkdir(parents=True, exist_ok=True)
    teil = _zwischendatei(ausgabe)
    befehl = [str(ffmpeg()), "-hide_banner", "-nostdin", "-y", "-loglevel", "error"]
    befehl += ["-progress", "pipe:1", "-nostats"]
    befehl += (vor_eingabe or []) + ["-i", str(eingabe)] + argumente
    if format:
        befehl += ["-f", format]
    befehl.append(str(teil))
    fehlerzeilen: deque[str] = deque(maxlen=20)
    prozess = subprocess.Popen(
        befehl,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        **_startoptionen(),
    )

    def fehler_lesen() -> None:
        for zeile in prozess.stderr:
            if zeile.strip():
                fehlerzeilen.append(zeile.strip())

    leser = threading.Thread(target=fehler_lesen, daemon=True)
    leser.start()
    abgebrochen = False

    def beobachten() -> None:
        nonlocal abgebrochen
        while prozess.poll() is None:
            if abbrechen is not None and abbrechen.wait(0.1):
                abgebrochen = True
                prozess.kill()
                return

    waechter = threading.Thread(target=beobachten, daemon=True)
    waechter.start()
    try:
        for zeile in prozess.stdout:
            if fortschritt is not None and dauer and zeile.startswith("out_time_us="):
                wert = zeile.split("=", 1)[1].strip()
                if wert.isdigit():
                    fortschritt(min(1.0, int(wert) / 1e6 / dauer))
        prozess.wait()
        waechter.join(1)
        leser.join(1)
    except BaseException:
        prozess.kill()
        prozess.wait()
        teil.unlink(missing_ok=True)
        raise
    if abgebrochen or (abbrechen is not None and abbrechen.is_set()):
        teil.unlink(missing_ok=True)
        raise MiksanFehler("Abgebrochen.")
    if prozess.returncode != 0 or not teil.is_file():
        teil.unlink(missing_ok=True)
        grund = fehlerzeilen[-1] if fehlerzeilen else f"Rückgabecode {prozess.returncode}"
        raise MiksanFehler(f"ffmpeg konnte '{eingabe.name}' nicht verarbeiten: {grund}")
    teil.replace(ausgabe)
    if fortschritt is not None:
        fortschritt(1.0)
    return ausgabe


# --- Aufgaben --------------------------------------------------------------------------------


def standard_ziel(eingabe: Path, endung: str, zusatz: str = "") -> Path:
    name = f"{eingabe.stem}{'-' + zusatz if zusatz else ''}.{endung}"
    ziel = eingabe.with_name(name)
    if ziel == eingabe:
        ziel = eingabe.with_name(f"{eingabe.stem}-neu.{endung}")
    return ziel


def _endung(ausgabe: Path | None, standard: str, erlaubt) -> str:
    if ausgabe is not None and ausgabe.suffix:
        endung = ausgabe.suffix.lower().lstrip(".")
        endung = {"jpeg": "jpg", "oga": "ogg", "aac": "m4a"}.get(endung, endung)
        if endung not in erlaubt:
            raise BedienFehler(f"Die Endung .{endung} passt nicht. Möglich: {', '.join(erlaubt)}")
        return endung
    return standard


def video_umwandeln(
    eingabe: str | Path,
    ausgabe: str | Path | None = None,
    *,
    ziel: str | None = None,
    start: float | None = None,
    ende: float | None = None,
    **optionen,
) -> Path:
    eingabe = Path(eingabe)
    ausgabe = Path(ausgabe) if ausgabe else None
    endung = ziel or _endung(ausgabe, "mp4", VIDEO_ZIELE)
    steuerung = {
        k: optionen.pop(k) for k in ("fortschritt", "abbrechen", "overwrite") if k in optionen
    }
    info = untersuchen(eingabe)
    if not info.hat_video:
        raise MiksanFehler(f"'{eingabe.name}' enthält kein Video.")
    argumente = video_befehl(endung, **optionen)
    dauer = _teildauer(info.dauer, start, ende)
    return ausfuehren(
        eingabe,
        ausgabe or standard_ziel(eingabe, endung),
        _zeitbereich(start, ende) + argumente,
        dauer=dauer,
        **steuerung,
    )


def _teildauer(dauer: float | None, start: float | None, ende: float | None) -> float | None:
    if dauer is None:
        return None
    return max(0.1, (ende if ende is not None else dauer) - (start or 0))


def kuerzen(
    eingabe: str | Path,
    ausgabe: str | Path | None = None,
    *,
    start: float | None = None,
    ende: float | None = None,
    neu_kodieren: bool = False,
    **steuerung,
) -> Path:
    """Schneidet einen Teil heraus – ohne Neukodierung (schnell, an Schlüsselbildern) oder
    genau (neu kodiert)."""
    eingabe = Path(eingabe)
    if start is None and ende is None:
        raise BedienFehler("Bitte Start und/oder Ende angeben.")
    info = untersuchen(eingabe)
    if info.dauer is not None and start is not None and start >= info.dauer:
        raise BedienFehler(f"Der Start liegt hinter dem Ende ({zeit_text(info.dauer)}).")
    endung = eingabe.suffix.lower().lstrip(".") or "mp4"
    ziel = Path(ausgabe) if ausgabe else standard_ziel(eingabe, endung, "gekuerzt")
    if neu_kodieren:
        if info.hat_video:
            argumente = video_befehl("webm" if endung == "webm" else "mp4")
        else:
            argumente = audio_befehl(endung if endung in AUDIO_ZIELE else "m4a", cover=info.cover)
    else:
        argumente = ["-map", "0", "-c", "copy", "-avoid_negative_ts", "make_zero"]
    return ausfuehren(
        eingabe,
        ziel,
        _zeitbereich(start, ende) + argumente,
        dauer=_teildauer(info.dauer, start, ende),
        **steuerung,
    )


def verkleinern(
    eingabe: str | Path,
    ausgabe: str | Path | None = None,
    *,
    ziel_byte: int,
    aufloesung: int | None = None,
    fortschritt: Fortschritt | None = None,
    abbrechen: threading.Event | None = None,
    overwrite: bool = False,
) -> Path:
    """Video auf eine Zielgrösse bringen (z. B. unter 10 MB für Discord oder Mail).

    Die Bitrate wird aus der Dauer berechnet (zwei Durchgänge mit x264). Ist das Ergebnis
    trotzdem zu gross, wird mit kleinerer Bitrate wiederholt.
    """
    eingabe = Path(eingabe)
    info = untersuchen(eingabe)
    if not info.hat_video or not info.dauer:
        raise MiksanFehler(f"'{eingabe.name}' enthält kein Video mit bekannter Dauer.")
    ziel = Path(ausgabe) if ausgabe else standard_ziel(eingabe, "mp4", "klein")
    if ziel.exists() and not overwrite:
        raise MiksanFehler(f"'{ziel}' gibt es schon und bleibt unverändert.")
    video_kbit, audio_kbit = zielgroesse_bitraten(ziel_byte, info.dauer, info.audio is not None)
    with tempfile.TemporaryDirectory(prefix="miksan-") as ordner:
        log = str(Path(ordner) / "pass")
        for versuch in range(3):
            basis = ["-map", "0:v:0", "-c:v", "libx264", "-preset", "medium"]
            basis += ["-b:v", f"{video_kbit}k", "-pix_fmt", "yuv420p", "-passlogfile", log]
            basis += _skalieren(aufloesung)

            def teil(anteil: float, stufe: int) -> None:
                if fortschritt is not None:
                    fortschritt((stufe + anteil) / 2)

            leer = Path(ordner) / "leer.mp4"
            ausfuehren(
                eingabe,
                leer,
                basis + ["-pass", "1", "-an"],
                dauer=info.dauer,
                fortschritt=lambda a: teil(a, 0),
                abbrechen=abbrechen,
                overwrite=True,
                format="mp4",
            )
            ton = (
                ["-map", "0:a:0?", "-c:a", "aac", "-b:a", f"{audio_kbit}k"]
                if audio_kbit
                else ["-an"]
            )
            ausfuehren(
                eingabe,
                ziel,
                basis + ["-pass", "2", "-movflags", "+faststart"] + ton,
                dauer=info.dauer,
                fortschritt=lambda a: teil(a, 1),
                abbrechen=abbrechen,
                overwrite=True if versuch or overwrite else False,
            )
            groesse = ziel.stat().st_size
            if groesse <= ziel_byte:
                return ziel
            video_kbit = max(20, int(video_kbit * ziel_byte / groesse * 0.95))
    ziel.unlink(missing_ok=True)
    raise MiksanFehler("Die Zielgrösse wurde nicht erreicht – bitte etwas grösser wählen.")


def zu_gif(
    eingabe: str | Path,
    ausgabe: str | Path | None = None,
    *,
    breite: int = 480,
    fps: float = 12,
    start: float | None = None,
    ende: float | None = None,
    **steuerung,
) -> Path:
    eingabe = Path(eingabe)
    info = untersuchen(eingabe)
    ziel = Path(ausgabe) if ausgabe else standard_ziel(eingabe, "gif")
    return ausfuehren(
        eingabe,
        ziel,
        _zeitbereich(start, ende) + gif_befehl(breite, fps),
        dauer=_teildauer(info.dauer, start, ende),
        **steuerung,
    )


def audio_umwandeln(
    eingabe: str | Path,
    ausgabe: str | Path | None = None,
    *,
    ziel: str | None = None,
    qualitaet: str = STANDARD_QUALITAET,
    bitrate: str | None = None,
    normalisieren: bool = False,
    start: float | None = None,
    ende: float | None = None,
    **steuerung,
) -> Path:
    """Ton umwandeln – auch den Ton aus einem Video herausziehen."""
    eingabe = Path(eingabe)
    ausgabe = Path(ausgabe) if ausgabe else None
    endung = ziel or _endung(ausgabe, "mp3", AUDIO_ZIELE)
    info = untersuchen(eingabe)
    if info.audio is None:
        raise MiksanFehler(f"'{eingabe.name}' enthält keinen Ton.")
    argumente = audio_befehl(
        endung,
        qualitaet=qualitaet,
        bitrate=bitrate,
        normalisieren=normalisieren,
        cover=info.cover,
    )
    return ausfuehren(
        eingabe,
        ausgabe or standard_ziel(eingabe, endung),
        _zeitbereich(start, ende) + argumente,
        dauer=_teildauer(info.dauer, start, ende),
        **steuerung,
    )


def einzelbild(
    eingabe: str | Path,
    ausgabe: str | Path | None = None,
    *,
    zeit: float = 0.0,
    overwrite: bool = False,
    abbrechen: threading.Event | None = None,
) -> Path:
    """Speichert das Bild an Zeitpunkt ``zeit`` (Sekunden) als PNG oder JPEG."""
    eingabe = Path(eingabe)
    ausgabe = Path(ausgabe) if ausgabe else None
    endung = _endung(ausgabe, "png", ("png", "jpg", "webp"))
    info = untersuchen(eingabe)
    if not info.hat_video:
        raise MiksanFehler(f"'{eingabe.name}' enthält kein Video.")
    if info.dauer is not None and zeit > info.dauer:
        raise BedienFehler(f"Zeitpunkt liegt hinter dem Ende ({zeit_text(info.dauer)}).")
    ziel = ausgabe or standard_ziel(eingabe, endung, f"bild-{zeit_text(zeit).replace(':', '-')}")
    return ausfuehren(
        eingabe,
        ziel,
        einzelbild_befehl(),
        vor_eingabe=["-ss", f"{zeit:.3f}"],
        overwrite=overwrite,
        abbrechen=abbrechen,
    )


def vorschaubild(eingabe: str | Path, kante: int = 192):
    """Erstes Bild eines Videos (bzw. Cover einer Tondatei) als PIL-Bild, sonst ``None``."""
    import io

    from PIL import Image

    programm = ffmpeg_finden()
    if programm is None:
        return None
    befehl = [str(programm), "-hide_banner", "-loglevel", "error", "-i", str(eingabe)]
    befehl += ["-map", "0:v:0", "-frames:v", "1", "-vf", f"scale='min({kante},iw)':-2"]
    befehl += ["-f", "image2pipe", "-c:v", "png", "pipe:1"]
    try:
        ergebnis = subprocess.run(befehl, capture_output=True, timeout=30, **_startoptionen())
        if ergebnis.returncode != 0 or not ergebnis.stdout:
            return None
        bild = Image.open(io.BytesIO(ergebnis.stdout))
        bild.load()
        return bild.convert("RGBA")
    except Exception:  # kein Video, Zeitüberschreitung …
        return None

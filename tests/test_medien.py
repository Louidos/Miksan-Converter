"""Video und Audio (ffmpeg). Befehlsbau ohne ffmpeg; echte Läufe mit 2-Sekunden-Clips, ohne
ffmpeg übersprungen (Fixture ``clips``)."""

import sys
import threading
from pathlib import Path

import pytest

from miksan_converter import medien
from miksan_converter.cli import main
from miksan_converter.fehler import BedienFehler, MiksanFehler

# --- ohne ffmpeg ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "sekunden"),
    [("83", 83), ("83.5", 83.5), ("1:23", 83), ("0:01:23.5", 83.5), ("1,5", 1.5), (None, None)],
)
def test_zeit_parsen(text, sekunden):
    assert medien.zeit_parsen(text) == sekunden


@pytest.mark.parametrize("text", ["a", "1:2:3:4", "-5"])
def test_zeit_ungueltig(text):
    with pytest.raises(BedienFehler):
        medien.zeit_parsen(text)


def test_video_befehle():
    mp4 = medien.video_befehl("mp4", qualitaet="hoch", aufloesung=720, fps=30)
    assert "libx264" in mp4 and "18" in mp4 and "+faststart" in mp4 and "aac" in mp4
    assert "scale=-2:'min(ih,720)'" in mp4 and "30" in mp4
    webm = medien.video_befehl("webm", crf=40, ohne_ton=True)
    assert "libvpx-vp9" in webm and "40" in webm and "-an" in webm and "libopus" not in webm
    assert "palettegen" in " ".join(medien.video_befehl("gif"))
    with pytest.raises(BedienFehler):
        medien.video_befehl("avi")
    with pytest.raises(BedienFehler):
        medien.video_befehl("mp4", qualitaet="riesig")
    with pytest.raises(BedienFehler):
        medien.video_befehl("mp4", aufloesung=999)


def test_audio_befehle():
    mp3 = medien.audio_befehl("mp3", cover=True, normalisieren=True)
    assert "libmp3lame" in mp3 and "attached_pic" in mp3 and "loudnorm" in " ".join(mp3)
    assert "-map_metadata" in mp3
    opus = medien.audio_befehl("opus", cover=True, bitrate="96k")
    assert "-vn" in opus and "96k" in opus  # Opus ohne Cover
    with pytest.raises(BedienFehler):
        medien.audio_befehl("mp3", bitrate="viel")


def test_zielgroesse_bitraten():
    video, audio = medien.zielgroesse_bitraten(10_000_000, 60, True)
    assert audio == 96 and (video + audio) * 60 * 1000 / 8 <= 10_000_000
    with pytest.raises(MiksanFehler, match="zu klein"):
        medien.zielgroesse_bitraten(10_000, 600, True)


def test_ohne_ffmpeg_klare_meldung(monkeypatch, tmp_path: Path, capsys):
    monkeypatch.setattr(medien, "ffmpeg_finden", lambda: None)
    (tmp_path / "a.mov").write_bytes(b"x")
    assert main(["video", "umwandeln", str(tmp_path / "a.mov")]) == 3
    assert "miksan-converter[medien]" in capsys.readouterr().err
    assert not medien.ffmpeg_vorhanden()


def test_ffmpeg_suche_reihenfolge(monkeypatch, tmp_path: Path):
    eigenes = tmp_path / "mein-ffmpeg"
    eigenes.write_bytes(b"")
    monkeypatch.setattr(medien.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    medien.pfad_setzen(str(eigenes))
    try:
        assert medien.ffmpeg_finden() == eigenes
    finally:
        medien.pfad_setzen(None)
    assert medien.ffmpeg_finden() == Path("/usr/bin/ffmpeg")
    monkeypatch.setattr(medien.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", None)
    assert medien.ffmpeg_finden() is None


# --- mit ffmpeg ----------------------------------------------------------------------------


def test_untersuchen(clips):
    info = medien.untersuchen(clips["clip_mov"])
    assert (info.breite, info.hoehe, info.audio) == (320, 240, "aac")
    assert info.dauer == pytest.approx(2.0, abs=0.1) and info.hat_video
    ton = medien.untersuchen(clips["ton_mp3"])
    assert ton.cover and not ton.hat_video and ton.metadaten["title"] == "Testlied"


@pytest.mark.parametrize("quelle", ["clip_mov", "clip_mkv"])
def test_mov_und_mkv_zu_mp4(quelle, clips, tmp_path: Path):
    ziel = tmp_path / f"{quelle}.mp4"
    assert main(["video", "umwandeln", str(clips[quelle]), "-o", str(ziel)]) == 0
    info = medien.untersuchen(ziel)
    assert info.video == "h264" and info.audio == "aac"
    assert info.dauer == pytest.approx(2.0, abs=0.15)


def test_video_zu_mp3_und_webm(clips, tmp_path: Path):
    assert main(["video", "ton", str(clips["clip_mov"]), "-o", str(tmp_path / "ton.mp3")]) == 0
    assert medien.untersuchen(tmp_path / "ton.mp3").audio == "mp3"
    schritte = []
    ziel = medien.video_umwandeln(
        clips["clip_mkv"],
        tmp_path / "klein.webm",
        qualitaet="klein",
        aufloesung=480,
        ohne_ton=True,
        fortschritt=schritte.append,
    )
    info = medien.untersuchen(ziel)
    assert info.video == "vp9" and info.audio is None
    assert schritte and schritte[-1] == 1.0


def test_audio_metadaten_und_cover_bleiben(clips, tmp_path: Path):
    for ziel in ("m4a", "flac"):
        pfad = medien.audio_umwandeln(clips["ton_mp3"], tmp_path / f"lied.{ziel}")
        info = medien.untersuchen(pfad)
        assert info.metadaten.get("title") == "Testlied" and info.cover, ziel
    pfad = medien.audio_umwandeln(clips["ton_wav"], tmp_path / "lied.opus", normalisieren=True)
    assert medien.untersuchen(pfad).audio == "opus"


def test_kuerzen_ohne_und_mit_neukodierung(clips, tmp_path: Path):
    ziel = tmp_path / "kurz.mkv"
    args = ["video", "kuerzen", str(clips["clip_mkv"]), "--start", "0.5", "--ende", "1.5"]
    assert main([*args, "-o", str(ziel)]) == 0
    assert medien.untersuchen(ziel).dauer < 1.8
    genau = medien.kuerzen(clips["clip_mov"], tmp_path / "genau.mov", ende=1, neu_kodieren=True)
    assert medien.untersuchen(genau).dauer == pytest.approx(1.0, abs=0.1)
    with pytest.raises(BedienFehler):
        medien.kuerzen(clips["clip_mov"], tmp_path / "x.mov")
    with pytest.raises(BedienFehler):
        medien.kuerzen(clips["clip_mov"], tmp_path / "x.mov", start=2, ende=1)


def test_verkleinern_auf_zielgroesse(clips, tmp_path: Path):
    ziel = tmp_path / "klein.mp4"
    assert main(["video", "verkleinern", str(clips["clip_mov"]), "--zielgroesse", "60KB",
                 "-o", str(ziel)]) == 0  # fmt: skip
    assert ziel.stat().st_size <= 60_000
    assert medien.untersuchen(ziel).video == "h264"


def test_gif_und_einzelbild(clips, tmp_path: Path):
    from PIL import Image

    gif = medien.zu_gif(clips["clip_mov"], tmp_path / "a.gif", breite=160, fps=5)
    with Image.open(gif) as bild:
        assert bild.size[0] == 160 and bild.n_frames >= 8
    assert main(["video", "bild", str(clips["clip_mov"]), "--zeit", "1",
                 "-o", str(tmp_path / "bild.jpg")]) == 0  # fmt: skip
    with Image.open(tmp_path / "bild.jpg") as bild:
        assert bild.size == (320, 240)
    vorschau = medien.vorschaubild(clips["clip_mkv"], 100)
    assert vorschau is not None and vorschau.width == 100
    assert medien.vorschaubild(clips["ton_wav"]) is None


def test_abbrechen_laesst_keine_datei_liegen(clips, tmp_path: Path):
    abbrechen = threading.Event()
    abbrechen.set()
    ziel = tmp_path / "abbruch.mp4"
    with pytest.raises(MiksanFehler, match="Abgebrochen"):
        medien.video_umwandeln(clips["clip_mov"], ziel, abbrechen=abbrechen)
    assert list(tmp_path.iterdir()) == []


def test_fehler_ohne_halbe_datei(tmp_path: Path, clips):
    kaputt = tmp_path / "kaputt.mp4"
    kaputt.write_bytes(b"kein video")
    with pytest.raises(MiksanFehler, match="keine lesbare"):
        medien.video_umwandeln(kaputt, tmp_path / "aus.mp4")
    with pytest.raises(MiksanFehler, match="kein Video"):
        medien.video_umwandeln(clips["ton_wav"], tmp_path / "aus.mp4")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["kaputt.mp4"]
    ziel = tmp_path / "doppelt.mp3"
    ziel.write_bytes(b"da")
    assert main(["audio", str(clips["ton_wav"]), "-o", str(ziel)]) == 1
    assert ziel.read_bytes() == b"da"

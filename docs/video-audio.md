# Video und Audio

Videos und Tondateien lokal umwandeln, kürzen und verkleinern – ohne Upload, ohne Werbe-Webseite.
Die Arbeit macht das Programm **ffmpeg**, das Miksan-Converter als eigenes Programm startet.

## ffmpeg

Miksan-Converter sucht ffmpeg in dieser Reihenfolge:

1. Pfad aus den **Einstellungen** der Oberfläche (Einstellungen → Video & Audio) bzw. die
   Umgebungsvariable `MIKSAN_FFMPEG` für die Kommandozeile,
2. `ffmpeg` im **PATH** (z. B. aus der Paketverwaltung),
3. das mitgelieferte ffmpeg aus dem Extra **`[medien]`** (Paket `imageio-ffmpeg`):

```bash
pip install "miksan-converter[medien]"
```

Im **Windows-Installer** ist ffmpeg enthalten. Fehlt ffmpeg ganz, meldet `miksan video …`
bzw. `miksan audio …` den Installationsbefehl (Rückgabecode 3) und in der Oberfläche ist der
Bereich „Video & Audio“ ausgegraut; der Rest der App läuft normal.

## Video – `miksan video`

```bash
miksan video umwandeln film.mov                          # -> film.mp4 (H.264 + AAC)
miksan video umwandeln film.mkv --to webm --qualitaet klein --aufloesung 720
miksan video umwandeln *.mov -o fertig/ --ohne-ton --fps 30
miksan video kuerzen film.mp4 --start 0:12 --ende 1:30   # ohne Neukodierung (schnell)
miksan video kuerzen film.mp4 --start 12.5 --genau       # bildgenau (neu kodiert)
miksan video verkleinern film.mp4 --zielgroesse 10MB     # z. B. für Discord oder Mail
miksan video gif film.mp4 --start 5 --ende 8 --breite 480 --fps 12
miksan video ton film.mp4 --to m4a                       # Ton herausziehen
miksan video bild film.mp4 --zeit 0:42 -o standbild.png  # Einzelbild speichern
```

| Aktion | Ergebnis ohne `-o` | Optionen |
|---|---|---|
| `umwandeln` (`convert`) | `<name>.mp4` bzw. `.<ziel>` | `--to mp4/webm/mkv/mov/gif`, `--qualitaet klein/ausgewogen/hoch` (Standard ausgewogen), `--crf N`, `--aufloesung 1080/720/480` (nur verkleinern), `--fps`, `--ohne-ton`, `--start`, `--ende` |
| `kuerzen` (`trim`) | `<name>-gekuerzt.<endung>` | `--start`, `--ende`, `--genau` |
| `verkleinern` (`shrink`) | `<name>-klein.mp4` | `--zielgroesse 10MB` (Pflicht), `--aufloesung` |
| `gif` | `<name>.gif` | `--breite` (Standard 480), `--fps` (Standard 12), `--start`, `--ende` |
| `ton` (`audio`) | `<name>.mp3` | `--to`, `--qualitaet` |
| `bild` (`frame`) | `<name>-bild-0-42.png` | `--zeit` (Standard: Anfang), Endung von `-o`: png, jpg, webp |

- **Qualitätsstufen** statt roher Zahlen: MP4/MKV/MOV nutzen H.264 mit CRF 28 / 23 / 18 und AAC
  96 / 160 / 256 kbit/s, WebM nutzt VP9 mit CRF 38 / 32 / 26 und Opus. `--crf` überschreibt.
- **Kürzen ohne Neukodierung** kopiert die Daten nur (sehr schnell, keine Qualitätsverluste),
  beginnt aber am nächsten Schlüsselbild; `--genau` kodiert neu und schneidet bildgenau.
- **Auf Zielgrösse verkleinern** rechnet die Bitrate aus der Dauer (5 % Reserve) und kodiert
  in zwei Durchgängen mit H.264. Ist das Ergebnis trotzdem grösser, wird mit kleinerer Bitrate
  wiederholt – die Datei ist danach höchstens so gross wie verlangt. Ist die Zielgrösse für
  die Länge zu klein, gibt es eine klare Meldung.
- **Video → GIF** erstellt zuerst eine eigene Farbpalette für das Video (deutlich schöner als
  die Standardfarben).

## Audio – `miksan audio`

```bash
miksan audio lied.wav --to mp3                         # -> lied.mp3
miksan audio *.flac --to opus --qualitaet klein -o unterwegs/
miksan audio podcast.mp3 --normalisieren --start 0:30  # Lautstärke angleichen, kürzen
miksan audio lied.flac --to m4a --bitrate 256k
```

Ziele: **MP3, WAV, FLAC, OGG (Vorbis), Opus, M4A (AAC)**. Optionen: `--qualitaet`,
`--bitrate`, `--normalisieren` (Lautheit nach EBU R128, −16 LUFS), `--start`, `--ende`.
**Titel, Interpret und Album bleiben erhalten**, das **Cover** bei MP3, M4A und FLAC.

## Oberfläche

Bereich **Video & Audio** in der Seitenleiste: *Video umwandeln*, *Video kürzen*,
*Video verkleinern*, *Video → GIF*, *Ton herausziehen*, *Einzelbild speichern*,
*Audio umwandeln*. Die Dateiliste zeigt das erste Bild des Videos (bzw. das Cover), die Dauer,
die Auflösung und die Grösse. Mehrere Dateien werden **nacheinander** verarbeitet (ffmpeg nutzt
selbst alle Prozessorkerne); der Fortschritt kommt in Prozent direkt aus ffmpeg.
**Abbrechen** beendet ffmpeg sofort und löscht die halbfertige Datei – es bleibt nie eine
kaputte Datei liegen (geschrieben wird erst in eine Zwischendatei, die am Ende umbenannt wird).

## Lizenz

Der Code von Miksan-Converter bleibt MIT. ffmpeg ist ein eigenes Programm mit eigener Lizenz:

| Teil | Lizenz |
|---|---|
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) (Extra `[medien]`) | BSD-2-Clause |
| mitgeliefertes ffmpeg-Programm (aus imageio-ffmpeg, im Windows-Installer) | **GPL-3.0** – übersetzt mit `--enable-gpl --enable-version3` (u. a. x264) |
| eigenes ffmpeg (PATH oder Einstellungen) | je nach Build LGPL oder GPL |

Weil das mitgelieferte ffmpeg nur als getrenntes Programm aufgerufen wird, bleibt
Miksan-Converter selbst MIT. Der Windows-Installer legt den GPL-Text und Hinweise zum
Quelltext in den Ordner `lizenzen\` des Programms (`FFMPEG.txt`, `FFMPEG-COPYING.GPLv3.txt`).
Welche Version und welche Übersetzungsoptionen genutzt werden, zeigt `ffmpeg -version` bzw.
Einstellungen → Video & Audio.

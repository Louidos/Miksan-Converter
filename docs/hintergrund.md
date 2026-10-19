# Hintergrund entfernen

```bash
pip install "miksan-converter[ki]"

miksan hintergrund portrait.jpg portrait.png     # oder kurz: miksan bg …
miksan bg portrait.jpg                           # -> portrait-freigestellt.png
miksan bg produkt.heic produkt.jpg --background "#ffffff"
miksan bg portrait.jpg maske.png --nur-maske
miksan bg portrait.jpg portrait.png --modell genau
```

Das Freistellen läuft **lokal auf der CPU** mit [rembg](https://github.com/danielgatis/rembg)
(ONNX Runtime). Es werden keine Bilder hochgeladen, es gibt keine Cloud und keine Telemetrie.

## Optionen

| Option | Bedeutung |
|---|---|
| `--modell NAME` (`--model`) | Modell wählen, siehe unten. Standard: `klein` |
| `--nur-maske` (`--mask-only`) | nur die Maske ausgeben (weiss = Vordergrund, schwarz = Hintergrund) |
| `--background FARBE` | Füllfarbe, wenn das Ziel keine Transparenz kann (z. B. JPEG). Standard: Weiss |
| `--to FORMAT` | Zielformat, wenn keine Ausgabedatei angegeben ist (Standard: PNG) |
| `--overwrite`, `--page N`, `--verbose` | wie bei `miksan convert` |

Transparenz bleibt in **PNG, WebP, AVIF**, HEIC, TIFF, TGA, QOI und JPEG 2000 erhalten. Ohne
Ausgabedatei entsteht `<name>-freigestellt.png` (bzw. `<name>-maske.png`) neben dem Original;
das Original wird nie verändert.

## Modelle

| Name | rembg-Modell | Grösse (Download) | Wofür | Lizenz |
|---|---|---|---|---|
| `klein` (Standard) | `u2netp` | ca. 5 MB | schnell, für die meisten Motive | Apache-2.0 |
| `genau` | `isnet-general-use` | ca. 180 MB | genauere Kanten | Apache-2.0 |
| `person` | `u2net_human_seg` | ca. 170 MB | Personen | Apache-2.0 |
| `sehr-genau` | `birefnet-general` | ca. 970 MB | sehr genau, deutlich langsamer | MIT |

Andere rembg-Modellnamen (z. B. `silueta`, `isnet-anime`) können direkt angegeben werden; deren
Lizenz bitte selbst prüfen.

## Speicherort der Modelle

Ein Modell wird **beim ersten Gebrauch einmal heruntergeladen** (das ist der einzige
Netzwerkzugriff von Miksan-Converter) und danach **offline** aus diesem Ordner geladen:

| System | Ordner |
|---|---|
| Linux | `~/.cache/miksan-converter/modelle` (bzw. `$XDG_CACHE_HOME/miksan-converter/modelle`) |
| macOS | `~/Library/Caches/miksan-converter/modelle` |
| Windows | `%LOCALAPPDATA%\miksan-converter\modelle` |

Anpassen lässt sich der Ordner mit der Umgebungsvariable `MIKSAN_MODELL_ORDNER`. Ist bereits
`REMBG_HOME` oder `U2NET_HOME` gesetzt (eigene rembg-Installation), wird dieser Ordner genutzt,
damit Modelle nicht doppelt geladen werden. Zum Aufräumen kann der Ordner einfach gelöscht
werden.

Ohne Extra `[ki]` erscheint: „Bitte `pip install miksan-converter[ki]` installieren“
(Rückgabecode 3).

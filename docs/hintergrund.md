# Hintergrund entfernen

```bash
pip install "miksan-converter[ki]"

miksan hintergrund portrait.jpg portrait.png     # oder kurz: miksan bg …
miksan bg portrait.jpg                           # -> portrait-freigestellt.png
miksan bg produkt.heic produkt.jpg --background "#ffffff"
miksan bg portrait.jpg maske.png --nur-maske
miksan bg portrait.jpg portrait.png --modell genau
miksan bg portrait.jpg portrait.png --kante 3             # weicherer Rand
miksan bg portrait.jpg pass.jpg --neue-farbe weiss        # neuer Hintergrund: Farbe
miksan bg produkt.jpg werbung.jpg --neues-bild strand.jpg # neuer Hintergrund: Bild
miksan bg portrait.jpg unscharf.jpg --weichzeichnen       # Original weichgezeichnet
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
| `--kante PX` (`--feather`) | Rand der Maske um 0–50 Pixel weicher machen (Standard: 0 = wie bisher) |
| `--neue-farbe FARBE` (`--replace-color`) | neuen Hintergrund in dieser Farbe setzen (z. B. `weiss`, `"#1e6fe0"`) |
| `--neues-bild DATEI` (`--replace-image`) | Bild als neuen Hintergrund, füllend eingepasst (wird zugeschnitten, nicht verzerrt) |
| `--weichzeichnen [STÄRKE]` (`--blur`) | weichgezeichnetes Original als Hintergrund (Standard-Stärke 20) |
| `--overwrite`, `--page N`, `--verbose` | wie bei `miksan convert` |

Die drei Optionen für einen neuen Hintergrund schliessen sich gegenseitig aus und lassen sich
nicht mit `--nur-maske` verbinden. Ohne diese Optionen verhält sich `miksan hintergrund` genau
wie bisher (transparenter Hintergrund).

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

Der **Windows-Installer** bringt das Modell `klein` mit (Lizenz Apache-2.0, Lizenztext im
Programmordner), damit Hintergrund entfernen sofort und ohne Internet funktioniert. In der
Oberfläche zeigt die Modellauswahl, ob ein Modell schon geladen ist; fehlende Modelle lädt der
Knopf **Herunterladen** mit Fortschrittsanzeige – nie ungefragt mitten im Lauf.

## In der Oberfläche

Auf der Seite „Hintergrund entfernen“: Modell wählen (mit Grösse), **Neuer Hintergrund**
(Transparent, Farbe mit Schnellwahl Weiss/Schwarz/Blau, eigenes Bild, weichgezeichnetes
Original), **Kante weicher** (0–10 px) und Zielformat. Die Vorschau zeigt das freigestellte
Bild; die Maske wird pro Datei und Modell nur einmal gerechnet, ein Wechsel des Hintergrunds
oder der Kante ist deshalb sofort sichtbar.

## Speicherort der Modelle

Ein Modell wird **einmal heruntergeladen** – in der Oberfläche nur über den Knopf
„Herunterladen“, in der Kommandozeile beim ersten Gebrauch (das ist der einzige
Netzwerkzugriff von Miksan-Converter) – und danach **offline** aus diesem Ordner geladen:

| System | Ordner |
|---|---|
| Linux | `~/.cache/miksan-converter/modelle` (bzw. `$XDG_CACHE_HOME/miksan-converter/modelle`) |
| macOS | `~/Library/Caches/miksan-converter/modelle` |
| Windows | `%LOCALAPPDATA%\miksan-converter\modelle` |

Anpassen lässt sich der Ordner mit der Umgebungsvariable `MIKSAN_MODELL_ORDNER`. Ist bereits
`REMBG_HOME` oder `U2NET_HOME` gesetzt (eigene rembg-Installation), wird dieser Ordner genutzt,
damit Modelle nicht doppelt geladen werden. Zum Aufräumen kann der Ordner einfach gelöscht
werden.

Mit der Umgebungsvariable `MIKSAN_KEIN_DOWNLOAD=1` wird jeder Download verboten: fehlt das
Modell lokal, gibt es eine Fehlermeldung statt eines Netzwerkzugriffs (so prüft die CI, dass der
Installer offline funktioniert).

Ohne Extra `[ki]` erscheint: „Bitte `pip install miksan-converter[ki]` installieren“
(Rückgabecode 3).

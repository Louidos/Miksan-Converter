# Miksan-Converter

Leichtes Open-Source-Kommandozeilentool zum Umwandeln und Bearbeiten von Bildern – lokal, ohne Cloud
und ohne Telemetrie.

## Projektstand

Im Aufbau, noch keine veröffentlichte Version. Vorhanden:

- Umwandeln zwischen allen gängigen Bildformaten (`miksan convert`): PNG, JPEG, WebP, GIF, BMP,
  TIFF, ICO, TGA, PPM/PGM, AVIF, HEIC/HEIF, JPEG 2000, QOI; PDF als Ziel; SVG und Kamera-RAW als
  Eingabe (optional). Ausrichtung, Farbprofile, Animationen und mehrseitige TIFF bleiben erhalten.
- Formatliste (`miksan formats`), siehe [docs/formate.md](docs/formate.md)
- Hintergrund entfernen mit lokalem KI-Modell (`miksan hintergrund`, kurz `miksan bg`; optional),
  siehe [docs/hintergrund.md](docs/hintergrund.md)

Geplant: JPEG XL, PSD mit Ebenen.

## Installation

Voraussetzung: Python 3.11 oder neuer.

```bash
pip install git+https://github.com/Louidos/Miksan-Converter.git
```

Oder aus einem geklonten Repo:

```bash
pip install .
```

Optionale Extras (der Kern bleibt schlank):

```bash
pip install "miksan-converter[svg]"   # SVG als Eingabe
pip install "miksan-converter[raw]"   # Kamera-RAW als Eingabe
pip install "miksan-converter[ki]"    # Hintergrund entfernen (lokales KI-Modell)
```

## Start

```bash
miksan convert foto.png foto.jpg      # Zielformat aus der Endung
miksan convert foto.png --to webp     # erzeugt foto.webp neben dem Original
miksan convert IMG_0001.HEIC IMG_0001.jpg
miksan convert logo.png logo.jpg --background "#000000"
miksan convert scan.tif seite3.png --page 3
miksan bg portrait.jpg portrait.png   # Hintergrund entfernen (Extra [ki])
miksan formats                        # alle unterstützten Formate
```

Mehr dazu in [docs/bedienung.md](docs/bedienung.md).

## Entwicklung

Mit [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/Louidos/Miksan-Converter.git
cd Miksan-Converter
uv sync
uv run ruff check .
uv run pytest
```

## Lizenz

MIT, siehe [LICENSE](LICENSE).

Genutzte Bibliotheken und ihre Lizenzen:

| Bibliothek | Zweck | Lizenz |
|---|---|---|
| [Pillow](https://python-pillow.org/) | Bilder lesen und schreiben | MIT-CMU (HPND) |
| [pillow-heif](https://github.com/bigcat88/pillow_heif) | HEIC/HEIF | BSD-3-Clause ¹ |
| [resvg-py](https://github.com/baseplate-admin/resvg-py) (Extra `[svg]`) | SVG rendern | MIT |
| [rawpy](https://github.com/letmaik/rawpy) (Extra `[raw]`) | Kamera-RAW entwickeln | MIT ² |

¹ Die Binärpakete von pillow-heif enthalten libheif und libde265 (LGPL-3.0) sowie x265
(GPL-2.0-or-later). Miksan-Converter selbst verteilt diese Bibliotheken nicht, sie werden bei der
Installation von PyPI geladen; der Code dieses Projekts bleibt MIT. Wer ein Paket mit allen
Abhängigkeiten weitergibt, muss deren Lizenzen beachten.
| [rembg](https://github.com/danielgatis/rembg) (Extra `[ki]`) | Hintergrund entfernen | MIT ³ |
| [ONNX Runtime](https://onnxruntime.ai/) (Extra `[ki]`) | KI-Modell auf der CPU ausführen | MIT |

² rawpy enthält LibRaw (LGPL-2.1 oder CDDL-1.0).
³ Die Modelle werden beim ersten Gebrauch geladen; Lizenzen der Modelle stehen in
[docs/hintergrund.md](docs/hintergrund.md).

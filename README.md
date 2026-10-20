# Miksan-Converter

Leichtes Open-Source-Tool zum Umwandeln und Bearbeiten von Bildern – mit Kommandozeile und
grafischer Oberfläche, lokal, ohne Cloud und ohne Telemetrie.

## Projektstand

Aktuelle Version: **0.1.0** (siehe [CHANGELOG.md](CHANGELOG.md)). Enthalten:

- Umwandeln zwischen allen gängigen Bildformaten (`miksan convert`): PNG, JPEG, WebP, GIF, BMP,
  TIFF, ICO, TGA, PPM/PGM, AVIF, HEIC/HEIF, JPEG 2000, QOI; PDF als Ziel; SVG und Kamera-RAW als
  Eingabe (optional). Ausrichtung, Farbprofile, Animationen und mehrseitige TIFF bleiben erhalten.
- Formatliste (`miksan formats`), siehe [docs/formate.md](docs/formate.md)
- Bilder skalieren, zuschneiden, drehen, spiegeln, komprimieren (Qualität oder Zielgrösse) und
  Metadaten entfernen – beim Umwandeln oder mit `miksan bearbeiten`, siehe
  [docs/bearbeiten.md](docs/bearbeiten.md)
- Ganze Ordner, mehrere Dateien und Muster wie `*.heic` auf einmal verarbeiten – parallel, mit
  Fortschrittsanzeige und Zusammenfassung, siehe [docs/ordner.md](docs/ordner.md)
- Hintergrund entfernen mit lokalem KI-Modell (`miksan hintergrund`, kurz `miksan bg`; optional),
  siehe [docs/hintergrund.md](docs/hintergrund.md)
- Grafische Oberfläche (`miksan-gui`; optional): Bilder und Ordner per Drag & Drop umwandeln,
  bearbeiten und freistellen, mit Fortschritt, Abbrechen und Zusammenfassung, siehe
  [docs/oberflaeche.md](docs/oberflaeche.md) *(noch nicht veröffentlicht)*
- Windows-Installer (`MiksanConverter-Setup-X.Y.Z.exe`) ohne Python, siehe
  [docs/installer.md](docs/installer.md) *(noch nicht veröffentlicht)*

Geplant: JPEG XL, PSD mit Ebenen.

## Installation

**Windows:** Installer `MiksanConverter-Setup-X.Y.Z.exe` unter
[Releases](https://github.com/Louidos/Miksan-Converter/releases) herunterladen und ausführen –
ohne Python, mit Oberfläche, Kommandozeile `miksan` und allen Extras. Weil der Installer nicht
signiert ist, kann Windows SmartScreen beim ersten Start warnen: „Weitere Informationen“ →
„Trotzdem ausführen“. Details in [docs/installer.md](docs/installer.md).

**Mit pip** (Windows, macOS, Linux), Voraussetzung: Python 3.11 oder neuer.

```bash
pip install "git+https://github.com/Louidos/Miksan-Converter.git@v0.1.0"
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
pip install "miksan-converter[gui]"   # grafische Oberfläche (miksan-gui)
pip install "miksan-converter[gui,ki,svg,raw]"   # alles
```

## Start

Grafische Oberfläche (Extra `[gui]`):

```bash
miksan-gui                            # oder: miksan gui
```

Kommandozeile:

```bash
miksan convert foto.png foto.jpg      # Zielformat aus der Endung
miksan convert foto.png --to webp     # erzeugt foto.webp neben dem Original
miksan convert IMG_0001.HEIC IMG_0001.jpg
miksan convert logo.png logo.jpg --background "#000000"
miksan convert scan.tif seite3.png --page 3
miksan convert gross.jpg klein.webp --max 1200
miksan bearbeiten foto.jpg --zielgroesse 300KB --metadaten-entfernen
miksan bg portrait.jpg portrait.png   # Hintergrund entfernen (Extra [ki])
miksan convert fotos/ --to jpg -o fertig/        # ganzer Ordner
miksan bg fotos/ -o freigestellt/ --rekursiv
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
| [rembg](https://github.com/danielgatis/rembg) (Extra `[ki]`) | Hintergrund entfernen | MIT ³ |
| [ONNX Runtime](https://onnxruntime.ai/) (Extra `[ki]`) | KI-Modell auf der CPU ausführen | MIT |
| [PySide6](https://doc.qt.io/qtforpython-6/) (Extra `[gui]`) | grafische Oberfläche (Qt) | LGPL-3.0 ⁴ |

¹ Die Binärpakete von pillow-heif enthalten libheif und libde265 (LGPL-3.0) sowie x265
(GPL-2.0-or-later). Miksan-Converter selbst verteilt diese Bibliotheken nicht, sie werden bei der
Installation von PyPI geladen; der Code dieses Projekts bleibt MIT. Wer ein Paket mit allen
Abhängigkeiten weitergibt, muss deren Lizenzen beachten.
² rawpy enthält LibRaw (LGPL-2.1 oder CDDL-1.0).
³ Die Modelle werden beim ersten Gebrauch geladen; Lizenzen der Modelle stehen in
[docs/hintergrund.md](docs/hintergrund.md).
⁴ PySide6 und Qt stehen unter LGPL-3.0. Miksan-Converter bindet sie nur dynamisch ein und
verändert sie nicht; der Code dieses Projekts bleibt MIT.

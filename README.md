# Miksan-Converter

Leichtes Open-Source-Kommandozeilentool zum Umwandeln und Bearbeiten von Bildern – lokal, ohne Cloud
und ohne Telemetrie.

## Projektstand

Im Aufbau, noch keine veröffentlichte Version. Vorhanden: Umwandeln zwischen PNG, JPEG, WebP, GIF,
BMP und TIFF (`miksan convert`) und die Formatliste (`miksan formats`).

## Installation

Voraussetzung: Python 3.11 oder neuer.

```bash
pip install git+https://github.com/Louidos/Miksan-Converter.git
```

Oder aus einem geklonten Repo:

```bash
pip install .
```

## Start

```bash
miksan convert foto.png foto.jpg      # Zielformat aus der Endung
miksan convert foto.png --to webp     # erzeugt foto.webp neben dem Original
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

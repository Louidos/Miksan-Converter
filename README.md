# Miksan-Converter

Leichtes Open-Source-Kommandozeilentool zum Umwandeln und Bearbeiten von Bildern – lokal, ohne Cloud
und ohne Telemetrie.

## Projektstand

Im Aufbau, noch keine veröffentlichte Version.

## Installation (Entwicklung)

Voraussetzung: Python 3.11 oder neuer und [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/Louidos/Miksan-Converter.git
cd Miksan-Converter
uv sync
```

## Tests und Linter

```bash
uv run ruff check .
uv run pytest
```

## Lizenz

MIT, siehe [LICENSE](LICENSE).

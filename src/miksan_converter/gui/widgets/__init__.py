"""Wiederverwendbare Bausteine der Werkzeug-Seiten (Ablagefläche, Dateiliste, Ablaufleiste …)."""

from __future__ import annotations

from pathlib import Path


def abgelegte_pfade(event) -> list[str]:
    """Lokale Dateien und Ordner aus einem Drag-&-Drop-Ereignis."""
    daten = event.mimeData()
    if not daten.hasUrls():
        return []
    return [str(Path(url.toLocalFile())) for url in daten.urls() if url.isLocalFile()]

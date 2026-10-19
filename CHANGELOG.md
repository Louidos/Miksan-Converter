# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei festgehalten.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionen folgen [Semantic Versioning](https://semver.org/lang/de/).

## Unveröffentlicht

### Hinzugefügt

- Befehl `miksan convert` zum Umwandeln von Bildern und `miksan formats` für die Formatliste (#2)
- Unterstützung für alle gängigen Bildformate inkl. HEIC, AVIF, WebP, TIFF, ICO, SVG und RAW (optional); Ausrichtung, Farbprofile, Animationen und mehrseitige TIFF bleiben erhalten, Transparenz wird bei JPEG & Co. auf `--background` gelegt (#3)
- Hintergrund von Bildern lokal entfernen mit `miksan hintergrund` (optional, Extra `[ki]`) (#4)

# Changelog

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei festgehalten.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
die Versionen folgen [Semantic Versioning](https://semver.org/lang/de/).

## Unveröffentlicht

### Hinzugefügt

- Vorschau mit Vorher/Nachher-Schieber und geschätzter Dateigrösse vor dem Umwandeln (#21)

### Geändert

- Die Oberfläche hat ein neues, helles Design in Blau und Weiss mit eigenen Icons (#19)
- Neue Aufteilung der App: Startseite und Seitenleiste mit je einer eigenen Seite pro Werkzeug, Dateiliste mit Miniaturbildern (#20)

## 0.2.0 – 2026-10-20

### Hinzugefügt

- Grafische Oberfläche (`miksan-gui`): Bilder und Ordner per Drag & Drop umwandeln, bearbeiten und freistellen, mit Fortschritt und Zusammenfassung (Extra `[gui]`) (#14)
- Windows-Installer (`MiksanConverter-Setup-X.Y.Z.exe`): Miksan-Converter ohne Python installieren, mit Startmenü-Eintrag, Kommandozeile `miksan` und Deinstallation (#15)

## 0.1.0 – 2026-10-19

### Hinzugefügt

- Befehl `miksan convert` zum Umwandeln von Bildern und `miksan formats` für die Formatliste (#2)
- Unterstützung für alle gängigen Bildformate inkl. HEIC, AVIF, WebP, TIFF, ICO, SVG und RAW (optional); Ausrichtung, Farbprofile, Animationen und mehrseitige TIFF bleiben erhalten, Transparenz wird bei JPEG & Co. auf `--background` gelegt (#3)
- Hintergrund von Bildern lokal entfernen mit `miksan hintergrund` (optional, Extra `[ki]`) (#4)
- Bilder beim Umwandeln skalieren, zuschneiden, drehen, komprimieren und Metadaten entfernen; neuer Befehl `miksan bearbeiten` (#5)
- Ganze Ordner und mehrere Dateien auf einmal verarbeiten, parallel und mit Zusammenfassung (#6)

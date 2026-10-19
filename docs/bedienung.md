# Bedienung

## `miksan convert` – Bild umwandeln

```bash
miksan convert <eingabe> <ausgabe> [--to FORMAT] [--overwrite] [--verbose]
miksan convert <eingabe> --to FORMAT
```

- Das **Eingabeformat** wird am Inhalt der Datei erkannt. Eine falsche Endung (z. B. ein PNG,
  das `bild.jpg` heisst) stört nicht.
- Das **Zielformat** ergibt sich aus der Endung der Ausgabedatei oder aus `--to` (Alias `--nach`).
  Ohne Ausgabedatei wird die neue Datei neben dem Original mit passender Endung abgelegt.
  Widersprechen sich Endung und `--to`, bricht der Befehl mit einer Meldung ab.
- Eine vorhandene Zieldatei wird **nie stillschweigend überschrieben**. Mit `--overwrite`
  (Alias `--ueberschreiben`) wird sie ersetzt. Die Eingabedatei selbst wird nie verändert.
- `--verbose` (Alias `-v`, `--ausfuehrlich`) zeigt Details und bei Fehlern die technische Ursache.

## `miksan formats` – Formatliste

Zeigt alle unterstützten Formate mit Endungen und ob sie gelesen und geschrieben werden können
(Alias `miksan formate`).

## Rückgabecodes

| Code | Bedeutung |
|---|---|
| 0 | alles in Ordnung |
| 1 | Fehler bei der Verarbeitung (z. B. Datei fehlt, beschädigt, Ziel vorhanden) |
| 2 | falsche Bedienung (z. B. unbekanntes Format, widersprüchliche Angaben) |
| 130 | mit Strg+C abgebrochen |

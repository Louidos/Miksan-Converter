# Bedienung

## `miksan convert` – Bild umwandeln

```bash
miksan convert <eingabe> <ausgabe> [--to FORMAT] [--overwrite] [--background FARBE]
                                   [--page N] [--verbose]
miksan convert <eingabe> --to FORMAT
```

- Das **Eingabeformat** wird am Inhalt der Datei erkannt. Eine falsche Endung (z. B. ein PNG,
  das `bild.jpg` heisst) stört nicht.
- Das **Zielformat** ergibt sich aus der Endung der Ausgabedatei oder aus `--to` (Alias `--nach`).
  Ohne Ausgabedatei wird die neue Datei neben dem Original mit passender Endung abgelegt.
  Widersprechen sich Endung und `--to`, bricht der Befehl mit einer Meldung ab.
- Eine vorhandene Zieldatei wird **nie stillschweigend überschrieben**. Mit `--overwrite`
  (Alias `--ueberschreiben`) wird sie ersetzt. Die Eingabedatei selbst wird nie verändert.
- `--background FARBE` (Alias `--hintergrundfarbe`): Füllfarbe für transparente Bereiche, wenn
  das Ziel keine Transparenz kann (z. B. JPEG). Standard Weiss; Beispiele: `"#000000"`,
  `schwarz`, `white`.
- `--page N` (Alias `--seite`): nur diese Seite bzw. dieses Einzelbild übernehmen (ab 1), z. B.
  aus einem mehrseitigen TIFF oder einer Animation.
- `--verbose` (Alias `-v`, `--ausfuehrlich`) zeigt Details und bei Fehlern die technische Ursache.

Welche Formate unterstützt werden und was beim Umwandeln erhalten bleibt, steht in
[formate.md](formate.md).

## `miksan formats` – Formatliste

Zeigt alle unterstützten Formate mit Endungen, ob sie gelesen und geschrieben werden können,
welches Extra nötig ist und welche Einschränkungen gelten (Alias `miksan formate`).
`--markdown` gibt die Tabelle im Markdown-Format aus.

## Rückgabecodes

| Code | Bedeutung |
|---|---|
| 0 | alles in Ordnung |
| 1 | Fehler bei der Verarbeitung (z. B. Datei fehlt, beschädigt, Ziel vorhanden) |
| 2 | falsche Bedienung (z. B. unbekanntes Format, widersprüchliche Angaben) |
| 3 | ein optionales Extra fehlt (die Meldung nennt den Installationsbefehl) |
| 130 | mit Strg+C abgebrochen |

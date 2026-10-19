# Ordner und mehrere Dateien

Alle Befehle (`convert`, `bearbeiten`, `hintergrund`/`bg`) nehmen statt einer Datei auch
**Ordner**, **mehrere Dateien** oder **Muster** wie `*.heic`:

```bash
miksan convert fotos/ --to jpg -o fertig/
miksan convert fotos/ --to webp -o web/ --rekursiv --max 1600
miksan convert "urlaub/*.heic" --to jpg -o jpg/
miksan convert a.png b.png c.png --to webp            # Ergebnisse neben den Originalen
miksan bearbeiten fotos/ -o klein/ --zielgroesse 500KB --metadaten-entfernen
miksan bg fotos/ -o freigestellt/
```

## Regeln

- **Ausgabe:** Mit `-o ORDNER` (Alias `--ausgabe-ordner`, `--output`) landen die Ergebnisse in
  diesem Ordner; er wird bei Bedarf angelegt. Ohne `-o` entstehen sie neben den Originalen
  (`bearbeiten`: `<name>-bearbeitet`, `bg`: `<name>-freigestellt`).
- **Zielformat:** `convert` braucht bei mehreren Dateien `--to`. `bearbeiten` behält das Format
  jeder Datei, `bg` speichert PNG (beides änderbar mit `--to`).
- **Ordner:** Es werden alle Dateien mit bekannter Bild-Endung genommen (siehe
  [formate.md](formate.md)); versteckte Dateien und Ordner (Name beginnt mit `.`) werden
  übersprungen. Ausdrücklich genannte Dateien werden immer versucht – das Format wird am Inhalt
  erkannt.
- **Unterordner:** nur mit `--rekursiv` (Alias `-r`, `--recursive`). Die Ordnerstruktur bleibt im
  Ausgabeordner erhalten (`fotos/urlaub/a.heic` → `fertig/urlaub/a.jpg`). Liegt der Ausgabeordner
  im Eingabeordner, werden seine Dateien nicht erneut verarbeitet.
- **Muster** wie `*.heic` oder `**/*.png` (mit `--rekursiv`) werden von Miksan selbst aufgelöst –
  das funktioniert auch unter Windows. Unter Linux/macOS am besten in Anführungszeichen setzen.
- **Zwei Dateien ohne `-o`** bedeuten Eingabe und Ausgabe (`miksan convert a.png b.jpg`). Ist
  `--to` angegeben und gibt es die zweite Datei schon, werden beide als Eingaben behandelt.
- **Gleiche Zielnamen** (z. B. `bild.png` und `bild.gif` → `bild.jpg`) werden nicht
  überschrieben, sondern als Fehler gemeldet. Vorhandene Dateien bleiben ohne `--overwrite`
  unverändert.

## Parallel und Fortschritt

Die Dateien werden parallel verarbeitet, standardmässig so viele gleichzeitig wie die CPU Kerne
hat; mit `--jobs N` (Alias `-j`) lässt sich das ändern (`--jobs 1` = nacheinander). Im Terminal
zeigt eine Zeile den Fortschritt (`[12/40] bild.jpg`). Bei `bg` wird das KI-Modell nur einmal
geladen.

## Fehler und Zusammenfassung

Eine fehlerhafte Datei bricht den Lauf nicht ab. Am Ende steht eine Zusammenfassung:

```
Fehler:
  'fotos/kaputt.jpg' ist beschädigt oder unvollständig.
7 ok, 1 Fehler
```

Der Rückgabecode ist 0, wenn alles geklappt hat, sonst 1. Mit `--verbose` wird zusätzlich jede
umgewandelte Datei aufgelistet.

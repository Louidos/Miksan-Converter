# Weitere Bild-Werkzeuge

Die typischen Kleinigkeiten, für die man sonst eine Online-Seite sucht – lokal, ohne Upload.
Alle Werkzeuge stehen in der Oberfläche im Bereich **Bilder** und in der Kommandozeile. Sie
lesen alle Formate, die Miksan-Converter kennt (HEIC, WebP, AVIF, RAW …). Originale werden
nicht verändert – ausser beim Umbenennen, das genau dafür da ist.

## Wasserzeichen

```bash
miksan wasserzeichen foto.jpg --text "© Miksan 2026"                 # -> foto-wasserzeichen.jpg
miksan wasserzeichen fotos/ --logo logo.png --position unten-links -o fertig/
miksan wasserzeichen foto.jpg --text "ENTWURF" --position gekachelt --deckkraft 25
```

| Option | Bedeutung |
|---|---|
| `--text TEXT` oder `--logo DATEI` | Text oder Bild (am besten PNG mit Transparenz) |
| `--position` | `oben-links`, `oben`, `oben-rechts`, `links`, `mitte`, `rechts`, `unten-links`, `unten`, `unten-rechts` (Standard) oder `gekachelt` (schräg über das ganze Bild) |
| `--groesse %` | Breite des Wasserzeichens in % der Bildbreite (Standard 20) |
| `--deckkraft %` | 0–100 (Standard 50) |
| `--farbe` | Textfarbe (Standard weiss, mit dunklem Rand für Lesbarkeit) |
| `-o`, `--to`, `--overwrite`, `-r` | Ausgabedatei/-ordner, Zielformat, überschreiben, Unterordner |

In der Oberfläche zeigt die **Vorschau** das Ergebnis sofort (Vorher/Nachher-Schieber).

## Stapel-Umbenennen

```bash
miksan umbenennen fotos/ --muster "urlaub-{datum}-{nr}" --probe   # nur anzeigen
miksan umbenennen fotos/ --muster "urlaub-{datum}-{nr}"
miksan umbenennen *.jpg --muster "{name}_{breite}x{hoehe}" -o kopien/   # Kopien statt umbenennen
```

Platzhalter: `{name}` (alter Name ohne Endung), `{nr}` (laufende Nummer mit führenden Nullen,
ab `--start`, Standard 1), `{datum}` (Aufnahmedatum aus EXIF, sonst Änderungsdatum,
`JJJJ-MM-TT`), `{breite}`, `{hoehe}`. Die Endung bleibt. Die Dateien werden nach Ordner und
Name sortiert nummeriert.

**Sicherheit:** Vor dem Start werden alle neuen Namen berechnet und geprüft. Entsteht ein Name
doppelt oder gibt es eine Zieldatei schon, wird **abgebrochen, ohne eine Datei anzufassen**
(Rückgabecode 2). Es wird nie etwas überschrieben. Die Oberfläche zeigt die Tabelle
„Alter Name → Neuer Name“ und die Konflikte schon beim Tippen; der Knopf bleibt dann gesperrt.

## Animation

```bash
miksan animation erstellen bild1.png bild2.png bild3.png -o anim.gif --dauer 300
miksan animation erstellen *.jpg -o anim.webp --schleife 3      # 3× wiederholen (0 = endlos)
miksan animation zerlegen anim.gif -o einzelbilder/ --format png
```

Beim Erstellen werden alle Bilder auf die Grösse des ersten eingepasst (zentriert, Rest
transparent). In der Oberfläche bestimmt die Reihenfolge der Liste die Reihenfolge
(ziehen oder Alt+↑/↓). Zerlegen speichert `<name>-bild-001.png` … (ohne `-o` in
`<name>-bilder/`).

## Icon-Set

```bash
miksan iconset logo.png                 # -> logo-icons/
miksan iconset logo.svg -o website/icons/
```

Erzeugt `favicon.ico` (16, 24, 32, 48, 64, 128, 256 px) und `icon-16x16.png`, `icon-32x32.png`,
`icon-48x48.png`, `icon-180x180.png` (Apple Touch), `icon-192x192.png`, `icon-512x512.png`.
Nicht quadratische Bilder werden zentriert und transparent aufgefüllt.

## Zuschneiden

```bash
miksan zuschneiden foto.jpg --verhaeltnis 1:1                  # mittig quadratisch
miksan zuschneiden foto.jpg --vorlage profilbild               # 400 × 400
miksan zuschneiden foto.jpg --bereich 100,50,800,800 --ziel 1080x1080
```

| Option | Bedeutung |
|---|---|
| `--verhaeltnis` | `1:1`, `4:3`, `3:4`, `16:9`, `9:16`, `3:2` oder eigenes wie `5:4` |
| `--bereich x,y,b,h` | Ausschnitt in Pixeln (sonst der grösste mittige Ausschnitt) |
| `--ziel BxH` | feste Zielmasse; das Verhältnis folgt daraus |
| `--vorlage` | `profilbild` (400×400), `instagram` (1080×1080), `instagram-hoch` (1080×1350), `story` (1080×1920), `youtube` (1280×720), `link` (1200×630), `x-kopf` (1500×500) |

In der Oberfläche wird der Ausschnitt **mit der Maus** gewählt: Rechteck aufziehen
(mit festem Verhältnis, wenn eines gewählt ist), innen ziehen verschiebt es. Hilfslinien
zeigen die Drittel. Jedes Bild der Liste merkt sich seinen eigenen Ausschnitt; „Ausschnitt
mittig“ setzt alle zurück.

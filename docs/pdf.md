# PDF-Werkzeuge

Die häufigsten PDF-Aufgaben gehen lokal in Miksan-Converter – ohne Werbe-Webseiten, ohne
Upload. Das Original wird nie verändert.

```bash
pip install "miksan-converter[pdf]"
```

Im Windows-Installer ist das Extra enthalten. Fehlt es, meldet `miksan pdf …` den
Installationsbefehl (Rückgabecode 3) und in der Oberfläche sind die Werkzeuge im Bereich
„PDF“ ausgegraut; der Rest der App läuft normal.

## Kommandozeile

```bash
miksan pdf zusammenfuegen a.pdf b.pdf c.pdf -o gesamt.pdf    # Alias: merge
miksan pdf teilen buch.pdf                                   # jede Seite einzeln (split)
miksan pdf teilen buch.pdf --seiten 1-3,5 -o teile/          # je Bereich eine Datei
miksan pdf drehen scan.pdf --grad 90 --seiten 2,4            # Alias: rotate
miksan pdf loeschen scan.pdf --seiten 3,7-8                  # Alias: delete
miksan pdf bilder buch.pdf --format png --dpi 150 -o seiten/ # PDF → Bilder (to-images)
miksan pdf aus-bildern foto1.jpg foto2.heic -o album.pdf     # Bilder → PDF (from-images)
miksan pdf aus-bildern scan.png --seitengroesse bild         # Seite so gross wie das Bild
miksan pdf verkleinern gross.pdf --qualitaet 60              # Alias: compress
```

| Aktion | Ergebnis ohne `-o` | Optionen |
|---|---|---|
| `zusammenfuegen` | `<erstes>-zusammengefuegt.pdf` | Reihenfolge = Reihenfolge der Argumente |
| `teilen` | `<name>-seite-3.pdf` bzw. `<name>-seiten-1-3.pdf` neben dem Original | `--seiten 1-3,5` (leer = jede Seite einzeln) |
| `drehen` | `<name>-gedreht.pdf` | `--grad 90/180/270` (im Uhrzeigersinn), `--seiten` (Standard: alle) |
| `loeschen` | `<name>-bearbeitet.pdf` | `--seiten` (Pflicht; mindestens eine Seite muss bleiben) |
| `bilder` | `<name>-seite-01.png` … neben dem Original | `--format png/jpeg`, `--dpi` (Standard 150), `--seiten` |
| `aus-bildern` | `<erstes>.pdf` | `--seitengroesse a4` (Standard, Bild mit Rand eingepasst, hoch oder quer) oder `bild` |
| `verkleinern` | `<name>-klein.pdf` | `--qualitaet` 1–100 (Standard 70); zeigt Grösse vorher → nachher |

Alle Aktionen kennen `--overwrite` und (ausser `aus-bildern`) `--passwort` für geschützte PDFs.
Seitenangaben beginnen bei 1: `1-3,5`, `4-` (ab Seite 4), `-2` (bis Seite 2).

**Verkleinern** komprimiert eingebettete Bilder neu als JPEG (sehr grosse werden auf höchstens
2000 Pixel verkleinert) und fasst doppelte Objekte zusammen. Text und Vektorgrafik bleiben
unverändert. Wird die Datei dadurch nicht kleiner, bleibt der Inhalt wie im Original.

## Oberfläche

Bereich **PDF** in der Seitenleiste: *PDF zusammenfügen*, *PDF teilen*,
*Seiten drehen & löschen*, *PDF → Bilder*, *Bilder → PDF*, *PDF verkleinern*.

- Die Dateiliste zeigt zu jedem PDF eine Miniatur der ersten Seite und die Seitenzahl.
- Beim Teilen, Drehen/Löschen und PDF → Bilder zeigt die Seite unter der Liste **alle Seiten
  als Miniaturen**. Markierte Seiten werden ins Feld „Bereiche“ bzw. „Seiten“ übernommen.
- Beim Zusammenfügen und bei Bilder → PDF bestimmt die Reihenfolge der Liste die Reihenfolge
  im PDF: Einträge mit der Maus ziehen oder mit **Alt+↑/↓** verschieben.
- **Passwortgeschützte PDFs**: beim Start fragt das Fenster nach dem Passwort (bei falschem
  Passwort noch einmal). Das Passwort wird nicht gespeichert.
- **Defekte PDFs** brechen nichts ab: die Zeile zeigt „… ist kein gültiges oder ein
  beschädigtes PDF“, die übrigen Dateien werden verarbeitet.

## Bibliotheken

| Bibliothek | Zweck | Lizenz |
|---|---|---|
| [pypdf](https://github.com/py-pdf/pypdf) | zusammenfügen, teilen, drehen, löschen, verkleinern | BSD-3-Clause |
| [pypdfium2](https://github.com/pypdfium2-team/pypdfium2) | Seiten zu Bildern rendern (PDFium) | Apache-2.0 / BSD-3-Clause |

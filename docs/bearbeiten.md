# Bilder bearbeiten

Alle Bearbeitungen gehen direkt beim Umwandeln (`miksan convert`) oder einzeln mit
`miksan bearbeiten` (Alias `edit`). Ohne Ausgabedatei legt `bearbeiten` die Datei
`<name>-bearbeitet.<endung>` im selben Format neben das Original. Das Original wird nie verändert.

```bash
miksan convert gross.jpg klein.webp --max 1200
miksan bearbeiten foto.jpg --zielgroesse 300KB         # -> foto-bearbeitet.jpg
miksan bearbeiten scan.png --zuschneiden 40,40,800,600 --drehen 90
miksan convert IMG_0001.HEIC teilen.jpg --max 2000 --metadaten-entfernen
```

## Optionen

| Option | Alias | Bedeutung |
|---|---|---|
| `--breite PX` | `--width` | neue Breite; ohne `--hoehe` bleibt das Seitenverhältnis |
| `--hoehe PX` | `--height` | neue Höhe; ohne `--breite` bleibt das Seitenverhältnis |
| `--max PX` | | längste Seite höchstens so lang, Seitenverhältnis bleibt; vergrössert nie |
| `--zuschneiden X,Y,B,H` | `--crop` | Ausschnitt ab linker oberer Ecke (x, y) mit Breite und Höhe in Pixeln |
| `--drehen 90\|180\|270` | `--rotate` | im Uhrzeigersinn drehen |
| `--spiegeln h\|v` | `--flip` | `h` = waagrecht (links/rechts tauschen), `v` = senkrecht (oben/unten) |
| `--qualitaet 1–100` | `--quality` | Qualität für JPEG, WebP, AVIF und HEIC (bei verlustfreien Formaten ohne Wirkung) |
| `--zielgroesse GRÖSSE` | `--target-size` | Datei höchstens so gross, z. B. `500KB`, `1.5MB`, `2MiB` |
| `--metadaten-entfernen` | `--strip` | EXIF (inkl. GPS, Kamera, Datum) und XMP entfernen |

Sind `--breite` und `--hoehe` beide angegeben, entsteht genau diese Grösse (das Seitenverhältnis
kann sich dann ändern). `--max` kann mit `--breite`/`--hoehe` kombiniert werden.

## Reihenfolge

Die Schritte laufen immer in dieser festen Reihenfolge:

1. **Ausrichtung** – die EXIF-Ausrichtung des Fotos wird angewendet
2. **Zuschnitt** – Koordinaten beziehen sich auf das richtig ausgerichtete Bild
3. **Drehen**
4. **Spiegeln**
5. **Grösse** (`--breite`, `--hoehe`, `--max`)
6. **Speichern** (Qualität, Zielgrösse, Metadaten)

## Zielgrösse

`--zielgroesse` sucht die höchste Qualität, bei der die Datei höchstens so gross ist. Reicht
selbst die niedrigste Qualität nicht, wird das Bild schrittweise verkleinert (mit Hinweis).
`KB`/`MB` sind 1000 bzw. 1 000 000 Byte, `KiB`/`MiB` 1024 bzw. 1 048 576 Byte. Das geht nur bei
verlustbehafteten Formaten (JPEG, WebP, AVIF, HEIC).

## Metadaten

Standardmässig bleiben EXIF, XMP und das Farbprofil erhalten. `--metadaten-entfernen` entfernt
EXIF (u. a. GPS-Position, Kameramodell, Aufnahmezeit) und XMP. Weil die Ausrichtung schon vorher
angewendet wird, steht das Bild danach trotzdem richtig. Das ICC-Farbprofil bleibt erhalten, damit
die Farben stimmen – es enthält keine persönlichen Daten.

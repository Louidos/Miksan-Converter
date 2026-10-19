# Unterstützte Formate

Das Eingabeformat wird immer am **Dateiinhalt** erkannt, nicht an der Endung. Die Endungen in der
Tabelle bestimmen nur das **Zielformat**, wenn kein `--to` angegeben ist.
`miksan formats` zeigt dieselbe Tabelle (als Markdown: `miksan formats --markdown`).

| Format | Endungen | Lesen | Schreiben | Extra | Einschränkungen |
|---|---|---|---|---|---|
| png | `.png` `.apng` | ja | ja | – | Animation als APNG |
| jpeg | `.jpg` `.jpeg` `.jpe` `.jfif` | ja | ja | – | keine Transparenz (wird auf --background gelegt) |
| webp | `.webp` | ja | ja | – | verlustfrei, wenn die Quelle verlustfrei ist |
| gif | `.gif` | ja | ja | – | max. 256 Farben, Transparenz nur an/aus |
| bmp | `.bmp` `.dib` | ja | ja | – | keine Transparenz |
| tiff | `.tif` `.tiff` | ja | ja | – | mehrseitig; verlustfrei komprimiert (Deflate) |
| ico | `.ico` | ja | ja | – | max. 256x256, mehrere Grössen, wird quadratisch aufgefüllt |
| tga | `.tga` `.icb` `.vda` `.vst` | ja | ja | – | – |
| ppm | `.ppm` `.pgm` `.pbm` `.pnm` | ja | ja | – | keine Transparenz |
| pdf | `.pdf` | nein | ja | – | nur Schreiben; keine Transparenz |
| avif | `.avif` `.avifs` | ja | ja | – | – |
| heif | `.heic` `.heif` `.hif` | ja | ja | – | über pillow-heif |
| jpeg2000 | `.jp2` `.j2k` `.j2c` `.jpx` `.jpf` | ja | ja | – | verlustfrei gespeichert |
| qoi | `.qoi` | ja | ja | – | – |
| svg | `.svg` `.svgz` | ja | nein | [svg] | nur Lesen, wird in ein Rasterbild umgewandelt |
| raw | `.dng` `.cr2` `.cr3` `.crw` `.nef` `.nrw` `.arw` `.srf` `.sr2` `.raf` `.orf` `.rw2` `.raw` `.pef` `.srw` `.x3f` `.erf` `.3fr` `.iiq` `.mrw` `.kdc` `.dcr` `.mos` `.rwl` | ja | nein | [raw] | nur Lesen, Entwicklung mit Kamera-Weissabgleich |

Weitere Formate, die Pillow lesen kann (z. B. PSD als zusammengefügtes Bild, PCX, ICNS, DDS),
werden ebenfalls gelesen, aber nicht eigens getestet.

## Optionale Extras

| Extra | Installation | Wofür | Bibliothek |
|---|---|---|---|
| `[svg]` | `pip install miksan-converter[svg]` | SVG/SVGZ als Eingabe | resvg-py |
| `[raw]` | `pip install miksan-converter[raw]` | Kamera-RAW als Eingabe | rawpy (LibRaw) |

Fehlt ein Extra, nennt die Fehlermeldung genau den passenden Installationsbefehl
(Rückgabecode 3).

## Was beim Umwandeln erhalten bleibt

- **Ausrichtung:** Die EXIF-Ausrichtung (z. B. hochkant fotografiert) wird angewendet; das
  Ergebnis steht richtig und trägt Ausrichtung 1, damit es nicht doppelt gedreht wird.
- **Farbprofile (ICC):** bleiben bei PNG, JPEG, WebP, TIFF, AVIF und HEIC erhalten. Bei Zielen
  ohne Profil-Unterstützung (GIF, BMP, ICO, TGA, PPM, PDF, QOI, JPEG 2000) wird nach sRGB
  umgerechnet, damit die Farben stimmen.
- **EXIF/XMP:** bleiben bei PNG, JPEG, WebP, TIFF, AVIF und HEIC erhalten.
- **Transparenz:** Bei Zielen ohne Alpha-Kanal (z. B. JPEG, BMP, PDF) wird die Transparenz auf
  die Farbe aus `--background` gelegt (Standard: Weiss), z. B. `--background "#000000"` oder
  `--background schwarz`.
- **Animationen:** GIF, WebP, APNG und AVIF bleiben animiert, wenn das Ziel Animationen kann
  (GIF, WebP, PNG, AVIF); Bilddauer und Wiederholung werden übernommen.
- **Mehrere Seiten:** Mehrseitige TIFF (und Animationen) werden nach TIFF und PDF mit allen
  Seiten übernommen. Bei Zielen mit nur einem Bild wird die erste Seite genommen, mit
  `--page N` (Alias `--seite`) eine andere.
- **ICO:** Symbole mit mehreren Grössen behalten alle Grössen. Aus anderen Bildern entstehen die
  Grössen 16 bis 256 px (nicht grösser als das Original); nicht quadratische Bilder werden
  transparent aufgefüllt statt verzerrt.
- **Qualität:** Verlustfreie Quellen werden nach WebP verlustfrei gespeichert. JPEG wird mit
  Qualität 92 (ohne Farbunterabtastung), WebP 90, HEIC 90 und AVIF 85 gespeichert. TIFF wird
  verlustfrei (Deflate) komprimiert – ausser das Bild hat EXIF-Aufnahmedaten oder GPS-Angaben,
  dann wird es unkomprimiert gespeichert, damit diese erhalten bleiben. 16-Bit-Bilder bleiben in PNG, TIFF und PPM 16 Bit, sonst
  werden sie sauber auf 8 Bit umgerechnet.

## Fehlerfälle

Beschädigte oder abgeschnittene Dateien ergeben eine klare Meldung („beschädigt oder
unvollständig“) und Rückgabecode 1. Die Zieldatei wird erst in eine temporäre Datei im selben
Ordner geschrieben und danach umbenannt – es bleibt nie eine halb geschriebene Datei zurück.

## Geplant

- JPEG XL (`.jxl`)
- PSD mit einzelnen Ebenen

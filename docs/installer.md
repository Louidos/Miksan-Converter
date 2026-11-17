# Windows-Installer

Unter Windows lässt sich Miksan-Converter ohne Python wie ein normales Programm installieren.

## Installieren

1. Unter [Releases](https://github.com/Louidos/Miksan-Converter/releases) die Datei
   `MiksanConverter-Setup-X.Y.Z.exe` herunterladen.
2. Doppelklicken. Weil der Installer nicht signiert ist, kann **Windows SmartScreen** warnen
   („Der Computer wurde durch Windows geschützt“). Dann auf **Weitere Informationen** und
   **Trotzdem ausführen** klicken.
3. Den Assistenten durchklicken (Deutsch oder Englisch). Ohne Adminrechte wird nur für den
   aktuellen Benutzer installiert (nach `%LOCALAPPDATA%\Programs\Miksan-Converter`); mit
   Adminrechten wahlweise für alle Benutzer (nach `C:\Program Files\Miksan-Converter`).
   Optional:
   - **Desktop-Verknüpfung**
   - **Kommandozeile „miksan“ zum PATH hinzufügen** (Standard: aus) – danach funktioniert
     `miksan convert …` in jeder neuen Eingabeaufforderung bzw. PowerShell.

Der Installer enthält die Oberfläche, die Kommandozeile und alle Extras (SVG, Kamera-RAW,
Hintergrund entfernen). Python wird nicht gebraucht.

## Starten

- **Oberfläche:** Startmenü → *Miksan-Converter* (siehe [oberflaeche.md](oberflaeche.md))
- **Kommandozeile:** `miksan.exe` im Programmordner, bzw. `miksan`, wenn der PATH-Eintrag
  gewählt wurde (siehe [bedienung.md](bedienung.md))

## Rechtsklick-Menü und nur ein Fenster

Bei der Installation ist die Aufgabe **„Im Explorer-Rechtsklick-Menü anzeigen“** angehakt: Bilder,
PDFs, Videos, Tondateien und Ordner haben dann den Eintrag **„Mit Miksan-Converter öffnen“**
(unter Windows 11 unter „Weitere Optionen anzeigen“). Die Einträge stehen unter
`Software\Classes\SystemFileAssociations\<endung>\shell\MiksanConverter` (bzw.
`Directory\shell` für Ordner), ändern keine Standardprogramme und werden beim Deinstallieren
entfernt. Ein zweiter Start öffnet kein zweites Fenster: die Dateien gehen an das laufende.
Still installieren ohne Rechtsklick-Menü: `/TASKS=` ohne `kontextmenue`.

## Hintergrund entfernen

Das Standardmodell **„klein“** (`u2netp`, ca. 5 MB) ist im Installer enthalten: Hintergrund
entfernen funktioniert direkt nach der Installation **ohne Internet**. Beim ersten Gebrauch wird
es nach `%LOCALAPPDATA%\miksan-converter\modelle` kopiert. Das Modell steht unter der
Apache-Lizenz 2.0 (U²-Net); Lizenztext und Herkunft liegen im Programmordner unter
`_internal\miksan_modelle\` (`U-2-Net-LICENSE.txt`, `MODELLE.txt`).

Die grösseren Modelle („genau“, „person“, „sehr genau“) sind nicht enthalten (der Installer
wäre sonst viel grösser). Sie werden im Programm auf der Seite „Hintergrund entfernen“ über den
Knopf **Herunterladen** einmalig geladen und danach offline genutzt.

## Video und Audio

Der Installer enthält das Programm **ffmpeg** (aus `imageio-ffmpeg`), damit Video und Audio
sofort funktionieren. Dieses ffmpeg steht unter der **GPL-3.0**; Lizenztext und Hinweise zum
Quelltext liegen im Programmordner unter `lizenzen\` (`FFMPEG.txt`,
`FFMPEG-COPYING.GPLv3.txt`). Miksan-Converter startet ffmpeg nur als eigenes Programm, der
eigene Code bleibt MIT. Ein anderes ffmpeg lässt sich unter Einstellungen → Video & Audio
angeben. Details in [video-audio.md](video-audio.md).

## Aktualisieren

Einfach den neuen Installer ausführen; er ersetzt die vorhandene Installation. Einstellungen und
Modelle bleiben erhalten.

Beim Bauen lädt `packaging/windows/bauen.py` das kleine Modell einmal nach `build/modelle/`
(Prüfsumme wird geprüft) und legt die Lizenztexte aus `packaging/windows/lizenzen/` dazu;
`--ohne-modell` baut ohne Modell.

## Deinstallieren

Über **Einstellungen → Apps → Installierte Apps** (bzw. „Apps & Features“) →
*Miksan-Converter* → *Deinstallieren*. Entfernt werden Programmordner, Startmenü- und
Desktop-Verknüpfung, PATH-Eintrag, gespeicherte Einstellungen und der Cache. Die
heruntergeladenen KI-Modelle werden nur gelöscht, wenn man die Nachfrage mit **Ja**
beantwortet.

Installer selbst bauen: siehe [packaging/windows/README.md](../packaging/windows/README.md).

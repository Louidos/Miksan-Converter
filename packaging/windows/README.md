# Windows-Installer bauen

Hier liegt alles, was aus Miksan-Converter einen Windows-Installer
(`MiksanConverter-Setup-X.Y.Z.exe`) macht. Für Nutzer: siehe [docs/installer.md](../../docs/installer.md).

| Datei | Zweck |
|---|---|
| `miksan.spec` | PyInstaller (onedir): `Miksan-Converter.exe` (Oberfläche, ohne Konsole) und `miksan.exe` (Kommandozeile) im selben Ordner, alle Extras |
| `start_gui.py`, `start_cli.py`, `_laufzeit.py` | Startskripte der beiden Programme |
| `installer.iss` | Inno-Setup-Skript (Deutsch/Englisch, ohne Adminrechte möglich) |
| `miksan.ico` | Programm-Icon (16–256 px), erzeugt mit `icon_erzeugen.py` |
| `icon_erzeugen.py` | zeichnet das Icon neu (auch `src/miksan_converter/gui/miksan.png`) |
| `bauen.py` | baut alles mit einem Befehl |

## Lokal bauen (Windows)

Voraussetzungen: [uv](https://docs.astral.sh/uv/) und [Inno Setup 6](https://jrsoftware.org/isdl.php)
(z. B. `choco install innosetup`).

```powershell
uv sync --locked --extra gui --extra svg --extra raw --extra ki --group installer
uv run python packaging/windows/bauen.py
```

Ergebnis: `dist\MiksanConverter-Setup-X.Y.Z.exe`. Zwischenstände liegen in `build\`
(`build\programm\Miksan-Converter\` ist das fertige Programm ohne Installer). `build\` und
`dist\` sind in `.gitignore`.

Optionen von `bauen.py`:

- `--nur-programm` – nur PyInstaller, kein Installer (geht auch unter Linux/macOS, z. B. um
  versteckte Importe zu prüfen)
- `--iscc PFAD` – Pfad zu `ISCC.exe`, falls Inno Setup nicht gefunden wird

Die Version kommt aus `pyproject.toml` (und muss mit `src/miksan_converter/__init__.py`
übereinstimmen); sie wird nirgends von Hand eingetragen.

## Prüfen

```powershell
build\programm\Miksan-Converter\miksan.exe --version
build\programm\Miksan-Converter\Miksan-Converter.exe --selbsttest bericht.txt
```

`--selbsttest` (versteckt) lädt alle Extras, öffnet das Fenster ohne Bildschirm, wandelt ein
Testbild um und endet mit Code 0, wenn alles klappt. Der Bericht steht in `bericht.txt`.

## Automatisch (GitHub Actions)

`.github/workflows/windows-installer.yml` baut den Installer auf `windows-latest`

- bei Pull Requests, die `packaging/**`, `pyproject.toml`, `uv.lock` oder `src/**` ändern
  (Installer als Workflow-Artefakt),
- von Hand („Run workflow“),
- bei jedem veröffentlichten Release – dann wird der Installer an das Release angehängt.

Jedes Mal läuft ein Rauchtest: still installieren (`/VERYSILENT /SUPPRESSMSGBOXES /CURRENTUSER`),
`miksan.exe --version`, ein Testbild nach JPG, HEIC und WebP umwandeln, Hintergrund entfernen
(lädt das kleine Modell), `Miksan-Converter.exe --selbsttest`, still deinstallieren und prüfen,
dass Programmordner und PATH-Eintrag weg sind und die Modelle bleiben.

## Hinweise

- **onedir statt onefile:** startet schneller, und die Qt-Bibliotheken bleiben eigene DLLs
  (LGPL: sie können ersetzt werden).
- **KI-Modelle** sind nicht eingepackt; sie werden beim ersten Gebrauch nach
  `%LOCALAPPDATA%\miksan-converter\modelle` geladen.
- **numba** (über rembg → pymatting) braucht die Quelltexte von pymatting und einen
  beschreibbaren Cache; deshalb `module_collection_mode={"pymatting": "py"}` in der Spec und
  `NUMBA_CACHE_DIR` in `_laufzeit.py` (`%LOCALAPPDATA%\miksan-converter\cache`).
- **Keine Code-Signatur:** Windows SmartScreen warnt beim ersten Start.

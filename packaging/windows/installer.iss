; Inno-Setup-Skript für Miksan-Converter.
;
; Wird von packaging/windows/bauen.py aufgerufen:
;   iscc /DAppVersion=X.Y.Z /DQuelle=<build\programm\Miksan-Converter> /DRepo=<Repo> /O<dist> installer.iss
; Die Version kommt aus pyproject.toml und wird nie von Hand eingetragen.

#ifndef AppVersion
  #error AppVersion fehlt – bitte über bauen.py bauen (liest die Version aus pyproject.toml)
#endif
#ifndef Quelle
  #define Quelle "..\..\build\programm\Miksan-Converter"
#endif
#ifndef Repo
  #define Repo "..\.."
#endif

#define AppName "Miksan-Converter"
#define AppExe "Miksan-Converter.exe"
#define CliExe "miksan.exe"

[Setup]
; Feste ID: Updates ersetzen die vorhandene Installation, statt eine zweite anzulegen
AppId={{6E1F3C2A-8B4D-4F6A-9C1E-2D7B5A9E4F10}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Louidos
AppPublisherURL=https://github.com/Louidos/Miksan-Converter
AppSupportURL=https://github.com/Louidos/Miksan-Converter/issues
AppUpdatesURL=https://github.com/Louidos/Miksan-Converter/releases
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Ohne Adminrechte installierbar (nur für den aktuellen Benutzer); im Dialog wählbar
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile={#Repo}\LICENSE
SetupIconFile=miksan.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
OutputBaseFilename=MiksanConverter-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesEnvironment=yes
CloseApplications=yes

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
de.PfadAufgabe=Kommandozeile „miksan“ zum PATH hinzufügen
en.PfadAufgabe=Add the "miksan" command line tool to PATH
de.Zusatz=Zusätzlich:
en.Zusatz=Additional options:
de.ModelleLoeschen=Sollen auch die heruntergeladenen KI-Modelle gelöscht werden?%n%n%1%n%nBei „Nein“ bleiben sie für eine spätere Installation erhalten.
en.ModelleLoeschen=Do you also want to delete the downloaded AI models?%n%n%1%n%nChoose "No" to keep them for a later installation.
de.KommandozeileName=Miksan-Converter (Kommandozeile)
en.KommandozeileName=Miksan-Converter (command line)

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "pfad"; Description: "{cm:PfadAufgabe}"; GroupDescription: "{cm:Zusatz}"; Flags: unchecked

[Files]
Source: "{#Quelle}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Dateien, die zur Laufzeit im Programmordner entstehen können
Type: filesandordirs; Name: "{app}"

[Code]
const
  UmgebungBenutzer = 'Environment';
  UmgebungSystem = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';

function UmgebungWurzel: Integer;
begin
  if IsAdminInstallMode then
    Result := HKEY_LOCAL_MACHINE
  else
    Result := HKEY_CURRENT_USER;
end;

function UmgebungSchluessel: String;
begin
  if IsAdminInstallMode then
    Result := UmgebungSystem
  else
    Result := UmgebungBenutzer;
end;

{ Liefert die Position von Ordner in Pfad (mit ; umschlossen), 0 = nicht enthalten }
function PfadPosition(const Pfad, Ordner: String): Integer;
begin
  Result := Pos(';' + Uppercase(Ordner) + ';', ';' + Uppercase(Pfad) + ';');
end;

procedure PfadHinzufuegen(const Ordner: String);
var
  Pfad: String;
begin
  if not RegQueryStringValue(UmgebungWurzel, UmgebungSchluessel, 'Path', Pfad) then
    Pfad := '';
  if PfadPosition(Pfad, Ordner) > 0 then
    exit;
  if (Pfad <> '') and (Copy(Pfad, Length(Pfad), 1) <> ';') then
    Pfad := Pfad + ';';
  RegWriteExpandStringValue(UmgebungWurzel, UmgebungSchluessel, 'Path', Pfad + Ordner);
end;

procedure PfadEntfernen(const Ordner: String);
var
  Pfad: String;
  Stelle: Integer;
begin
  if not RegQueryStringValue(UmgebungWurzel, UmgebungSchluessel, 'Path', Pfad) then
    exit;
  Stelle := PfadPosition(Pfad, Ordner);
  if Stelle = 0 then
    exit;
  { ';' + Pfad + ';' -> den Eintrag samt einem Trennzeichen herausschneiden }
  Pfad := ';' + Pfad + ';';
  Delete(Pfad, Stelle, Length(Ordner) + 1);
  { die zusätzlichen Trennzeichen am Anfang und Ende wieder entfernen }
  if Copy(Pfad, 1, 1) = ';' then
    Delete(Pfad, 1, 1);
  if Copy(Pfad, Length(Pfad), 1) = ';' then
    Delete(Pfad, Length(Pfad), 1);
  RegWriteExpandStringValue(UmgebungWurzel, UmgebungSchluessel, 'Path', Pfad);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('pfad') then
    PfadHinzufuegen(ExpandConstant('{app}'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Daten, Modelle: String;
begin
  if CurUninstallStep <> usPostUninstall then
    exit;
  PfadEntfernen(ExpandConstant('{app}'));
  { gespeicherte Einstellungen des Fensters (QSettings) }
  RegDeleteKeyIncludingSubkeys(HKEY_CURRENT_USER, 'Software\Miksan\Miksan-Converter');
  RegDeleteKeyIfEmpty(HKEY_CURRENT_USER, 'Software\Miksan');
  { Cache (z. B. numba) immer löschen, Modelle nur auf Nachfrage }
  Daten := ExpandConstant('{localappdata}\miksan-converter');
  DelTree(Daten + '\cache', True, True, True);
  Modelle := Daten + '\modelle';
  if DirExists(Modelle) then
    if SuppressibleMsgBox(FmtMessage(CustomMessage('ModelleLoeschen'), [Modelle]),
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
      DelTree(Modelle, True, True, True);
  RemoveDir(Daten);
end;

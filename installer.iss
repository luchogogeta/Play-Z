; Instalador de Reproductor (Inno Setup).
;
; Instala en la carpeta del usuario actual (%LocalAppData%\Programs\Reproductor)
; para no requerir permisos de administrador, con acceso directo en el menú
; inicio y, opcionalmente, en el escritorio, más un desinstalador normal
; (aparece en "Agregar o quitar programas").
;
; Requiere haber generado antes dist\Reproductor\ con:
;   pyinstaller Reproductor.spec

#define MyAppName "Reproductor"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "luchogogeta"
#define MyAppExeName "Reproductor.exe"

[Setup]
AppId={{B6E1B2E2-2F3B-4B7D-9C1A-2E6F6E6C4F1A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=Instalar-Reproductor
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\Reproductor\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

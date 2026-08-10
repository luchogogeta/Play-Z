; Instalador de Play-Z (Inno Setup).
;
; Instala en la carpeta del usuario actual (%LocalAppData%\Programs\Play-Z)
; para no requerir permisos de administrador, con acceso directo en el menú
; inicio y, opcionalmente, en el escritorio, más un desinstalador normal
; (aparece en "Agregar o quitar programas").
;
; Requiere haber generado antes dist\Play-Z\ con:
;   pyinstaller Play-Z.spec

#define MyAppName "Play-Z"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "luchogogeta"
#define MyAppExeName "Play-Z.exe"

[Setup]
AppId={{ABC4ED89-DE0A-45C4-A62E-C860444F9082}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=Instalar-Play-Z
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
Source: "dist\Play-Z\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

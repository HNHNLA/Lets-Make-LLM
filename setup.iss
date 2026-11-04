; Inno Setup 6 script for LML 1.0.0-alpha
; Build from the project root after creating dist\lml\lml.exe.

#define AppName "LML"
#define AppVersion "1.0.0-alpha"
#define AppPublisher "nether1082"
#define AppExeName "lml.exe"

[Setup]
AppId={{B2D7A8F1-9C34-4E61-A5F0-1C7D9B3E2A60}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=LML-{#AppVersion}-Setup
UninstallDisplayName={#AppName}
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\lml\lml.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "lml_persona.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\LML"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\LML"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch LML"; Flags: postinstall nowait skipifsilent

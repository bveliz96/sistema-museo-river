#define MyAppName "Sistema Museo River"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "Sistema Museo River"
#define MyAppExeName "SistemaMuseoRiver.exe"

[Setup]
AppId={{8E5E13A0-2A62-4E08-B44B-9BCE0D4573CC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={autopf}\Sistema Museo River
DefaultGroupName=Sistema Museo River

DisableProgramGroupPage=yes
PrivilegesRequired=admin

ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

OutputDir=instalador
OutputBaseFilename=Instalador_Sistema_Museo_River_{#MyAppVersion}

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

UninstallDisplayIcon={app}\{#MyAppExeName}

CloseApplications=yes
RestartApplications=no

VersionInfoVersion=1.2.0.0
VersionInfoDescription=Instalador del Sistema Museo River
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}


[Languages]

Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"


[Tasks]

Name: "desktopicon"; \
    Description: "Crear un acceso directo en el escritorio"; \
    GroupDescription: "Accesos directos:"; \
    Flags: unchecked


[Files]

Source: "dist\SistemaMuseoRiverFinal\SistemaMuseoRiver.exe"; \
    DestDir: "{app}"; \
    Flags: ignoreversion

Source: "dist\SistemaMuseoRiverFinal\servidor.exe"; \
    DestDir: "{app}"; \
    Flags: ignoreversion


[Dirs]

Name: "{commonappdata}\SistemaMuseoRiver"; \
    Permissions: users-modify; \
    Flags: uninsneveruninstall

Name: "{commonappdata}\SistemaMuseoRiver\database"; \
    Permissions: users-modify; \
    Flags: uninsneveruninstall

Name: "{commonappdata}\SistemaMuseoRiver\backups"; \
    Permissions: users-modify; \
    Flags: uninsneveruninstall

Name: "{commonappdata}\SistemaMuseoRiver\logs"; \
    Permissions: users-modify; \
    Flags: uninsneveruninstall

Name: "{commonappdata}\SistemaMuseoRiver\config"; \
    Permissions: users-modify; \
    Flags: uninsneveruninstall


[Icons]

Name: "{group}\Sistema Museo River"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"

Name: "{commondesktop}\Sistema Museo River"; \
    Filename: "{app}\{#MyAppExeName}"; \
    WorkingDir: "{app}"; \
    Tasks: desktopicon


[Run]

Filename: "{app}\{#MyAppExeName}"; \
    Description: "Abrir el panel del Sistema Museo River"; \
    WorkingDir: "{app}"; \
    Flags: nowait postinstall skipifsilent
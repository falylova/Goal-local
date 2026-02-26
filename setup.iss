[Setup]
AppName=Yetilogs
AppVersion=2.0
DefaultDirName={pf}\Yetilogs
DefaultGroupName=Yetilogs
OutputBaseFilename=Yetilogs
OutputDir=output
SetupIconFile=assets\batterie.ico
UninstallDisplayIcon={app}\version2.exe
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\CD.exe"; DestDir: "{app}"
Source: "dist\version2.exe"; DestDir: "{app}"
Source: "assets\batterie.ico"; DestDir: "{app}"

[Icons]
Name: "{group}\Yeti"; Filename: "{app}\version2.exe"; IconFilename: "{app}\batterie.ico"
Name: "{commondesktop}\Yeti"; Filename: "{app}\version2.exe"; IconFilename: "{app}\batterie.ico"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: Créer une icône sur le bureau

[Run]
Filename: "{app}\CD.exe"; Flags: nowait runhidden

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
ValueType: string; ValueName: "MonLogiciel"; ValueData: """{app}\CD.exe"""; Flags: uninsdeletevalue

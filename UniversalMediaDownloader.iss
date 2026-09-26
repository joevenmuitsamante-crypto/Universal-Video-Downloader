#define MyAppName "Universal Media Downloader"
#ifndef MyAppVersion
#define MyAppVersion "4.3.0"
#endif
#define MyAppPublisher "Universal Media Downloader"
#define MyAppExeName "UniversalMediaDownloader.exe"

[Setup]
AppId={{7D6B0A3A-5E88-4F1E-9A7E-420260000001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Universal Media Downloader
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=UniversalMediaDownloader_Setup_v{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=UniversalMediaDownloader.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Dirs]
Name: "{localappdata}\UniversalMediaDownloader"; Attribs: hidden
Name: "{localappdata}\UniversalMediaDownloader\bin"; Attribs: hidden

[Files]
Source: "dist\UniversalMediaDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "build\components\yt-dlp.exe"; DestDir: "{localappdata}\UniversalMediaDownloader\bin"; Flags: ignoreversion
Source: "build\components\ffmpeg.exe"; DestDir: "{localappdata}\UniversalMediaDownloader\bin"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{localappdata}\UniversalMediaDownloader\bin"
Type: filesandordirs; Name: "{localappdata}\UniversalMediaDownloader"

[Setup]
AppName=MyWindowsApp
AppVersion=1.0.0
DefaultDirName={autopf}\MyWindowsApp
DefaultGroupName=MyWindowsApp
OutputDir=Output
OutputBaseFilename=MyWindowsAppSetup
Compression=lzma
SolidCompression=yes

[Files]
; Update the Source path to match your Node compilation output (e.g., dist\MyWindowsApp.exe)
Source: "dist\MyWindowsApp.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\MyWindowsApp"; Filename: "{app}\MyWindowsApp.exe"
Name: "{autodesktop}\MyWindowsApp"; Filename: "{app}\MyWindowsApp.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

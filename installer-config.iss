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
Source: "MatixTheMathClub\publish\MatixTheMathClub.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "MatixTheMathClub\publish\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs


[Icons]
Name: "{group}\MyWindowsApp"; Filename: "{app}\MyWindowsApp.exe"
Name: "{autodesktop}\MyWindowsApp"; Filename: "{app}\MyWindowsApp.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

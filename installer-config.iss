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
Name: "{group}\Matix The Math Club"; Filename: "{app}\MatixTheMathClub.exe"
Name: "{autodesktop}\Matix The Math Club"; Filename: "{app}\MatixTheMathClub.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MatixTheMathClub.exe"; Description: "{cm:LaunchProgram,Matix The Math Club}"; Flags: nowait postinstall skipifsilent


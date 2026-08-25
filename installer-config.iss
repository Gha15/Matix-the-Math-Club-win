[Setup]
AppName=Matix The Math Club
AppVersion=1.0.0
DefaultDirName={autopf}\MatixTheMathClub
DefaultGroupName=Matix The Math Club
UninstallDisplayIcon={app}\MatixTheMathClub.exe
Compression=lzma2
SolidCompression=yes
OutputDir=Output
OutputBaseFilename=MatixMathClubSetup

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "MatixTheMathClub\publish\MatixTheMathClub.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "MatixTheMathClub\publish\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Matix The Math Club"; Filename: "{app}\MatixTheMathClub.exe"
Name: "{autodesktop}\Matix The Math Club"; Filename: "{app}\MatixTheMathClub.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MatixTheMathClub.exe"; Description: "{cm:LaunchProgram,Matix The Math Club}"; Flags: nowait postinstall skipifsilent

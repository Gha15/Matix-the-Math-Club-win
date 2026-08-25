[Setup]
AppName=Matix The Math Club
AppVersion=1.0.0
DefaultDirName={autopf}\MatixTheMathClub
DefaultGroupName=Matix The Math Club
UninstallDisplayIcon={app}\MatixTheMathClub-Win.exe
OutputDir=Output
OutputBaseFilename=MatixMathClubSetup

; --- EXTREME COMPRESSION PRESETS ---
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumFastBytes=273
; ------------------------------------

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "publish\MatixTheMathClub-Win.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "publish\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Matix The Math Club"; Filename: "{app}\MatixTheMathClub-Win.exe"
Name: "{autodesktop}\Matix The Math Club"; Filename: "{app}\MatixTheMathClub-Win.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MatixTheMathClub-Win.exe"; Description: "{cm:LaunchProgram,Matix The Math Club}"; Flags: nowait postinstall skipifsilent

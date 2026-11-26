#define MyAppName "SwimRocket Встречи"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "SwimRocket"
#define MyAppExeName "SwimRocketMeetings.exe"

[Setup]
AppId={{7A5E3A11-5B8B-4B3A-9D4F-123456789ABC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\SwimRocket Встречи
DefaultGroupName=SwimRocket Встречи
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename=SwimRocketMeetings-Setup
SetupIconFile=resources\swimrocket.ico
UninstallDisplayIcon={app}\SwimRocketMeetings.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
Source: "dist\SwimRocketMeetings\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\SwimRocket Встречи"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\resources\swimrocket.ico"
Name: "{group}\SwimRocket Встречи"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\resources\swimrocket.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить SwimRocket Встречи"; Flags: nowait postinstall skipifsilent

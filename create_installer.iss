; Inno Setup Script for Unified Parser
; Creates a professional Windows installer

[Setup]
AppName=Unified Parser
AppVersion=1.0
AppPublisher=Unified Parser Team
AppContact=support@example.com
DefaultDirName={pf}\UnifiedParser
DefaultGroupName=Unified Parser
OutputDir=installer_output
OutputBaseFilename=UnifiedParser_Setup
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Languages\English.isl"

[Files]
; Main application folder
Source: "export\Unified_Parser\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Unified Parser"; Filename: "{app}\Unified_Parser.exe"
Name: "{commondesktop}\Unified Parser"; Filename: "{app}\Unified_Parser.exe"
Name: "{group}\{cm:UninstallProgram,Unified Parser}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\Unified_Parser.exe"; Description: "{cm:LaunchProgram,Unified Parser}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  
  // Check if Python is NOT installed (we don't need it, but inform user)
  // This is just informational - our app works without Python
  
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Create cache directory for Playwright browsers
    ForceDirectories(ExpandConstant('{userappdata}') + '\..\.cache\ms-playwright');
  end;
end;

[Messages]
WelcomeLabel1=Добро пожаловать в мастер установки Unified Parser!
WelcomeLabel2=Это установит Unified Parser на ваш компьютер.%n%nВерсия: 1.0%n%nРекомендуется закрыть все работающие приложения перед установкой.
SetupWindowTitle=Установка Unified Parser
SelectDirLabel3=Установка будет выполнена в следующую папку:
SelectDirBrowseLabel=Выберите папку для установки Unified Parser:
ReadyLabel1=Готов к установке Unified Parser на ваш компьютер.
ReadyLabel2a=Unified Parser будет установлен в следующую папку:
ReadyLabel2b=%n%nНажмите Установить для продолжения.
FinishedHeadingLabel=Установка Unified Parser завершена!
RunEntryText=Запустить Unified Parser

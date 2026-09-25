; Status Pet installer (Inno Setup). Built by tools/build_installer.py, which passes AppVersion,
; first builds the app folder with PyInstaller into build\dist\Status Pet and the pictures into build\art
; (tools/make_setup_art.py).
; Per-user install: no admin rights needed. Settings live in %LOCALAPPDATA%\Status Pet and are kept on uninstall.

#ifndef AppVersion
  #define AppVersion "1.0.1"
#endif
#define AppName "Status Pet"
#define AppExe "Status Pet.exe"

[Setup]
AppId={{6F1C2A4E-8B3D-4F7A-9C55-5A7E2D9B31C4}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=no
DisableWelcomePage=no
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=StatusPet-Setup-{#AppVersion}
SetupIconFile=..\src\assets\app_icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
WizardImageFile=..\build\art\side_welcome.bmp,..\build\art\side_welcome@2x.bmp
WizardSmallImageFile=..\build\art\badge.bmp,..\build\art\badge@2x.bmp
WizardImageStretch=no
; the language follows Windows (Korean Windows -> Korean), no language question
ShowLanguageDialog=no
Compression=lzma2
SolidCompression=yes
; the app's single-instance lock: Setup asks to close a running Status Pet first
AppMutex=Local\StatusPet.SingleInstance

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "ko"; MessagesFile: "compiler:Languages\Korean.isl"

[Messages]
en.WelcomeLabel1=Hi! Let's bring your pet home.
en.WelcomeLabel2=Status Pet is a little pixel pet that lives on your desktop. It walks around, naps when your PC is quiet, and gets busy (magic, painting, cooking...) when your PC works hard.%n%nThis will install Status Pet.
en.ClickNext=Click Next to continue.
en.WizardSelectTasks=A few choices
en.SelectTasksDesc=You can change these later in Settings.
en.SelectTasksLabel2=Pick what you like, then click Install.
en.WizardInstalling=Moving your pet in...
en.InstallingLabel=Packing snacks, hats and a tiny wand.
en.FinishedHeadingLabel=All set! Your pet is home.
en.FinishedLabelNoIcons=Look for it on your desktop. Right-click the pet for the menu, or point at it and click the gear for Settings.
en.FinishedLabel=Look for it on your desktop. Right-click the pet for the menu, or point at it and click the gear for Settings.
en.ClickFinish=Click Finish to close Setup.
ko.WelcomeLabel1=안녕하세요! 펫을 집으로 데려올게요.
ko.WelcomeLabel2=Status Pet은 바탕화면에 사는 작은 픽셀 펫입니다. 돌아다니다가 PC가 한가하면 낮잠을 자고, PC가 바쁘면 같이 바빠집니다 (마법, 그림, 요리...).%n%nStatus Pet을 설치합니다.
ko.ClickNext=계속하려면 [다음]을 클릭하세요.
ko.WizardSelectTasks=몇 가지 선택
ko.SelectTasksDesc=나중에 설정에서 바꿀 수 있습니다.
ko.SelectTasksLabel2=원하는 항목을 고른 뒤 [설치]를 클릭하세요.
ko.WizardInstalling=펫 이사 중...
ko.InstallingLabel=간식, 모자, 작은 지팡이 챙기는 중.
ko.FinishedHeadingLabel=완료! 펫이 집에 도착했어요.
ko.FinishedLabelNoIcons=바탕화면에서 찾아보세요. 펫을 오른쪽 클릭하면 메뉴, 펫을 가리키고 톱니바퀴를 클릭하면 설정이 열립니다.
ko.FinishedLabel=바탕화면에서 찾아보세요. 펫을 오른쪽 클릭하면 메뉴, 펫을 가리키고 톱니바퀴를 클릭하면 설정이 열립니다.
ko.ClickFinish=설치를 마치려면 [마침]을 클릭하세요.

[CustomMessages]
en.DeskIcon=Put a Status Pet shortcut on the desktop
en.ShortcutsGroup=Shortcuts:
en.StartupTask=Wake up my pet when Windows starts
en.StartupGroup=Startup:
en.RunNow=Say hello now (start Status Pet)
ko.DeskIcon=바탕화면에 Status Pet 바로가기 만들기
ko.ShortcutsGroup=바로가기:
ko.StartupTask=Windows 시작 시 펫 깨우기
ko.StartupGroup=시작:
ko.RunNow=지금 인사하기 (Status Pet 실행)

[Tasks]
Name: "desktopicon"; Description: "{cm:DeskIcon}"; GroupDescription: "{cm:ShortcutsGroup}"
Name: "startup"; Description: "{cm:StartupTask}"; GroupDescription: "{cm:StartupGroup}"; Flags: unchecked

[Files]
Source: "..\build\dist\{#AppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\build\art\*.bmp"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; same value the app's General tab "Start with Windows" switch uses (autostart.py)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExe}"""; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:RunNow}"; Flags: nowait postinstall skipifsilent

[Code]
{ The installing page uses Windows' own progress bar. }
var
  Big: Boolean;             { 150% Windows scaling or more: use the @2x pictures }

function Art(Name: String): String;
begin
  if Big then
    Name := Name + '@2x';
  ExtractTemporaryFile(Name + '.bmp');
  Result := ExpandConstant('{tmp}\' + Name + '.bmp');
end;

procedure InitializeWizard;
begin
  Big := ScaleX(100) >= 150;
  WizardForm.WizardBitmapImage2.Bitmap.LoadFromFile(Art('side_finish'));   { Finish: happy pet + hearts }
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpInstalling then
    WizardForm.WizardSmallBitmapImage.Bitmap.LoadFromFile(Art('badge_focused'));
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  { the switch may have been turned on inside the app, so remove the startup entry either way }
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', '{#AppName}');
end;

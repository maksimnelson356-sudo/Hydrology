; ============================================================
; HydroSphere — Windows Installer (Inno Setup 6+)
; ============================================================
; Скрипт для Inno Setup Compiler
; Скачать: https://jrsoftware.org/isinfo.php
;
; Для сборки:
;   1. Собрать PyInstaller: python build.py
;   2. Запустить Inno Setup Compiler → открыть этот файл
;   3. Или: iscc.exe hydrosphere_installer.iss
; ============================================================

#define MyAppName "HydroSphere"
#define MyAppNameRU "HydroSphere"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "HydroSphere Team"
#define MyAppURL "https://hydrosphere.app"
#define MyAppExeName "HydroSphere.exe"
#define MyAppDescription "Платформа гидрологической статистики"
#define MyAppCopyright "© 2026 HydroSphere"

; Пути к файлам (после сборки PyInstaller)
#define SourceDir "..\dist\HydroSphere"
#define IconFile "..\icon.ico"

; ============================================================
[Setup]
; AppId — уникальный идентификатор (никогда не менять!)
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVerName={#MyAppName}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
AppCopyright={#MyAppCopyright}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\installer_output
OutputBaseFilename=HydroSphere_Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=120
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

; Внешний вид
; WizardImageFile=installer_wizard.bmp
; WizardSmallFile=installer_logo.bmp

; Язык
LanguageDetectionMethod=uilanguage
ShowLanguageDialog=yes

; Регистрация
CreateAppDir=yes
UsePreviousAppDir=yes
AllowNoIcons=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: checkedonce
Name: "startmenuicon"; Description: "Создать ярлык в меню «Пуск»"; GroupDescription: "Дополнительные ярлыки:"; Flags: checkedonce
Name: "associatehsp"; Description: "Ассоциировать файлы .hsp с {#MyAppName}"; GroupDescription: "Файлы:"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "Создать ярлык в панели быстрого запуска"; GroupDescription: "Дополнительные ярлыки:"; Flags: unchecked

[Files]
; Копируем всё из папки PyInstaller
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Иконка приложения
Source: "{#IconFile}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Группа программ
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"
Name: "{group}\Удалить {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{group}\README"; Filename: "{app}\README.txt"; AfterInstall: CreateReadme

; Рабочий стол
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "{#MyAppDescription}"

; Быстрый запуск
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

; Папка запуска
Name: "{userprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startmenuicon

[Run]
; Запуск после установки
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить {#MyAppName}"; Flags: nowait postinstall skipifsilent
Filename: "https://hydrosphere.app/docs"; Description: "Открыть документацию"; Flags: postinstall skipifsilent shellexec

[Registry]
; Ассоциация файлов .hsp
Root: HKA; Subkey: "Software\Classes\.hsp\OpenWithProgids"; ValueType: string; ValueName: "HydroSphere.hsp"; ValueData: ""; Flags: uninsdeletevalue; Tasks: associatehsp
Root: HKA; Subkey: "Software\Classes\.hsp"; ValueType: string; ValueName: ""; ValueData: "HydroSphere.hsp"; Flags: uninsdeletekey; Tasks: associatehsp
Root: HKA; Subkey: "Software\Classes\HydroSphere.hsp"; ValueType: string; ValueName: ""; ValueData: "Проект HydroSphere"; Flags: uninsdeletekey; Tasks: associatehsp
Root: HKA; Subkey: "Software\Classes\HydroSphere.hsp\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"; Tasks: associatehsp
Root: HKA; Subkey: "Software\Classes\HydroSphere.hsp\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: associatehsp

; Путь для автообновлений
Root: HKA; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletevalue

[Code]
// Проверка: запущено ли приложение перед установкой
function InitializeSetup(): Boolean;
begin
  Result := True;
end;

// Создание README.txt
procedure CreateReadme;
var
  Filename: String;
  Content: String;
begin
  Filename := ExpandConstant('{app}\README.txt');
  Content := '=== HydroSphere ===' + #13#10 +
    'Платформа гидрологической статистики' + #13#10 + #13#10 +
    'Системные требования:' + #13#10 +
    '  - Windows 10/11 (64-bit)' + #13#10 +
    '  - 4 GB RAM' + #13#10 +
    '  - 500 MB свободного места на диске' + #13#10 + #13#10 +
    'Документация: https://hydrosphere.app/docs' + #13#10 +
    'Поддержка: https://hydrosphere.app/support' + #13#10 + #13#10 +
    '(C) 2026 HydroSphere Team';
  SaveStringToFile(Filename, Content, False);
end;

// Удаление при обновлении (обновление на месте)
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Успешная установка
  end;
end;

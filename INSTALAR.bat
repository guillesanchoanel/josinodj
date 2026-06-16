@echo off
setlocal EnableDelayedExpansion
title JOSINODJ - Instalador

:: Comprobar si se ejecuta como Administrador
net session >nul 2>&1
if errorlevel 1 (
    echo Solicitando permisos de administrador...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

set "SRC=%~dp0"
set "DEST=%ProgramFiles%\JOSINODJ"
set VERSION=2.2.0

echo.
echo  ============================
echo    Instalando JOSINODJ...
echo  ============================
echo.
echo  Destino: %DEST%
echo.

:: Copiar archivos
echo  Copiando archivos...
if not exist "%DEST%" mkdir "%DEST%"
xcopy /E /Y /Q "%SRC%*" "%DEST%\" >nul
if errorlevel 1 (
    echo  ERROR al copiar archivos.
    pause
    exit /b 1
)

:: Acceso directo en Escritorio
echo  Creando acceso directo en el Escritorio...
powershell -NoProfile -Command ^
  "$s = (New-Object -COM WScript.Shell).CreateShortcut([Environment]::GetFolderPath('CommonDesktopDirectory') + '\JOSINODJ.lnk'); " ^
  "$s.TargetPath = '%DEST%\JOSINODJ.exe'; " ^
  "$s.WorkingDirectory = '%DEST%'; " ^
  "$s.Description = 'JOSINODJ - DJ Software'; " ^
  "$s.Save()"

:: Acceso directo en Menú Inicio
echo  Creando acceso en Menu Inicio...
set "START_MENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs\JOSINODJ"
if not exist "%START_MENU%" mkdir "%START_MENU%"
powershell -NoProfile -Command ^
  "$s = (New-Object -COM WScript.Shell).CreateShortcut('%START_MENU%\JOSINODJ.lnk'); " ^
  "$s.TargetPath = '%DEST%\JOSINODJ.exe'; " ^
  "$s.WorkingDirectory = '%DEST%'; " ^
  "$s.Description = 'JOSINODJ - DJ Software'; " ^
  "$s.Save()"

:: Registrar en "Agregar o quitar programas"
echo  Registrando en Windows...
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /v "DisplayName"      /t REG_SZ /d "JOSINODJ" /f >nul
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /v "DisplayVersion"   /t REG_SZ /d "%VERSION%" /f >nul
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /v "Publisher"        /t REG_SZ /d "JOSINODJ" /f >nul
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /v "InstallLocation"  /t REG_SZ /d "%DEST%" /f >nul
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /v "DisplayIcon"      /t REG_SZ /d "%DEST%\JOSINODJ.exe" /f >nul
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /v "UninstallString"  /t REG_SZ /d "C:\Windows\System32\cmd.exe /c \"\"%DEST%\DESINSTALAR.bat\"\"" /f >nul
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /v "NoModify"         /t REG_DWORD /d 1 /f >nul
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /v "NoRepair"         /t REG_DWORD /d 1 /f >nul
for /f %%i in ('powershell -NoProfile -Command "(Get-ChildItem \"%DEST%\" -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1KB -as [int]"') do reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /v "EstimatedSize" /t REG_DWORD /d %%i /f >nul

echo.
echo  ============================
echo    Instalacion completada
echo  ============================
echo.
echo  JOSINODJ instalado en: %DEST%
echo  Acceso directo creado en el Escritorio
echo  Disponible en el Menu Inicio
echo.

start "" "%DEST%\JOSINODJ.exe"

exit /b 0

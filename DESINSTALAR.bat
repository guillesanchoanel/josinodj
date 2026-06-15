@echo off
chcp 65001 > /dev/null
title JOSINODJ - Desinstalador

net session >/dev/null 2>&1
if errorlevel 1 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo  ============================
echo    Desinstalando JOSINODJ...
echo  ============================
echo.

taskkill /IM JOSINODJ.exe /F >/dev/null 2>&1

set "DEST=%ProgramFiles%\JOSINODJ"
if exist "%DEST%" (
    echo  Eliminando archivos...
    rd /s /q "%DEST%"
)

powershell -NoProfile -Command "Remove-Item ([Environment]::GetFolderPath('CommonDesktopDirectory') + '\JOSINODJ.lnk') -Force -ErrorAction SilentlyContinue"

set "START_MENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs\JOSINODJ"
if exist "%START_MENU%" rd /s /q "%START_MENU%"

reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /f >/dev/null 2>&1

echo.
echo  ============================
echo    Desinstalacion completada
echo  ============================
echo.
echo  JOSINODJ desinstalado. Tus listas y ajustes en %USERPROFILE%\.josinodj\ no han sido eliminados.
echo.
pause
exit /b 0

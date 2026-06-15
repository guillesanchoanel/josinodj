@echo off
chcp 65001 > nul
title JOSINODJ - Desinstalador

net session > nul 2>&1
if errorlevel 1 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

setlocal EnableDelayedExpansion

echo.
echo  ============================
echo    Desinstalando JOSINODJ...
echo  ============================
echo.

echo  Cerrando JOSINODJ...
taskkill /IM JOSINODJ.exe /F > nul 2>&1
timeout /t 2 /nobreak > nul

echo  Eliminando accesos directos...
powershell -NoProfile -Command "Remove-Item ([Environment]::GetFolderPath('CommonDesktopDirectory') + '\JOSINODJ.lnk') -Force -ErrorAction SilentlyContinue"
powershell -NoProfile -Command "Remove-Item ([Environment]::GetFolderPath('Desktop') + '\JOSINODJ.lnk') -Force -ErrorAction SilentlyContinue"

set "START_MENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs\JOSINODJ"
if exist "!START_MENU!" rd /s /q "!START_MENU!"

echo  Limpiando registro...
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /f > nul 2>&1

echo  Eliminando archivos de programa...
set "DEST=%ProgramFiles%\JOSINODJ"
set "DELSCRIPT=%TEMP%\josinodj_del.bat"
> "!DELSCRIPT!" (
    echo @echo off
    echo ping 127.0.0.1 -n 3 ^>nul
    echo rd /s /q "!DEST!"
    echo del "!DELSCRIPT!"
)
start /min "" "!DELSCRIPT!"

echo.
echo  ============================
echo    Desinstalacion completada
echo  ============================
echo.
echo  Tus listas en %USERPROFILE%\.josinodj\ NO han sido eliminadas.
echo.
pause
exit /b 0

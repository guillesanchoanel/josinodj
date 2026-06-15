@echo off
chcp 65001 > /dev/null
title JOSINODJ - Desinstalador

:: Sin /elevated: copiar a TEMP y relanzar como admin
if /i "%~1" == "/elevated" goto :desinstalar

copy /Y "%~f0" "%TEMP%\JOSINODJ_uninstall.bat" > /dev/null 2>&1
powershell -Command "Start-Process 'cmd.exe' -ArgumentList '/c \"\"%TEMP%\JOSINODJ_uninstall.bat\"\" /elevated' -Verb RunAs -Wait"
del /f /q "%TEMP%\JOSINODJ_uninstall.bat" > /dev/null 2>&1
exit /b

:desinstalar
echo.
echo  ============================
echo    Desinstalando JOSINODJ...
echo  ============================
echo.

taskkill /IM JOSINODJ.exe /F > /dev/null 2>&1

set "DEST=%ProgramFiles%\JOSINODJ"
if exist "%DEST%" (
    echo  Eliminando archivos...
    rd /s /q "%DEST%"
)

powershell -NoProfile -Command "Remove-Item ([Environment]::GetFolderPath('CommonDesktopDirectory') + '\JOSINODJ.lnk') -Force -ErrorAction SilentlyContinue"

set "START_MENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs\JOSINODJ"
if exist "%START_MENU%" rd /s /q "%START_MENU%"

reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /f > /dev/null 2>&1

echo.
echo  ============================
echo    Desinstalacion completada
echo  ============================
echo.
echo  JOSINODJ desinstalado correctamente.
echo  Tus listas y ajustes en %USERPROFILE%\.josinodj\ NO han sido eliminados.
echo.
pause
exit /b 0

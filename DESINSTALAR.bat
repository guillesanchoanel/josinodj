@echo off
chcp 65001 > /dev/null
title JOSINODJ - Desinstalador

:: Si no estamos en TEMP, copiarse ahi y relanzar con permisos de admin
:: Esto evita el problema de borrar la carpeta mientras el bat corre dentro de ella
if /i not "%~dp0" == "%TEMP%\" (
    copy /Y "%~f0" "%TEMP%\JOSINODJ_uninstall.bat" > /dev/null
    powershell -Command "Start-Process '%TEMP%\JOSINODJ_uninstall.bat' -Verb RunAs"
    exit /b
)

:: A partir de aqui corremos desde TEMP como administrador
echo.
echo  ============================
echo    Desinstalando JOSINODJ...
echo  ============================
echo.

:: Cerrar el programa si esta abierto
taskkill /IM JOSINODJ.exe /F > /dev/null 2>&1

:: Borrar carpeta de instalacion
set "DEST=%ProgramFiles%\JOSINODJ"
if exist "%DEST%" (
    echo  Eliminando archivos...
    rd /s /q "%DEST%"
)

:: Borrar acceso directo del Escritorio
powershell -NoProfile -Command "Remove-Item ([Environment]::GetFolderPath('CommonDesktopDirectory') + '\JOSINODJ.lnk') -Force -ErrorAction SilentlyContinue"

:: Borrar acceso directo del Menu Inicio
set "START_MENU=%ProgramData%\Microsoft\Windows\Start Menu\Programs\JOSINODJ"
if exist "%START_MENU%" rd /s /q "%START_MENU%"

:: Borrar entrada del registro
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /f > /dev/null 2>&1

:: Borrar la copia temporal de este bat
del /f /q "%TEMP%\JOSINODJ_uninstall.bat" > /dev/null 2>&1

echo.
echo  ============================
echo    Desinstalacion completada
echo  ============================
echo.
echo  JOSINODJ ha sido desinstalado correctamente.
echo  Tus listas y ajustes en %USERPROFILE%\.josinodj\ NO han sido eliminados.
echo  Puedes borrarlos manualmente si lo deseas.
echo.
pause
exit /b 0

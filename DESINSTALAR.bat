@echo off
title JOSINODJ - Desinstalador

net session >nul 2>&1
if errorlevel 1 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo  Desinstalando JOSINODJ...
echo.

set "DEST=%ProgramFiles%\JOSINODJ"

:: Borrar accesos directos
del /f /q "%Public%\Desktop\JOSINODJ.lnk" >nul 2>&1
del /f /q "%USERPROFILE%\Desktop\JOSINODJ.lnk" >nul 2>&1
rmdir /s /q "%ProgramData%\Microsoft\Windows\Start Menu\Programs\JOSINODJ" >nul 2>&1

:: Limpiar registro
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\JOSINODJ" /f >nul 2>&1

:: Borrar archivos de configuración del usuario
rmdir /s /q "%USERPROFILE%\.josinodj" >nul 2>&1

:: Borrar carpeta de instalación
timeout /t 2 /nobreak >nul
rmdir /s /q "%DEST%" >nul 2>&1

echo  JOSINODJ desinstalado correctamente.
pause

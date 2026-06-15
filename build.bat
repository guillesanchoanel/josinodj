@echo off
setlocal EnableDelayedExpansion
title JOSINODJ - Compilando...
color 0B

echo.
echo  ==============================================
echo    JOSINODJ ^| Creando ejecutable Windows
echo  ==============================================
echo.

:: ── 1. Dependencias de build ─────────────────────────────────────────────
echo  [1/4] Instalando herramientas de build...
pip install pillow pyinstaller --quiet --upgrade
if errorlevel 1 (
    echo  ERROR: No se pudo instalar PyInstaller
    goto :error
)

:: ── 2. Convertir PNG a ICO ───────────────────────────────────────────────
echo  [2/4] Convirtiendo icono PNG ^-^> ICO...
python -c ^"
from PIL import Image
img = Image.open('assets/icon.png').convert('RGBA')
img.save('assets/icon.ico', format='ICO',
         sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
print('  OK: assets/icon.ico creado')
^"
if errorlevel 1 (
    echo  AVISO: No se pudo convertir el icono ^(necesitas 'pip install pillow'^)
    echo  Continuando sin icono personalizado...
)

:: ── 3. Compilar con PyInstaller ──────────────────────────────────────────
echo  [3/4] Compilando con PyInstaller ^(puede tardar 2-5 minutos^)...
python -m PyInstaller josinodj.spec --noconfirm --clean
if errorlevel 1 (
    echo.
    echo  ERROR: PyInstaller falló.
    echo  Posible causa: PyInstaller no es compatible con tu versión de Python.
    echo  Solución: instala Python 3.12 desde python.org y repite este proceso.
    goto :error
)

:: ── 4. Añadir script de instalación ─────────────────────────────────────
echo  [4/4] Preparando distribución...
if exist "dist\JOSINODJ\JOSINODJ.exe" (
    copy /Y "INSTALAR.bat" "dist\JOSINODJ\INSTALAR.bat" >nul 2>&1
    copy /Y "DESINSTALAR.bat" "dist\JOSINODJ\DESINSTALAR.bat" >nul 2>&1

    echo.
    echo  ==============================================
    echo    BUILD COMPLETADO CON EXITO
    echo  ==============================================
    echo.
    echo  Ejecutable:  dist\JOSINODJ\JOSINODJ.exe
    echo  Tamanyo:
    for /f "tokens=3" %%a in ('dir /s /-c "dist\JOSINODJ" ^| findstr "bytes"') do set SIZE=%%a
    echo    Carpeta dist\JOSINODJ ^(aprox. 150-300 MB^)
    echo.
    echo  Para INSTALAR en este PC:
    echo    Ejecuta dist\JOSINODJ\INSTALAR.bat  ^(como Administrador^)
    echo.
    echo  Para DISTRIBUIR a otros PCs:
    echo    Copia la carpeta dist\JOSINODJ entera y ejecuta INSTALAR.bat ahi
    echo    ^(no necesitan Python instalado^)
    echo.
) else (
    echo  ERROR: No se encontró el ejecutable generado
    goto :error
)

color 07
pause
exit /b 0

:error
echo.
echo  El build ha fallado. Revisa los errores arriba.
color 0C
pause
exit /b 1

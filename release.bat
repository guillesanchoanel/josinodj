@echo off
chcp 65001 > nul
echo ============================================
echo   JOSINODJ - Crear nueva release
echo ============================================
echo.

REM Leer version actual
set /p VERSION=<version.txt
set VERSION=%VERSION: =%

echo Version actual: %VERSION%
echo.
set /p NEW_VERSION=Nueva version (Enter para mantener %VERSION%):
if "%NEW_VERSION%"=="" set NEW_VERSION=%VERSION%

REM Actualizar version.txt
echo %NEW_VERSION%> version.txt

REM Compilar
echo.
echo [1/4] Compilando...
python -m PyInstaller josinodj.spec --noconfirm --clean
if errorlevel 1 (
    echo ERROR: Fallo al compilar
    pause
    exit /b 1
)

REM Copiar ffmpeg al dist si existe
if exist assets\ffmpeg.exe (
    echo Copiando ffmpeg...
    copy /Y assets\ffmpeg.exe dist\JOSINODJ\assets\ffmpeg.exe > nul
)

REM Crear zip del dist
echo [2/4] Creando zip...
set ZIP_NAME=JOSINODJ-v%NEW_VERSION%.zip
if exist %ZIP_NAME% del %ZIP_NAME%
powershell -Command "Compress-Archive -Path 'dist\JOSINODJ\*' -DestinationPath '%ZIP_NAME%'"
if errorlevel 1 (
    echo ERROR: Fallo al crear zip
    pause
    exit /b 1
)

REM Commit y push
echo [3/4] Subiendo codigo a GitHub...
git add -A
git commit -m "Release v%NEW_VERSION%"
git push origin master

REM Crear release en GitHub
echo [4/4] Creando release en GitHub...
gh release create v%NEW_VERSION% %ZIP_NAME% --title "v%NEW_VERSION%" --notes "Version %NEW_VERSION%"
if errorlevel 1 (
    echo ERROR: Fallo al crear release en GitHub
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Release v%NEW_VERSION% publicada!
echo ============================================
del %ZIP_NAME%
pause

@echo off
chcp 65001 >nul
title PixelCursor - EXE Olusturucu / Yeni Surum
cd /d "%~dp0"

echo ============================================================
echo   PixelCursor - yeni surum hazirlama
echo   (surum numarasi + exe derleme + version.json)
echo ============================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [HATA] Bu bilgisayarda Python bulunamadi.
    echo EXE'yi olusturmak icin SADECE senin bilgisayarinda Python gerekir.
    pause
    exit /b 1
)

if not exist "PixelCursor.pyw" (
    echo [HATA] PixelCursor.pyw bu klasorde bulunamadi.
    pause
    exit /b 1
)

set "HERE=%~dp0."
set "BUILD=%TEMP%\pixelcursor_build"

echo [1/4] Surum numarasi
echo   Enter'a basarsan surum otomatik bir artirilir (or. 4.0.0 -^> 4.0.1).
echo   Istersen kendin yaz (or. 4.1.0).
set "NEWVER="
set /p "NEWVER=  Yeni surum: "
set "VER="
for /f "delims=" %%v in ('python "%HERE%\PixelCursor.pyw" --bump-version %NEWVER%') do set "VER=%%v"
if "%VER%"=="" (
    echo [HATA] Surum numarasi ayarlanamadi.
    pause
    exit /b 1
)
echo   Surum: %VER%
echo.

echo [2/4] PyInstaller ve Pillow kuruluyor...
python -m pip install --upgrade --quiet --disable-pip-version-check pyinstaller Pillow
if errorlevel 1 (
    echo [HATA] Paketler kurulamadi. Internet baglantini kontrol et.
    pause
    exit /b 1
)

echo [3/4] EXE derleniyor (1-2 dakika surebilir)...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name "PixelCursor" ^
    --icon "%HERE%\PixelCursor.ico" ^
    --hidden-import PIL.Image ^
    --distpath "%HERE%" ^
    --workpath "%BUILD%\work" ^
    --specpath "%BUILD%" ^
    --log-level WARN ^
    "%HERE%\PixelCursor.pyw"
if errorlevel 1 (
    echo [HATA] Derleme basarisiz oldu.
    pause
    exit /b 1
)
rmdir /s /q "%BUILD%" 2>nul

echo [4/4] version.json olusturuluyor (guncelleme bilgisi)...
python "%HERE%\PixelCursor.pyw" --make-version-json "%HERE%" >nul
if errorlevel 1 (
    echo [HATA] version.json olusturulamadi.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   TAMAM! PixelCursor v%VER% hazir.
echo   Simdi GitHub Desktop'ta Commit + Push yap:
echo   kullanicilar uygulamadaki "Guncellemeleri denetle" ile
echo   yeni surume tek tikla gececek.
echo ============================================================
pause

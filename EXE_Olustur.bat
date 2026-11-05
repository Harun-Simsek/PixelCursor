@echo off
chcp 65001 >nul
title PixelCursor - EXE Olusturucu
cd /d "%~dp0"

echo ============================================================
echo   PixelCursor.exe olusturuluyor (Python gerektirmeyen surum)
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

echo [1/3] PyInstaller ve Pillow kuruluyor...
python -m pip install --upgrade --quiet --disable-pip-version-check pyinstaller Pillow
if errorlevel 1 (
    echo [HATA] Paketler kurulamadi. Internet baglantini kontrol et.
    pause
    exit /b 1
)

set "BUILD=%TEMP%\pixelcursor_build"
set "HERE=%~dp0."

echo [2/3] EXE derleniyor (1-2 dakika surebilir)...
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

echo [3/3] Gecici dosyalar temizleniyor...
rmdir /s /q "%BUILD%" 2>nul

echo.
echo ============================================================
echo   TAMAM! Masaustunde PixelCursor.exe olusturuldu.
echo   Arkadaslarina sadece bu dosyayi gondermen yeterli.
echo ============================================================
pause

@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
    echo Python 3.12 veya daha yenisi bulunamadi. https://www.python.org/downloads/
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)"
if errorlevel 1 (
    echo Python 3.12+ gerekli. Uygun Python kurun ve eski .venv klasorunu yeniden olusturun.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 (
    echo Kurulum basarisiz. Yukaridaki hata mesajini kontrol edin.
    pause
    exit /b 1
)
echo Kurulum tamamlandi. BASLAT_WINDOWS.bat ile uygulamayi acin.
pause

@echo off
echo ========================================
echo   Serious Game - Local Server
echo ========================================

cd /d "%~dp0"

REM Aktifkan virtualenv jika ada
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    echo [OK] Virtualenv aktif
) else (
    echo [!] Virtualenv tidak ditemukan, pakai Python global
)

REM Install dependencies jika belum
pip install -r requirements.txt -q

REM Inisialisasi database jika belum ada
if not exist "game.db" (
    echo [INFO] Database belum ada, membuat database...
    python seed.py
)

REM Tampilkan IP lokal
echo.
echo [INFO] IP Laptop ini:
ipconfig | findstr /i "IPv4"
echo.
echo [INFO] Siswa buka browser dan ketik: http://[IP_LAPTOP]:5000
echo [INFO] Contoh: http://192.168.1.10:5000
echo.
echo [INFO] Tekan Ctrl+C untuk menghentikan server
echo ========================================

python run.py
pause

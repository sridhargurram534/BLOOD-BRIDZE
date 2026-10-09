@echo off
cd /d "%~dp0"
setlocal

echo ============================================
echo        BLOOD BRIDGE - FULL PROTOTYPE
echo ============================================
echo.

echo [1/3] Installing frontend packages (if needed)...
npm.cmd install --legacy-peer-deps --include=optional
if errorlevel 1 (
  echo.
  echo npm install failed.
  pause
  exit /b 1
)

echo.
echo [2/3] Checking Python API dependencies...
python -c "import flask, flask_sqlalchemy, flask_socketio, flask_cors" >nul 2>&1
if errorlevel 1 (
  echo Installing Python API dependencies...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Python dependency installation failed.
    pause
    exit /b 1
  )
)

echo.
echo [3/3] Starting Blood Bridge API on port 5000...
start "Blood Bridge API" cmd /k "cd /d %~dp0 && python app.py"
timeout /t 3 /nobreak >nul

echo Starting Blood Bridge frontend on port 3000...
echo Keep this window open while using the app.
echo.
npm.cmd run dev

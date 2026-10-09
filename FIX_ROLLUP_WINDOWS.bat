@echo off
cd /d "%~dp0"
setlocal

echo ============================================
echo   BLOOD BRIDGE - WINDOWS ROLLUP REPAIR
echo ============================================
echo.

echo Removing broken/incomplete frontend install...
if exist node_modules rmdir /s /q node_modules
if exist package-lock.json del /f /q package-lock.json

echo.
echo Installing pinned Rollup/Vite dependencies...
npm.cmd install --legacy-peer-deps --include=optional
if errorlevel 1 (
  echo.
  echo npm install failed. Please check your Node.js/npm installation and internet connection.
  pause
  exit /b 1
)

echo.
echo Rollup repair complete. You can now run:
echo   npm.cmd run dev
 echo.
pause

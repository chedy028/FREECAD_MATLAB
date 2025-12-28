@echo off
:: MATLAB Engine API Installer
:: Right-click this file and select "Run as administrator"

echo ================================================
echo   MATLAB Engine API Installation
echo ================================================
echo.

:: Check if running as admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Not running as Administrator!
    echo.
    echo Please RIGHT-CLICK this file and select:
    echo "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo [OK] Running with admin privileges
echo.

:: Change to MATLAB directory
cd /d "C:\Program Files\MATLAB\R2025b\extern\engines\python"
if %errorlevel% neq 0 (
    echo [ERROR] MATLAB directory not found!
    pause
    exit /b 1
)

echo Installing to: C:\Users\chend\anaconda3\python.exe
echo.
echo This will take 30-60 seconds...
echo.

:: Install
C:\Users\chend\anaconda3\python.exe setup.py install

if %errorlevel% equ 0 (
    echo.
    echo ================================================
    echo   [SUCCESS] Installation Complete!
    echo ================================================
    echo.
    echo Testing...
    C:\Users\chend\anaconda3\python.exe -c "import matlab.engine; print('[OK] MATLAB Engine API is working!')"
    echo.
    echo You can now:
    echo   - Run full E2E tests
    echo   - Use MATLAB simulations in the agent
    echo   - Run thermal/structural analysis
    echo.
) else (
    echo.
    echo ================================================
    echo   [ERROR] Installation Failed
    echo ================================================
    echo.
    echo Please check the error messages above.
    echo.
)

echo.
pause

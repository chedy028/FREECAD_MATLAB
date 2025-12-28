# MATLAB Engine API Installation Guide
# Run PowerShell as Administrator, then run this script

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  MATLAB Engine API for Python Installer" -ForegroundColor White
Write-Host "============================================`n" -ForegroundColor Cyan

# Check for admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "[ERROR] This script requires Administrator privileges!" -ForegroundColor Red
    Write-Host "`nPlease:" -ForegroundColor Yellow
    Write-Host "  1. Right-click PowerShell" -ForegroundColor White
    Write-Host "  2. Select 'Run as Administrator'" -ForegroundColor White
    Write-Host "  3. Run this script again" -ForegroundColor White
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Running with Administrator privileges`n" -ForegroundColor Green

# Navigate to MATLAB directory
$matlabPath = "C:\Program Files\MATLAB\R2025b\extern\engines\python"
Write-Host "MATLAB Engine Path: $matlabPath" -ForegroundColor Cyan

if (-not (Test-Path $matlabPath)) {
    Write-Host "[ERROR] MATLAB Engine directory not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Set-Location $matlabPath
Write-Host "[OK] Changed to MATLAB Engine directory`n" -ForegroundColor Green

# Install
Write-Host "Installing MATLAB Engine API..." -ForegroundColor Cyan
Write-Host "This may take 1-2 minutes...`n" -ForegroundColor Yellow

try {
    python setup.py install
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n============================================" -ForegroundColor Green
        Write-Host "  [SUCCESS] MATLAB Engine API installed!" -ForegroundColor White
        Write-Host "============================================`n" -ForegroundColor Green
        
        Write-Host "Testing installation..." -ForegroundColor Cyan
        python -c "import matlab.engine; print('✓ MATLAB Engine API is working!')"
        
        Write-Host "`nYou can now run:" -ForegroundColor Yellow
        Write-Host "  - Full E2E tests with MATLAB simulation" -ForegroundColor White
        Write-Host "  - Autonomous CAD → MATLAB optimization loops" -ForegroundColor White
        Write-Host "  - Thermal/structural analysis with PDE Toolbox" -ForegroundColor White
    } else {
        throw "Installation returned error code $LASTEXITCODE"
    }
} catch {
    Write-Host "`n============================================" -ForegroundColor Red
    Write-Host "  [ERROR] Installation failed" -ForegroundColor White
    Write-Host "============================================`n" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "`nTry manual installation:" -ForegroundColor Yellow
    Write-Host "  cd '$matlabPath'" -ForegroundColor White
    Write-Host "  python setup.py install" -ForegroundColor White
}

Write-Host ""
Read-Host "Press Enter to exit"


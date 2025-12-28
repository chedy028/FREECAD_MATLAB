# Restart Script - Stop and Start Fresh
# Use this when you need to reload .env changes

Write-Host "Stopping any running servers..." -ForegroundColor Yellow
Get-Process python -ErrorAction SilentlyContinue | Where-Object {$_.CommandLine -like "*uvicorn*"} | Stop-Process -Force -ErrorAction SilentlyContinue

Start-Sleep -Seconds 2

Write-Host "Starting server with updated .env..." -ForegroundColor Green
.\start_app.ps1



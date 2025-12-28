# Start the CAD → MATLAB Autonomous Agent
# This script automatically loads the API key from .env file

Write-Host "Starting CAD -> MATLAB Autonomous Agent..." -ForegroundColor Cyan
Write-Host ""

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env file not found!" -ForegroundColor Red
    Write-Host "Please create a .env file with your OPENROUTER_API_KEY" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Example .env file:" -ForegroundColor Yellow
    Write-Host "OPENROUTER_API_KEY=sk-or-v1-your-key-here" -ForegroundColor Gray
    exit 1
}

# Start the server (dotenv will auto-load the .env file)
Write-Host "Starting server on http://127.0.0.1:8001..." -ForegroundColor Green
Write-Host "Press CTRL+C to stop the server" -ForegroundColor Yellow
Write-Host ""

python -m uvicorn agent.api.main:app --host 127.0.0.1 --port 8001 --reload


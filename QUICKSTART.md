# 🚀 APP IS LIVE - QUICK START GUIDE

## ✅ Server Status: RUNNING

**Base URL:** http://127.0.0.1:8000  
**Interactive Docs:** http://127.0.0.1:8000/docs

---

## 🎯 Quick Start: Run Your First Autonomous Optimization

### Option 1: Using PowerShell

```powershell
$body = @{
    message = "Design an enclosure that minimizes mass while keeping max temperature below 85°C. Start with 120x60x40mm dimensions, 2.5mm walls, 80W heat source."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" `
                  -Method POST `
                  -Body $body `
                  -ContentType "application/json"
```

### Option 2: Using curl

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Design an enclosure, minimize mass, max temp 85C\"}"
```

### Option 3: Using the Interactive Docs

1. Open: http://127.0.0.1:8000/docs
2. Click on `POST /chat`
3. Click "Try it out"
4. Enter your design request
5. Click "Execute"

---

## 📊 What Just Happened:

✅ **App Started Successfully**  
✅ **353 LLM Models Available** (via OpenRouter)  
✅ **FreeCAD 1.0 Ready** (for CAD generation)  
✅ **MATLAB Engine 25.2 Ready** (for simulation)  
✅ **API Endpoints Active**

---

## 🧪 Test the System:

### 1. Check System Health
```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

### 2. List Available Models
```powershell
Invoke-RestMethod http://127.0.0.1:8000/models | 
    Select-Object -ExpandProperty models | 
    Select-Object id, name -First 10
```

### 3. Simple Test Chat
```powershell
$test = @{ message = "Hello, design a simple box 100x50x30mm" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" `
                  -Method POST `
                  -Body $test `
                  -ContentType "application/json"
```

---

## 🎨 Example Design Requests:

### Example 1: Thermal Optimization
```
"Design an aluminum enclosure for a 100W heat source. Minimize mass while keeping maximum temperature below 80°C. Start with 150x75x50mm, 3mm walls, ambient 25°C, natural convection."
```

### Example 2: Compact Design
```
"Create the smallest possible enclosure that maintains max temperature ≤ 90°C with a 50W heat source. Use 2mm walls minimum for structural integrity."
```

### Example 3: Mass-Constrained
```
"Design an enclosure with mass ≤ 500g that can handle 120W heat dissipation. Optimize dimensions starting from 200x100x60mm."
```

---

## 📁 Where to Find Results:

After each optimization:
```
runs/
└── <run-id>/
    ├── iter_000/
    │   ├── cad/
    │   │   ├── geometry.step      ← CAD model
    │   │   └── cad_meta.json     ← Dimensions, volume
    │   ├── simulation/
    │   │   ├── result.json        ← Metrics (temp, mass)
    │   │   ├── plots/
    │   │   │   └── temperature_distribution.png
    │   │   └── logs/
    │   └── result.json            ← Iteration summary
    ├── iter_001/
    └── ...
```

---

## 🔍 Monitor Progress:

### Watch Server Logs:
Check terminal where server is running for real-time updates

### View Artifacts:
```powershell
# List all runs
Get-ChildItem runs/ -Directory

# View latest run
$latestRun = Get-ChildItem runs/ -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1
explorer $latestRun.FullName
```

---

## 🛠️ Advanced Usage:

### Custom Model Selection:
```json
{
  "message": "Design request...",
  "model_choice": {
    "primary": "openai/gpt-4o",
    "fallbacks": ["anthropic/claude-3.5-sonnet"]
  }
}
```

### Resume Previous Run:
```json
{
  "message": "Continue optimization",
  "run_id": "previous-run-id-here"
}
```

---

## 🎯 Available LLM Models (Top Picks):

| Model | Context | Best For |
|-------|---------|----------|
| **openai/gpt-4o** | 128K | General design (default) |
| **anthropic/claude-3.5-sonnet** | 200K | Complex reasoning |
| **google/gemini-1.5-pro** | 1M | Long context |

View all 353 models at: http://127.0.0.1:8000/models

---

## ⚙️ System Configuration:

- **FreeCAD:** Auto-detected at `C:\Program Files\FreeCAD 1.0\`
- **MATLAB:** Auto-detected at `C:\Program Files\MATLAB\R2025b\`
- **Database:** SQLite at `./cad_matlab_agent.db`
- **Artifacts:** Saved to `./runs/`

---

## 🛑 To Stop the Server:

Press `CTRL+C` in the server terminal

---

## 🆘 Troubleshooting:

### Server not responding?
```powershell
# Check if running
Get-Process python | Where-Object {$_.Path -like "*uvicorn*"}

# Restart
# Press CTRL+C, then:
python -m uvicorn agent.api.main:app --reload
```

### Need real API key?
```powershell
# Set your OpenRouter API key:
$env:OPENROUTER_API_KEY="sk-or-v1-your-actual-key"
```

---

## 📚 Documentation:

- **API Docs:** http://127.0.0.1:8000/docs (Interactive)
- **Redoc:** http://127.0.0.1:8000/redoc (Alternative format)
- **Full Guide:** See `GETTING_STARTED.md`
- **Architecture:** See `ARCHITECTURE.md`
- **Test Results:** See `FINAL_E2E_RESULTS.md`

---

**🎉 Your Autonomous CAD → MATLAB Agent is LIVE!**  
**Start optimizing designs now at http://127.0.0.1:8000/docs** 🚀


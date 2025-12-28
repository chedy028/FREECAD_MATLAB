# 🚀 How to Start the Autonomous CAD → MATLAB Agent

## ✅ App is Currently Running!

**Server URL:** http://127.0.0.1:8002

**API Docs:** http://127.0.0.1:8002/docs

---

## 🔑 API Key is Saved!

Your OpenRouter API key is now saved in `.env` file:
```
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

The app will automatically load it on startup! 🎉

---

## 📋 Quick Start (Easiest Method)

### Option 1: Use the PowerShell Script (Recommended)
```powershell
.\start_app.ps1
```

### Option 2: Manual Command
```powershell
python -m uvicorn agent.api.main:app --host 127.0.0.1 --port 8002 --reload
```

**Note:** With `.env` file created, you no longer need to set the API key manually!

---

## 🌐 Use the Web UI

1. **Open the UI in your browser:**
   - Double-click `agent_ui.html` in your project folder, OR
   - Drag `agent_ui.html` into your browser

2. **The UI will automatically connect to:** `http://127.0.0.1:8002`

3. **Try the example:**
   - Click "Start Design & Optimization"
   - Example request is already filled in
   - Watch the agent work autonomously!

---

## 🧪 Test the API (PowerShell)

### Health Check
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8002/health" -Method GET
```

### List Available LLM Models
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8002/models" -Method GET
```

### Start an Optimization Task
```powershell
$body = @{
    message = "Design a cantilever beam that minimizes mass while keeping max stress below 200 MPa and deflection below 5mm. Use aluminum (E=69 GPa, density=2700 kg/m³), length 200mm, width 20mm, applied force 100N at the tip."
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8002/chat" `
                  -Method POST `
                  -Body $body `
                  -ContentType "application/json"
```

---

## 📁 Where Results are Saved

All design iterations are saved to:

```
C:\Projects\FREECAD_MATLAB\runs\
```

Each run creates:
```
runs/
  └── <run_id>/
      ├── iter_001/
      │   ├── cad/
      │   │   ├── geometry.step
      │   │   ├── preview.png
      │   │   └── cad_meta.json
      │   └── simulation/
      │       ├── results.json
      │       └── plots/
      ├── iter_002/
      │   └── ...
      └── summary.json
```

---

## 🛑 Stop the Server

Press `CTRL+C` in the terminal where the server is running

---

## 🔑 How the Logic Works

1. **You send a request:** "Design a beam that minimizes mass..."

2. **LLM (GPT-4) plans:** Outputs JSON with parameters
   ```json
   {
     "template": "cantilever_beam_v1",
     "parameters": {"length": 200, "width": 20, "height": 12},
     "reasoning": "Starting conservative for first iteration..."
   }
   ```

3. **FreeCAD builds:** Runs pre-written Python template with those parameters
   - Creates 3D geometry
   - Exports STEP file

4. **MATLAB simulates:** Runs pre-written analysis script
   - Imports geometry
   - Performs FEA (stress, deflection)
   - Returns metrics

5. **Agent evaluates:** Checks objectives & constraints
   - Stress: 156 MPa < 200 MPa ✅
   - Deflection: 3.2 mm < 5 mm ✅
   - Mass: 42g (can we reduce?)

6. **LLM decides:** "Let's try height=10mm to reduce mass..."

7. **Loop repeats** until optimal design is found! 🎯

---

## 📊 System Status

| Component | Status | Notes |
|-----------|--------|-------|
| **FastAPI Server** | ✅ Running | Port 8002 |
| **FreeCAD 1.0** | ✅ Configured | Headless mode |
| **MATLAB R2025b** | ✅ Engine API | PDE Toolbox |
| **OpenRouter API** | ✅ Connected | GPT-4 models |
| **Web UI** | ✅ Ready | `agent_ui.html` |

---

## 💡 Example Requests

### Cantilever Beam Optimization
```
Design a cantilever beam that minimizes mass while keeping max stress below 200 MPa and deflection below 5mm. Use aluminum (E=69 GPa, density=2700 kg/m³), length 200mm, width 20mm, applied force 100N at the tip.
```

### Electronics Enclosure Cooling
```
Optimize an aluminum enclosure for electronics cooling. Requirements: minimize mass, keep max temperature ≤ 85°C, start with 120×60×40mm box, 2.5mm wall thickness, internal heat source 80W, ambient 25°C.
```

### Bracket Stress Analysis
```
Design a mounting bracket that minimizes material usage while maintaining a safety factor of 1.5. Material: steel (E=200 GPa, yield=250 MPa), mounting holes at 50mm spacing, load 500N vertical.
```

---

## 🎉 You're Ready!

**Your autonomous design agent is running and ready to optimize!**

Open `agent_ui.html` in your browser and start designing! 🚀


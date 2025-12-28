# Autonomous CAD → MATLAB Simulation Agent

A fully autonomous pipeline where humans only chat with an LLM, which orchestrates:
- Parametric CAD model generation in FreeCAD (headless)
- Geometry export (STEP/STL)
- MATLAB simulation (PDE Toolbox / custom scripts)
- Iterative optimization based on objectives and constraints

## Features

- **LLM-Driven**: Uses OpenRouter API with model selection and fallbacks
- **Headless CAD**: FreeCAD CLI for parametric geometry generation
- **MATLAB Integration**: MATLAB Engine API for Python
- **Structured Outputs**: JSON schema validation for all LLM outputs
- **Safety First**: Sandboxed execution, allowlists, timeouts
- **State Machine**: Autonomous iteration with convergence detection

## Architecture

```
Chat UI → Agent API (FastAPI) → LLM Gateway (OpenRouter)
                              ↓
                         Orchestrator (State Machine)
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
             FreeCAD Runner      MATLAB Runner
                    ↓                   ↓
              CAD Artifacts      Simulation Results
                    └─────────┬─────────┘
                              ↓
                         Run Store (SQLite)
```

## Prerequisites

1. **Python 3.9+**
2. **FreeCAD** (with CLI support)
   - Windows: FreeCADCmd.exe
   - Linux: freecadcmd
   - macOS: FreeCADCmd in app bundle
3. **MATLAB** with:
   - MATLAB Engine API for Python
   - PDE Toolbox (for geometry import)
4. **OpenRouter API Key**

## Installation

### 1. Install Python dependencies

```bash
pip install poetry
poetry install
```

### 2. Install MATLAB Engine for Python

```bash
cd "matlabroot/extern/engines/python"
python setup.py install
```

Replace `matlabroot` with your MATLAB installation path (e.g., `C:\Program Files\MATLAB\R2023b` on Windows).

### 3. Configure FreeCAD path

Edit `config.yaml` to point to your FreeCAD CLI executable, or set the `FREECAD_PATH` environment variable.

### 4. Set up environment

```bash
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY
```

## Quick Start

### 1. Start the agent API

```bash
poetry run uvicorn agent.api.main:app --reload
```

### 2. Send a chat message

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Design an enclosure that minimizes mass while keeping max temperature below 85°C. Start with 120×60×40mm dimensions.",
    "run_id": null
  }'
```

### 3. Monitor progress

The agent will autonomously:
1. Plan the first design iteration
2. Generate CAD geometry in FreeCAD
3. Run MATLAB thermal simulation
4. Evaluate results against objectives/constraints
5. Iterate until convergence or budget exhaustion

## Project Structure

```
/agent
  /api              # FastAPI endpoints
  /llm              # OpenRouter client
  /orchestrator     # State machine, validators, scoring
  /tools            # FreeCAD and MATLAB runners
  /cad_templates    # Parametric CAD scripts
  /matlab           # Simulation entry points
  /db               # Database models
/runs               # Artifacts (gitignored)
/tests              # Acceptance tests
config.yaml         # Configuration
```

## Data Contracts

### DesignIteration Schema

The LLM outputs structured JSON for each iteration:

```json
{
  "run_id": "uuid",
  "iteration": 3,
  "model_choice": {
    "primary": "openai/gpt-4o",
    "fallbacks": ["anthropic/claude-3.5-sonnet"]
  },
  "cad": {
    "template": "parametric_enclosure_v1",
    "units": "mm",
    "params": {"L": 120.0, "W": 60.0, "H": 40.0, "wall_t": 2.5},
    "export": {"format": "step", "filename": "geometry.step"}
  },
  "simulation": {
    "type": "pde_thermal_steady",
    "matlab_entrypoint": "run_sim.m",
    "inputs": {"ambientC": 25, "heatW": 80, "hConv": 10}
  },
  "objectives": [{"name": "minimize", "metric": "mass_g", "weight": 1.0}],
  "constraints": [{"metric": "max_tempC", "op": "<=", "value": 85}]
}
```

## Exposed Tools (LLM Interface)

The LLM can only call these safe, allow-listed tools:

1. **list_models()** - Discover available OpenRouter models
2. **build_cad(template, params, export_format)** - Generate CAD geometry
3. **run_matlab(entrypoint, geometry_path, sim_inputs)** - Run simulation
4. **record_result(metrics, artifacts)** - Store iteration results
5. **final_report()** - Generate markdown summary

## Security

- **No raw shell access** for LLM
- **Sandboxed paths**: All operations under `runs/`
- **Allowlists**: CAD templates, MATLAB entrypoints, export formats
- **Timeouts**: FreeCAD (5min), MATLAB (10min)
- **Input validation**: Parameter ranges, blocked extensions

## Testing

```bash
poetry run pytest tests/
```

## License

MIT


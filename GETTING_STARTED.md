# Getting Started Guide

This guide will help you set up and run the CAD-MATLAB Agent for the first time.

## Prerequisites

### 1. Python 3.9+

```bash
python --version  # Should be 3.9 or higher
```

### 2. FreeCAD (with CLI)

**Windows:**
- Download from [freecad.org](https://www.freecad.org/)
- Install to default location: `C:\Program Files\FreeCAD 0.21\`
- FreeCADCmd.exe will be at `C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe`

**Linux:**
```bash
sudo apt install freecad
# or
sudo snap install freecad
```

**macOS:**
```bash
brew install --cask freecad
```

Verify installation:
```bash
# Linux
freecadcmd --version

# Windows
"C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe" --version

# macOS
/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd --version
```

### 3. MATLAB (with PDE Toolbox)

- Install MATLAB R2020b or later
- Ensure PDE Toolbox is installed
- Install MATLAB Engine API for Python:

```bash
# Find your MATLAB root
matlab -batch "disp(matlabroot); exit"

# Install engine (replace path with your matlabroot)
cd "/path/to/matlabroot/extern/engines/python"
python setup.py install
```

Verify installation:
```python
import matlab.engine
eng = matlab.engine.start_matlab()
print("MATLAB Engine working!")
eng.quit()
```

### 4. OpenRouter API Key

- Sign up at [openrouter.ai](https://openrouter.ai/)
- Get your API key
- Add credits to your account

## Installation

### Option 1: Using Poetry (Recommended)

```bash
# Clone or navigate to project
cd FREECAD_MATLAB

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### Option 2: Using pip

```bash
# Install dependencies
pip install -r requirements.txt
```

## Configuration

### 1. Create .env file

```bash
cp .env.example .env
```

### 2. Edit .env

```bash
# Required
OPENROUTER_API_KEY=your_api_key_here

# Optional - auto-detected if not set
# FREECAD_PATH=/usr/bin/freecadcmd
# MATLAB_ROOT=/usr/local/MATLAB/R2023b
```

### 3. Review config.yaml

The default `config.yaml` should work for most cases, but you can customize:

- **FreeCAD paths**: Update `freecad.windows_cmd`, `linux_cmd`, or `macos_cmd`
- **MATLAB timeout**: Increase if simulations are slow
- **Agent budgets**: Reduce `max_iterations` for faster testing
- **Convergence**: Adjust `epsilon` and `stable_iterations`

## Running the Agent

### Option 1: API Server (Recommended)

Start the FastAPI server:

```bash
python -m uvicorn agent.api.main:app --reload
```

Or with custom host/port:

```bash
python -m agent.api.main
```

The API will be available at:
- **Base URL**: http://localhost:8000
- **Interactive docs**: http://localhost:8000/docs
- **Health check**: http://localhost:8000/health

### Option 2: Programmatic (Python Script)

Run the example script:

```bash
python scripts/run_example.py
```

This will:
1. Initialize all components
2. Run a sample optimization
3. Save results to `runs/`

### Option 3: Using curl

Send a chat message:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Design an enclosure that minimizes mass while keeping max temperature below 85°C. Start with 120×60×40mm dimensions.",
    "run_id": null
  }'
```

## Verify Installation

Run the quickstart script:

```bash
bash scripts/quickstart.sh
```

This will:
1. Check environment variables
2. Start the API server
3. Run a health check
4. Send a test design request

## Understanding the Output

After a successful run, you'll see:

```
Design optimization completed!
- Total iterations: 8
- Best iteration: 6
- Best score: 142.5000
- Run ID: <uuid>

Check `runs/<uuid>/` for artifacts.
```

### Artifact Structure

```
runs/<run_id>/
├── iter_000/
│   ├── cad/
│   │   ├── geometry.step      # CAD geometry
│   │   └── cad_meta.json      # Bbox, volume, params
│   ├── simulation/
│   │   ├── result.json        # Metrics
│   │   ├── plots/
│   │   │   └── temperature_distribution.png
│   │   └── logs/
│   │       └── matlab.txt
│   └── result.json            # Iteration summary
├── iter_001/
│   └── ...
└── iter_00N/
    └── ...
```

## Example Workflows

### 1. Simple Thermal Optimization

**Goal**: Minimize mass while keeping max temperature ≤ 85°C

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Minimize mass, keep max temp ≤ 85°C. Start with 120×60×40mm enclosure, 80W heat source, 25°C ambient, convection coefficient 10 W/m²·K."
  }'
```

The agent will:
1. Start with baseline geometry
2. Run thermal simulation
3. Check if temp constraint is satisfied
4. If temp too high: increase dimensions/wall thickness
5. If temp OK: try reducing dimensions to minimize mass
6. Iterate until convergence

### 2. Custom Parameters

**Goal**: Explore different starting points

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Design a compact enclosure. Start with 80×40×30mm, wall thickness 1.5mm. Keep max temp ≤ 70°C with 50W heat."
  }'
```

### 3. Multi-Objective (Future)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Minimize both mass and max temperature. Start with 100×50×50mm."
  }'
```

## Testing

Run the test suite:

```bash
# All tests
pytest tests/

# Specific test file
pytest tests/test_validators.py

# With verbose output
pytest tests/ -v

# Skip E2E test (requires FreeCAD/MATLAB)
pytest tests/ -k "not e2e"
```

## Troubleshooting

### "FreeCAD CLI not found"

**Solution**: Set `FREECAD_PATH` in `.env` or update `config.yaml`

```bash
# Find FreeCAD
which freecadcmd  # Linux/macOS
# or check: C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe (Windows)

# Set in .env
echo "FREECAD_PATH=/path/to/freecadcmd" >> .env
```

### "MATLAB Engine API not installed"

**Solution**: Install MATLAB Engine for Python

```bash
cd "$(matlab -batch 'disp(matlabroot); exit')/extern/engines/python"
python setup.py install
```

### "OpenRouter API key invalid"

**Solution**: Check your API key

1. Log in to [openrouter.ai](https://openrouter.ai/)
2. Go to Keys section
3. Copy your key
4. Update `.env`:
   ```
   OPENROUTER_API_KEY=sk-or-v1-...
   ```

### "Simulation timeout"

**Solution**: Increase MATLAB timeout in `config.yaml`

```yaml
matlab:
  timeout_seconds: 1200  # 20 minutes
```

### "CAD generation failed"

**Possible causes:**
- Invalid parameters (too small/large)
- Wall thickness > dimensions
- FreeCAD version incompatibility

**Solution**: Check logs in `runs/<run_id>/iter_XXX/logs/`

## Advanced Configuration

### Using PostgreSQL

1. Install PostgreSQL
2. Create database: `createdb cad_matlab_agent`
3. Update `config.yaml`:
   ```yaml
   storage:
     database_url: "postgresql+asyncpg://user:password@localhost/cad_matlab_agent"
   ```

### Using Redis (Job Queue)

1. Install Redis
2. Update `config.yaml`:
   ```yaml
   queue:
     enabled: true
     broker_url: "redis://localhost:6379/0"
   ```
3. Install extras: `pip install redis celery`
4. Start worker: `celery -A agent.worker worker`

### Docker Deployment

```bash
# Build image
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f agent
```

**Note**: FreeCAD and MATLAB must be added to Docker image separately.

## Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) for system design
- Explore [agent/orchestrator/](agent/orchestrator/) for state machine
- Customize CAD templates in [cad_templates/](cad_templates/)
- Create new MATLAB simulations in [matlab/](matlab/)
- Review security in [agent/security.py](agent/security.py)

## Getting Help

- Check logs in `runs/<run_id>/`
- Run health check: `curl http://localhost:8000/health`
- Enable debug logging in `config.yaml`:
  ```yaml
  api:
    log_level: "DEBUG"
  ```
- Review FastAPI docs: http://localhost:8000/docs

## Common Patterns

### Accessing Run Results Programmatically

```python
import json
from pathlib import Path

run_id = "your-run-id-here"
run_dir = Path("runs") / run_id

# Read iteration results
for iter_dir in sorted(run_dir.glob("iter_*")):
    result_file = iter_dir / "result.json"
    with open(result_file) as f:
        result = json.load(f)
        print(f"Iteration {result['iteration']}: Score = {result['objective_score']}")

# Find best iteration
best_iter = max(
    run_dir.glob("iter_*"),
    key=lambda p: json.load(open(p / "result.json"))["objective_score"]
)
print(f"Best iteration: {best_iter.name}")
```

### Monitoring Progress

```python
import asyncio
from agent.orchestrator.runner import AgentOrchestrator

async def monitor_run():
    orchestrator = AgentOrchestrator(...)  # Initialize
    
    status = await orchestrator.start_run("Design request...")
    
    while orchestrator.current_state not in ["COMPLETED", "FAILED"]:
        await orchestrator.step()
        print(f"State: {orchestrator.current_state}, Iteration: {orchestrator.current_design.iteration}")
        await asyncio.sleep(1)
    
    print(f"Final status: {orchestrator.current_state}")

asyncio.run(monitor_run())
```

Happy optimizing! 🚀


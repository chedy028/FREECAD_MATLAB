# Architecture Documentation

## Overview

The CAD-MATLAB Agent is an autonomous system that iteratively designs and optimizes mechanical/thermal systems through LLM-driven planning, headless CAD generation, and MATLAB simulation.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User (Chat)                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Agent API                         │
│  - Chat endpoint                                            │
│  - Run status queries                                       │
│  - Health checks                                            │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│               AgentOrchestrator (State Machine)             │
│                                                             │
│  States:                                                    │
│  ┌─────┐   ┌──────────┐   ┌─────────┐   ┌──────────┐     │
│  │PLAN │──▶│BUILD_CAD │──▶│SIMULATE │──▶│EVALUATE  │     │
│  └─────┘   └──────────┘   └─────────┘   └──────────┘     │
│     ▲                                          │           │
│     │                                          ▼           │
│     │                                     ┌────────┐       │
│     └─────────────────────────────────────│DECIDE  │       │
│                                           └────────┘       │
│                          │                                 │
│                          ▼                                 │
│                   ┌─────────────┐                          │
│                   │FAIL_RECOVERY│                          │
│                   └─────────────┘                          │
└───────────────┬───────────────────────┬─────────────────────┘
                │                       │
        ┌───────▼────────┐      ┌──────▼──────┐
        │                │      │             │
        ▼                ▼      ▼             ▼
┌──────────────┐  ┌─────────────────┐  ┌──────────────┐
│ OpenRouter   │  │ FreeCAD Runner  │  │MATLAB Runner │
│  LLM Client  │  │  (Headless)     │  │ (Engine API) │
└──────────────┘  └─────────────────┘  └──────────────┘
        │                  │                   │
        │                  │                   │
        ▼                  ▼                   ▼
┌──────────────┐  ┌─────────────────┐  ┌──────────────┐
│  GPT-4, etc. │  │ CAD Templates   │  │ MATLAB Sims  │
└──────────────┘  └─────────────────┘  └──────────────┘
                           │                   │
                           └───────┬───────────┘
                                   ▼
                          ┌─────────────────┐
                          │  Artifacts      │
                          │  (runs/ dir)    │
                          │  - Geometry     │
                          │  - Results      │
                          │  - Plots        │
                          └─────────────────┘
```

## Component Details

### 1. FastAPI Agent API (`agent/api/main.py`)

**Responsibilities:**
- HTTP endpoints for chat-based interaction
- Request validation
- Response formatting
- Health checks

**Key Endpoints:**
- `POST /chat` - Send design request, get autonomous optimization
- `GET /health` - System health check
- `GET /models` - List available LLM models
- `GET /runs/{run_id}` - Get run status (future)

**Security:**
- CORS middleware
- Input validation via Pydantic
- No direct file access exposed

### 2. AgentOrchestrator (`agent/orchestrator/runner.py`)

**Responsibilities:**
- State machine implementation
- Autonomous iteration loop
- Conversation management with LLM
- Convergence detection
- Failure recovery

**State Machine:**

1. **PLAN**: LLM proposes `DesignIteration` JSON
   - First iteration: uses user request
   - Subsequent: uses previous results
   - Output: Validated `DesignIteration` schema

2. **BUILD_CAD**: Generate geometry
   - Calls `FreeCADRunner`
   - Validates template, parameters, format
   - Produces STEP/STL file

3. **SIMULATE**: Run analysis
   - Calls `MATLABRunner`
   - Imports geometry (PDE Toolbox)
   - Produces metrics, plots, logs

4. **EVALUATE**: Assess results
   - Compute objective score
   - Check constraint satisfaction
   - Record iteration result

5. **DECIDE**: Determine next action
   - Check stop conditions:
     - Constraints satisfied + converged
     - Budget exhausted (iterations, time, failures)
   - If continue: add results to conversation, return to PLAN
   - If stop: transition to COMPLETED/STOPPED

6. **FAIL_RECOVERY**: Handle errors
   - CAD generation failure
   - Simulation failure
   - LLM suggests parameter adjustments
   - Max failures → FAILED state

**Stop Conditions:**
- Constraints satisfied AND converged (improvement < ε for N iterations)
- Iteration budget reached
- Wall-time budget reached
- Consecutive failures exceed limit

### 3. OpenRouter Client (`agent/llm/openrouter_client.py`)

**Responsibilities:**
- Chat completion requests
- Tool calling (OpenAI-style)
- Model discovery and caching
- Response parsing
- Retry logic

**Features:**
- Model fallbacks
- Structured outputs (`response_format`)
- Rate limiting handling
- Timeout management

**API:**
```python
await client.chat_completion(
    messages=[...],
    model="openai/gpt-4o",
    tools=[...],  # Optional function definitions
    response_format={"type": "json_object"},  # Structured output
    route="fallback",  # Auto-fallback to other models
)
```

### 4. FreeCAD Runner (`agent/tools/freecad_runner.py`)

**Responsibilities:**
- Execute FreeCAD CLI (`freecadcmd`)
- Validate templates, parameters, formats
- Parse CAD metadata (bbox, volume)
- Timeout enforcement

**Template System:**
- Templates are Python scripts in `cad_templates/`
- Each template exposes:
  - Command-line interface (argparse)
  - `build()` function (creates geometry)
  - `export()` function (writes STEP/STL)
  - Metadata generation (JSON)

**Security:**
- Template allowlist
- Parameter range validation
- Sandboxed execution (subprocess)
- Timeout enforcement (default: 5 minutes)

**Example Template:** `parametric_enclosure_v1.py`
- Parameters: L, W, H, wall_t, fillet_r
- Generates hollow box with optional fillets
- Exports STEP or STL

### 5. MATLAB Runner (`agent/tools/matlab_runner.py`)

**Responsibilities:**
- Start MATLAB Engine (lazy init)
- Execute MATLAB scripts
- Pass inputs via workspace
- Read outputs (JSON or workspace variables)
- Timeout enforcement

**MATLAB Engine API:**
```python
eng = matlab.engine.start_matlab()
eng.workspace["geometry_file"] = "/path/to/geometry.step"
eng.workspace["ambientC"] = 25
eng.eval("run('run_sim.m')", nargout=0)
metrics = json.load(open("result.json"))
```

**Security:**
- Entrypoint allowlist
- Sandboxed MATLAB directory
- Timeout enforcement (default: 10 minutes)
- Workspace cleanup between runs

**Example Simulation:** `run_sim.m`
- PDE thermal steady-state analysis
- Imports geometry via `importGeometry()`
- Applies BCs (convection)
- Solves and extracts metrics
- Saves plots and results

### 6. Validators (`agent/orchestrator/validators.py`)

**Responsibilities:**
- Pydantic schemas for all data contracts
- LLM output validation
- Type safety

**Key Schemas:**
- `DesignIteration` - Complete iteration specification (canonical LLM output)
- `CADConfig` - CAD generation parameters
- `SimulationConfig` - MATLAB simulation parameters
- `Objective` - Optimization objective (minimize/maximize)
- `Constraint` - Design constraint (metric op value)
- `CADResult` - CAD generation result
- `SimulationResult` - Simulation result
- `IterationResult` - Complete iteration result
- `RunStatus` - Current run status

### 7. Scoring (`agent/orchestrator/scoring.py`)

**Responsibilities:**
- Compute objective scores
- Evaluate constraints
- Detect convergence

**Objective Scoring:**
- Single objective: return metric (negated if maximizing)
- Multi-objective: weighted sum (normalized to minimization)

**Constraint Evaluation:**
- Check each constraint: `metric op value`
- Return (all_satisfied, violations_list)

**Convergence Detection:**
- Relative improvement < ε for N consecutive iterations
- Configurable ε (default: 0.1%) and N (default: 3)

### 8. Security (`agent/security.py`)

**Responsibilities:**
- Path validation (sandbox enforcement)
- Extension blocking
- Filename sanitization
- Template/entrypoint validation

**Guardrails:**
- All paths must be under `allowed_base_paths` (e.g., `runs/`)
- Blocked extensions: `.exe`, `.dll`, `.so`, `.sh`, `.bat`, `.ps1`
- Template allowlist (no arbitrary scripts)
- MATLAB entrypoint allowlist (no arbitrary code execution)
- Max file size limits

### 9. Database (`agent/db/models.py`)

**Responsibilities:**
- Persist run metadata
- Store iteration results
- Enable run queries (future)

**Models:**
- `Run` - Run-level metadata (state, budgets, best iteration)
- `Iteration` - Iteration-level results (design spec, CAD, simulation, evaluation)

**Technology:**
- SQLAlchemy async
- SQLite (default) or PostgreSQL
- Alembic for migrations (future)

## Data Flow

### Typical Iteration Flow

1. **User sends request**
   ```
   POST /chat
   {
     "message": "Design enclosure, minimize mass, max temp ≤ 85°C",
     "run_id": null
   }
   ```

2. **Orchestrator starts run**
   - Initialize state machine (PLAN)
   - Build conversation with system prompt + user request

3. **PLAN State**
   - LLM receives conversation history
   - LLM outputs `DesignIteration` JSON
   - Validation via Pydantic
   - Transition to BUILD_CAD

4. **BUILD_CAD State**
   - Extract CAD config from `DesignIteration`
   - Validate template, params, format
   - Run FreeCAD CLI: `freecadcmd template.py -- --L 120 --W 60 ...`
   - FreeCAD produces geometry.step + metadata
   - Transition to SIMULATE (or FAIL_RECOVERY on error)

5. **SIMULATE State**
   - Start MATLAB engine (if not started)
   - Set workspace variables (geometry path, sim inputs)
   - Run entrypoint: `run('run_sim.m')`
   - MATLAB imports geometry, solves PDE, saves results
   - Read metrics from result.json
   - Transition to EVALUATE (or FAIL_RECOVERY on error)

6. **EVALUATE State**
   - Compute objective score from metrics
   - Evaluate all constraints
   - Create `IterationResult`
   - Add to history
   - Transition to DECIDE

7. **DECIDE State**
   - Check stop conditions
   - If converged + constraints OK → COMPLETED
   - If budget exhausted → COMPLETED/STOPPED
   - Else → add iteration summary to conversation, return to PLAN

8. **Repeat** until terminal state

9. **Return final status**
   ```json
   {
     "run_id": "...",
     "state": "COMPLETED",
     "iterations_completed": 8,
     "best_iteration": 6,
     "best_score": 142.5,
     "message": "Check runs/xxx/ for artifacts"
   }
   ```

## Configuration

**Config File:** `config.yaml`

Key sections:
- `openrouter`: API key, models, timeouts
- `agent`: Budgets, convergence params
- `freecad`: CLI path, templates, param ranges
- `matlab`: Timeouts, entrypoints
- `storage`: Runs directory, database URL
- `security`: Sandbox, allowlists, blocked extensions
- `api`: Host, port, CORS

## Security Model

### Principles

1. **No LLM shell access**: LLM cannot execute arbitrary commands
2. **Allowlists everywhere**: Templates, entrypoints, formats
3. **Sandboxed paths**: All operations under `runs/`
4. **Timeouts**: Prevent runaway processes
5. **Input validation**: Pydantic schemas, range checks

### Attack Surface Analysis

**What the LLM CAN do:**
- Propose parameter values (validated against ranges)
- Choose from allowlisted templates
- Choose from allowlisted MATLAB entrypoints
- Set simulation inputs (numeric values)

**What the LLM CANNOT do:**
- Write files outside `runs/`
- Execute arbitrary shell commands
- Load arbitrary CAD scripts
- Run arbitrary MATLAB code
- Access network resources directly

**Residual Risks:**
- Malicious parameter values (mitigated by range validation)
- Resource exhaustion (mitigated by timeouts)
- FreeCAD/MATLAB vulnerabilities (out of scope)

## Testing

### Unit Tests
- `tests/test_validators.py` - Schema validation
- `tests/test_scoring.py` - Objective/constraint evaluation
- `tests/test_security.py` - Path validation, sanitization

### Integration Tests
- (Future) Test FreeCAD + MATLAB runners with fixtures

### Acceptance Test
- `tests/test_e2e.py` - Full autonomous run
- Requires: FreeCAD, MATLAB, OpenRouter API key
- Verifies: Complete pipeline, artifact generation, security

## Performance Considerations

### Bottlenecks
1. **LLM latency**: 2-10s per planning step
2. **FreeCAD execution**: 5-30s per geometry
3. **MATLAB simulation**: 10-120s per solve

### Optimization Strategies
1. **Model selection**: Faster models for planning (e.g., GPT-3.5)
2. **Parallel runs**: Multiple orchestrators (future)
3. **Job queue**: Celery for long-running sims (future)
4. **Caching**: Reuse results for identical designs (future)

### Scalability
- **Single-machine**: 3-5 concurrent runs (config: `max_concurrent_runs`)
- **Distributed**: Job queue + worker pool (future)
- **Database**: PostgreSQL for multi-user (future)

## Future Enhancements

1. **Tool calling**: Expose tools as OpenAI-style functions
2. **Bayesian optimization**: Smarter parameter search
3. **Multi-fidelity**: Quick sims for exploration, detailed for refinement
4. **Visualization**: Web UI for real-time monitoring
5. **Collaboration**: Multi-agent design exploration
6. **Database queries**: Query past runs, lineage tracking
7. **Experiment tracking**: MLflow-style logging

## References

- [OpenRouter API Docs](https://openrouter.ai/docs)
- [FreeCAD Python API](https://wiki.freecad.org/Python_scripting_tutorial)
- [MATLAB Engine API for Python](https://www.mathworks.com/help/matlab/matlab-engine-for-python.html)
- [PDE Toolbox Geometry Import](https://www.mathworks.com/help/pde/ug/importgeometry.html)


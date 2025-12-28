"""FastAPI main application"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent.config import load_config
from agent.db.models import init_db
from agent.llm.openrouter_client import OpenRouterClient
from agent.orchestrator.runner import AgentOrchestrator
from agent.orchestrator.validators import RunStatus
from agent.tools.freecad_runner import FreeCADRunner
from agent.tools.matlab_runner import MATLABRunner


# Load configuration
config = load_config()

# Global instances (initialized in lifespan)
orchestrator: Optional[AgentOrchestrator] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global orchestrator

    # Initialize database
    await init_db(config.storage.database_url)

    # Initialize clients
    api_key = os.getenv(config.openrouter.api_key_env)
    llm_client = OpenRouterClient(
        api_key=api_key,
        base_url=config.openrouter.base_url,
        http_referer=config.openrouter.http_referer,
        x_title=config.openrouter.x_title,
        timeout=config.openrouter.timeout_seconds,
    )

    # Initialize runners
    freecad_runner = FreeCADRunner(
        timeout=config.freecad.timeout_seconds,
        allowed_templates=config.freecad.allowed_templates,
        allowed_formats=config.freecad.allowed_export_formats,
        param_ranges=config.freecad.param_ranges,
    )

    matlab_runner = MATLABRunner(
        timeout=config.matlab.timeout_seconds,
        allowed_entrypoints=config.matlab.allowed_entrypoints,
        startup_options=config.matlab.startup_options,
        workspace_cleanup=config.matlab.workspace_cleanup,
    )

    # Initialize orchestrator
    runs_dir = Path(config.storage.base_dir)
    runs_dir.mkdir(exist_ok=True)

    orchestrator = AgentOrchestrator(
        openrouter_client=llm_client,
        freecad_runner=freecad_runner,
        matlab_runner=matlab_runner,
        runs_base_dir=runs_dir,
        convergence_epsilon=config.agent.convergence["epsilon"],
        convergence_stable_iters=int(config.agent.convergence["stable_iterations"]),
    )

    try:
        print(f"Agent API started - runs directory: {runs_dir.absolute()}")
    except UnicodeEncodeError:
        print("Agent API started - runs directory: runs/")

    yield

    # Cleanup
    await matlab_runner.stop_engine()
    print("Agent API shutdown")


# Create FastAPI app
app = FastAPI(
    title="CAD-MATLAB Agent API",
    description="Autonomous CAD → MATLAB simulation agent with LLM orchestration",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models

class ChatRequest(BaseModel):
    """Chat message request"""

    message: str
    run_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat message response"""

    run_id: str
    status: RunStatus
    message: str


class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    freecad_available: bool
    matlab_available: bool
    database_connected: bool


# Endpoints

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    # Test FreeCAD
    freecad_ok = await orchestrator.freecad.test_installation()

    # Test MATLAB
    matlab_ok = await orchestrator.matlab.test_installation()

    # Test database (always OK if we got here)
    db_ok = True

    return HealthResponse(
        status="healthy" if (freecad_ok and matlab_ok and db_ok) else "degraded",
        freecad_available=freecad_ok,
        matlab_available=matlab_ok,
        database_connected=db_ok,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint - start or continue a design run.
    
    If run_id is None, starts a new autonomous run.
    If run_id is provided, continues an existing run (not implemented in MVP).
    """
    # Start new autonomous run
    try:
        status = await orchestrator.run_autonomous(
            user_request=request.message,
            run_id=UUID(request.run_id) if request.run_id else None,
        )

        # Generate response message based on final state
        if status.state.value == "COMPLETED":
            message = (
                f"Design optimization completed!\n"
                f"- Total iterations: {status.iterations_completed}\n"
                f"- Best iteration: {status.best_iteration}\n"
                f"- Best score: {status.best_score:.4f}\n"
                f"- Run ID: {status.run_id}\n\n"
                f"Check `runs/{status.run_id}/` for artifacts."
            )
        elif status.state.value == "FAILED":
            message = (
                f"Design optimization failed after {status.consecutive_failures} failures.\n"
                f"- Total iterations: {status.iterations_completed}\n"
                f"- Run ID: {status.run_id}\n\n"
                f"Check `runs/{status.run_id}/` for error logs."
            )
        else:
            message = f"Run stopped in state: {status.state.value}"

        return ChatResponse(
            run_id=str(status.run_id),
            status=status,
            message=message,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running agent: {str(e)}")


@app.get("/runs/{run_id}", response_model=RunStatus)
async def get_run_status(run_id: str):
    """Get status of a specific run"""
    # TODO: Implement database lookup
    raise HTTPException(status_code=501, detail="Not implemented")


@app.get("/models")
async def list_models():
    """List available OpenRouter models"""
    try:
        models = await orchestrator.llm.list_models()
        return {
            "models": [
                {
                    "id": m.id,
                    "name": m.name,
                    "context_length": m.context_length,
                }
                for m in models
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching models: {str(e)}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "CAD-MATLAB Agent API",
        "version": "0.1.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent.api.main:app",
        host=config.api.host,
        port=config.api.port,
        log_level=config.api.log_level.lower(),
        reload=True,
    )


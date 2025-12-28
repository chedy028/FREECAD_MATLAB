"""FastAPI main application"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select

# Load .env file before anything else
load_dotenv()

from agent.config import load_config
from agent.db.models import init_db, Run, Iteration
from agent.llm.openrouter_client import OpenRouterClient
from agent.logging_config import setup_logging, get_logger
from agent.orchestrator.runner import AgentOrchestrator
from agent.orchestrator.validators import RunState, RunStatus
from agent.tools.freecad_runner import FreeCADRunner
from agent.tools.matlab_runner import MATLABRunner


# Load configuration
config = load_config()

# Global instances (initialized in lifespan)
orchestrator: Optional[AgentOrchestrator] = None
session_maker = None
logger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    global orchestrator, session_maker, logger

    # Setup logging first
    logger = setup_logging(config)
    logger.info("Starting CAD-MATLAB Agent API")

    # Initialize database and get session maker
    _, session_maker = await init_db(config.storage.database_url)
    logger.info("Database initialized")

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
    # Get platform-specific FreeCAD command
    import platform
    if platform.system() == "Windows":
        freecad_cmd = config.freecad.windows_cmd
    elif platform.system() == "Darwin":
        freecad_cmd = config.freecad.macos_cmd
    else:
        freecad_cmd = config.freecad.linux_cmd
    
    freecad_runner = FreeCADRunner(
        freecad_cmd=freecad_cmd,
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
        max_conversation_messages=config.agent.max_conversation_messages,
    )

    logger.info(
        "Agent API started",
        extra_data={"runs_dir": str(runs_dir.absolute())},
    )

    yield

    # Cleanup
    await matlab_runner.stop_engine()
    logger.info("Agent API shutdown")


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

        # Save to database
        if session_maker:
            try:
                await orchestrator.save_to_database(session_maker, request.message)
            except Exception as db_error:
                if logger:
                    logger.warning(
                        f"Failed to save run to database: {db_error}",
                        extra_data={"run_id": str(status.run_id)},
                    )

        # Generate response message based on final state
        if status.state.value == "COMPLETED":
            score_str = f"{status.best_score:.4f}" if status.best_score is not None else "N/A"
            message = (
                f"Design optimization completed!\n"
                f"- Total iterations: {status.iterations_completed}\n"
                f"- Best iteration: {status.best_iteration}\n"
                f"- Best score: {score_str}\n"
                f"- Stopped reason: {status.stopped_reason or 'N/A'}\n"
                f"- Run ID: {status.run_id}\n\n"
                f"Check `runs/{status.run_id}/` for artifacts."
            )
        elif status.state.value == "FAILED":
            message = (
                f"Design optimization failed after {status.consecutive_failures} failures.\n"
                f"- Total iterations: {status.iterations_completed}\n"
                f"- Stopped reason: {status.stopped_reason or 'N/A'}\n"
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


@app.get("/runs/{run_id}")
async def get_run_status(run_id: str):
    """Get status of a specific run"""
    if session_maker is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with session_maker() as session:
        # Query run
        result = await session.execute(
            select(Run).where(Run.run_id == run_id)
        )
        run = result.scalar_one_or_none()

        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        return {
            "run_id": run.run_id,
            "state": run.state,
            "current_iteration": run.current_iteration,
            "iterations_completed": run.iterations_completed,
            "consecutive_failures": run.consecutive_failures,
            "best_iteration": run.best_iteration,
            "best_score": run.best_score,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            "stopped_reason": run.stopped_reason,
            "user_request": run.user_request,
        }


@app.get("/runs/{run_id}/iterations")
async def get_run_iterations(run_id: str):
    """Get all iterations for a run"""
    if session_maker is None:
        raise HTTPException(status_code=500, detail="Database not initialized")

    async with session_maker() as session:
        # Check if run exists
        run_result = await session.execute(
            select(Run).where(Run.run_id == run_id)
        )
        run = run_result.scalar_one_or_none()

        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        # Get iterations
        result = await session.execute(
            select(Iteration)
            .where(Iteration.run_id == run_id)
            .order_by(Iteration.iteration)
        )
        iterations = result.scalars().all()

        return {
            "run_id": run_id,
            "total_iterations": len(iterations),
            "iterations": [
                {
                    "iteration": it.iteration,
                    "timestamp": it.timestamp.isoformat() if it.timestamp else None,
                    "duration_s": it.duration_s,
                    "cad_success": bool(it.cad_success),
                    "sim_success": bool(it.sim_success),
                    "objective_score": it.objective_score,
                    "constraints_satisfied": bool(it.constraints_satisfied) if it.constraints_satisfied is not None else None,
                    "constraint_violations": it.constraint_violations,
                    "artifacts_path": it.artifacts_path,
                }
                for it in iterations
            ],
        }


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
    """Root endpoint - serve the UI"""
    ui_path = Path(__file__).parent.parent.parent / "agent_ui.html"
    if ui_path.exists():
        return FileResponse(ui_path, media_type="text/html")
    return {
        "name": "CAD-MATLAB Agent API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/api")
async def api_info():
    """API info endpoint"""
    return {
        "name": "CAD-MATLAB Agent API",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/runs/{run_id}/artifacts/{filename}")
async def get_artifact(run_id: str, filename: str):
    """Serve artifact files (STL, STEP, etc.) from a run directory"""
    # Validate filename to prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Check in various subdirectories
    runs_dir = Path(config.storage.base_dir)
    possible_paths = [
        runs_dir / run_id / "cad" / filename,
        runs_dir / run_id / "simulation" / filename,
        runs_dir / run_id / filename,
    ]
    
    for file_path in possible_paths:
        if file_path.exists() and file_path.is_file():
            # Determine media type
            suffix = file_path.suffix.lower()
            media_types = {
                ".stl": "model/stl",
                ".step": "model/step",
                ".stp": "model/step",
                ".json": "application/json",
                ".txt": "text/plain",
                ".log": "text/plain",
                ".m": "text/plain",
                ".png": "image/png",
                ".jpg": "image/jpeg",
            }
            media_type = media_types.get(suffix, "application/octet-stream")
            
            return FileResponse(
                path=str(file_path),
                media_type=media_type,
                filename=filename
            )
    
    raise HTTPException(status_code=404, detail=f"Artifact '{filename}' not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "agent.api.main:app",
        host=config.api.host,
        port=config.api.port,
        log_level=config.api.log_level.lower(),
        reload=True,
    )


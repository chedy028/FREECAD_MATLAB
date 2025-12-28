"""Simple demo API for testing without FreeCAD/MATLAB"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(
    title="CAD-MATLAB Agent API (Demo Mode)",
    description="Demo API - FreeCAD and MATLAB not required",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    """Chat message request"""
    message: str
    run_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat message response"""
    run_id: str
    message: str
    status: str


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "CAD-MATLAB Agent API (Demo Mode)",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "note": "This is demo mode. To run full agent, install FreeCAD and MATLAB."
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mode": "demo",
        "freecad_available": False,
        "matlab_available": False,
        "database_connected": True,
        "note": "Install FreeCAD and MATLAB for full functionality"
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint - demo mode
    
    In full mode, this would start an autonomous optimization.
    """
    import uuid
    
    run_id = request.run_id or str(uuid.uuid4())
    
    return ChatResponse(
        run_id=run_id,
        status="demo_mode",
        message=(
            f"Demo Mode Response\n\n"
            f"Your request: {request.message}\n\n"
            f"In full mode, the agent would:\n"
            f"1. Parse your design requirements\n"
            f"2. Generate CAD geometry using FreeCAD\n"
            f"3. Run MATLAB thermal simulation\n"
            f"4. Iterate until objectives met\n"
            f"5. Return optimized design\n\n"
            f"To enable full functionality:\n"
            f"- Install FreeCAD (with CLI)\n"
            f"- Install MATLAB with PDE Toolbox\n"
            f"- Set OPENROUTER_API_KEY environment variable\n"
            f"- Restart with: python -m uvicorn agent.api.main:app\n\n"
            f"Run ID: {run_id}"
        )
    )


@app.get("/models")
async def list_models():
    """List available models (demo)"""
    return {
        "models": [
            {"id": "openai/gpt-4o", "name": "GPT-4o", "context_length": 128000},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "context_length": 200000},
            {"id": "google/gemini-1.5-pro", "name": "Gemini 1.5 Pro", "context_length": 1000000},
        ],
        "note": "Demo data. Set OPENROUTER_API_KEY to fetch real models."
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)




"""Configuration loader"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


class OpenRouterConfig(BaseModel):
    """OpenRouter configuration"""

    api_key_env: str = "OPENROUTER_API_KEY"
    base_url: str = "https://openrouter.ai/api/v1"
    default_model: str = "openai/gpt-4o"
    fallback_models: List[str] = []
    http_referer: Optional[str] = None
    x_title: Optional[str] = None
    model_cache_ttl_seconds: int = 600
    timeout_seconds: int = 120
    max_retries: int = 3


class AgentConfig(BaseModel):
    """Agent configuration"""

    max_concurrent_runs: int = 3
    max_conversation_messages: int = 50  # Conversation history limit
    default_budgets: Dict[str, int] = {
        "max_iterations": 30,
        "max_wall_time_s": 7200,
        "max_failures": 8,
    }
    convergence: Dict[str, float] = {
        "epsilon": 0.001,
        "stable_iterations": 3,
    }


class FreeCADConfig(BaseModel):
    """FreeCAD configuration"""

    windows_cmd: str = r"C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe"
    linux_cmd: str = "/usr/bin/freecadcmd"
    macos_cmd: str = "/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd"
    timeout_seconds: int = 300
    allowed_templates: List[str] = ["parametric_enclosure_v1"]
    allowed_export_formats: List[str] = ["step", "stl"]
    param_ranges: Dict[str, List[float]] = {}


class MATLABConfig(BaseModel):
    """MATLAB configuration"""

    timeout_seconds: int = 600
    allowed_entrypoints: List[str] = ["run_sim.m"]
    startup_options: List[str] = ["-nodesktop", "-nosplash"]
    workspace_cleanup: bool = True
    pde: Dict[str, Any] = {
        "geometry_formats": ["step", "stl"],
        "default_mesh_size": "normal",
    }


class StorageConfig(BaseModel):
    """Storage configuration"""

    base_dir: str = "runs"
    artifacts_retention_days: int = 30
    database_url: str = "sqlite+aiosqlite:///./cad_matlab_agent.db"
    structure: Dict[str, str] = {
        "cad": "cad",
        "simulation": "simulation",
        "plots": "plots",
        "logs": "logs",
    }


class SecurityConfig(BaseModel):
    """Security configuration"""

    sandbox_enabled: bool = True
    allowed_base_paths: List[str] = ["runs", "cad_templates", "matlab"]
    max_file_size_mb: int = 500
    blocked_extensions: List[str] = [
        ".exe", ".dll", ".so", ".dylib", ".sh", ".bat", ".ps1"
    ]


class APIConfig(BaseModel):
    """API configuration"""

    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    log_level: str = "INFO"


class QueueConfig(BaseModel):
    """Queue configuration"""

    enabled: bool = False
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/1"


class LoggingConfig(BaseModel):
    """Logging configuration"""

    level: str = "INFO"
    format: str = "json"  # "json" or "text"
    file_path: Optional[str] = None  # Optional file logging
    include_correlation_id: bool = True
    include_timestamps: bool = True


class Config(BaseModel):
    """Complete configuration"""

    openrouter: OpenRouterConfig
    agent: AgentConfig
    freecad: FreeCADConfig
    matlab: MATLABConfig
    storage: StorageConfig
    security: SecurityConfig
    api: APIConfig
    queue: QueueConfig
    logging: LoggingConfig = LoggingConfig()  # Default logging config


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from YAML file"""
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    
    return Config(**data)


# Global config instance (loaded on import)
config: Optional[Config] = None

try:
    config = load_config()
except Exception:
    # Config will be loaded when needed
    pass


"""Pydantic schemas for LLM output validation"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class ModelChoice(BaseModel):
    """LLM model selection with fallbacks"""

    primary: str = Field(..., description="Primary model ID from OpenRouter")
    fallbacks: List[str] = Field(
        default_factory=list, description="Fallback models if primary fails"
    )


class CADExport(BaseModel):
    """CAD export configuration"""

    format: Literal["step", "stl"] = Field(..., description="Export format")
    filename: str = Field(..., description="Output filename")


class CADConfig(BaseModel):
    """CAD generation parameters"""

    template: str = Field(..., description="CAD template name (must be allowlisted)")
    units: str = Field(default="mm", description="Dimensional units")
    params: Dict[str, float] = Field(..., description="Template-specific parameters")
    export: CADExport = Field(..., description="Export configuration")

    @field_validator("template")
    @classmethod
    def validate_template(cls, v: str) -> str:
        # Validation against allowlist happens in the runner
        if not v or not v.replace("_", "").isalnum():
            raise ValueError(f"Invalid template name: {v}")
        return v

    @field_validator("params")
    @classmethod
    def validate_params(cls, v: Dict[str, float]) -> Dict[str, float]:
        for key, val in v.items():
            if not isinstance(val, (int, float)):
                raise ValueError(f"Parameter {key} must be numeric, got {type(val)}")
            if val != val:  # NaN check
                raise ValueError(f"Parameter {key} cannot be NaN")
            if val == float("inf") or val == float("-inf"):
                raise ValueError(f"Parameter {key} cannot be infinite")
        return v


class SimulationConfig(BaseModel):
    """MATLAB simulation configuration"""

    type: str = Field(..., description="Simulation type identifier")
    matlab_entrypoint: str = Field(..., description="MATLAB script/function to execute")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Input parameters")
    outputs_requested: List[str] = Field(
        default_factory=list, description="Expected output variable names"
    )

    @field_validator("matlab_entrypoint")
    @classmethod
    def validate_entrypoint(cls, v: str) -> str:
        # Must be a .m file or function name
        if not v.endswith(".m") and not v.replace("_", "").isalnum():
            raise ValueError(f"Invalid MATLAB entrypoint: {v}")
        return v


class Objective(BaseModel):
    """Optimization objective"""

    name: Literal["minimize", "maximize"] = Field(..., description="Optimization direction")
    metric: str = Field(..., description="Metric name to optimize")
    weight: float = Field(default=1.0, gt=0, description="Objective weight (multi-objective)")


class ConstraintOperator(str, Enum):
    """Constraint comparison operators"""

    LE = "<="
    LT = "<"
    GE = ">="
    GT = ">"
    EQ = "=="


class Constraint(BaseModel):
    """Design constraint"""

    metric: str = Field(..., description="Metric name to constrain")
    op: ConstraintOperator = Field(..., description="Comparison operator")
    value: float = Field(..., description="Constraint threshold")

    def evaluate(self, metric_value: float) -> bool:
        """Evaluate if constraint is satisfied"""
        ops = {
            ConstraintOperator.LE: lambda x, y: x <= y,
            ConstraintOperator.LT: lambda x, y: x < y,
            ConstraintOperator.GE: lambda x, y: x >= y,
            ConstraintOperator.GT: lambda x, y: x > y,
            ConstraintOperator.EQ: lambda x, y: abs(x - y) < 1e-9,
        }
        return ops[self.op](metric_value, self.value)


class Budgets(BaseModel):
    """Iteration budgets"""

    max_iterations: int = Field(default=30, gt=0, description="Maximum iterations")
    max_wall_time_s: int = Field(default=7200, gt=0, description="Max wall time (seconds)")
    max_failures: int = Field(default=8, gt=0, description="Max consecutive failures")


class DesignIteration(BaseModel):
    """Complete design iteration specification - canonical LLM output"""

    run_id: UUID = Field(default_factory=uuid4, description="Unique run identifier")
    iteration: int = Field(default=0, ge=0, description="Iteration number")
    model_choice: ModelChoice = Field(..., description="LLM model selection")
    cad: CADConfig = Field(..., description="CAD generation config")
    simulation: SimulationConfig = Field(..., description="Simulation config")
    objectives: List[Objective] = Field(..., min_length=1, description="Optimization objectives")
    constraints: List[Constraint] = Field(default_factory=list, description="Design constraints")
    budgets: Budgets = Field(default_factory=Budgets, description="Iteration budgets")
    reasoning: Optional[str] = Field(None, description="LLM reasoning for this iteration")

    @model_validator(mode="after")
    def validate_metrics_consistency(self) -> "DesignIteration":
        """Ensure all referenced metrics are in outputs_requested"""
        requested = set(self.simulation.outputs_requested)
        
        # Check objectives
        for obj in self.objectives:
            if obj.metric not in requested:
                requested.add(obj.metric)
        
        # Check constraints
        for const in self.constraints:
            if const.metric not in requested:
                requested.add(const.metric)
        
        # Update outputs_requested to include all metrics
        self.simulation.outputs_requested = list(requested)
        return self


class CADResult(BaseModel):
    """Result from CAD generation"""

    success: bool
    path: Optional[str] = None
    bbox: Optional[Dict[str, float]] = None  # {"xmin": ..., "xmax": ..., etc.}
    volume: Optional[float] = None
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class SimulationResult(BaseModel):
    """Result from MATLAB simulation"""

    success: bool
    metrics: Dict[str, Any] = Field(default_factory=dict)
    plots: List[str] = Field(default_factory=list)
    logs: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class IterationResult(BaseModel):
    """Complete result of one iteration"""

    iteration: int
    cad_result: CADResult
    simulation_result: SimulationResult
    objective_score: Optional[float] = None
    constraints_satisfied: bool = False
    constraint_violations: List[str] = Field(default_factory=list)
    timestamp: str
    duration_s: float


class RunState(str, Enum):
    """Agent state machine states"""

    PLAN = "PLAN"
    BUILD_CAD = "BUILD_CAD"
    SIMULATE = "SIMULATE"
    EVALUATE = "EVALUATE"
    DECIDE = "DECIDE"
    FAIL_RECOVERY = "FAIL_RECOVERY"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RunStatus(BaseModel):
    """Current run status"""

    run_id: UUID
    state: RunState
    current_iteration: int = 0
    iterations_completed: int = 0
    consecutive_failures: int = 0
    best_iteration: Optional[int] = None
    best_score: Optional[float] = None
    started_at: str
    updated_at: str
    stopped_reason: Optional[str] = None


class FinalReport(BaseModel):
    """Final report after run completion"""

    run_id: UUID
    total_iterations: int
    best_iteration: int
    best_design: DesignIteration
    best_metrics: Dict[str, Any]
    constraints_satisfied: bool
    stopped_reason: str
    artifacts: List[str]
    lineage: List[IterationResult]
    summary: str  # Markdown summary


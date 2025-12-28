"""Test validators and schemas"""

import pytest
from agent.orchestrator.validators import (
    CADConfig,
    CADExport,
    Constraint,
    ConstraintOperator,
    DesignIteration,
    ModelChoice,
    Objective,
    SimulationConfig,
)


def test_cad_config_valid():
    """Test valid CAD configuration"""
    config = CADConfig(
        template="parametric_enclosure_v1",
        units="mm",
        params={"L": 120.0, "W": 60.0, "H": 40.0, "wall_t": 2.5},
        export=CADExport(format="step", filename="geometry.step"),
    )
    assert config.template == "parametric_enclosure_v1"
    assert config.params["L"] == 120.0


def test_cad_config_invalid_params():
    """Test CAD config with invalid parameters"""
    with pytest.raises(ValueError, match="cannot be NaN"):
        CADConfig(
            template="test",
            params={"L": float("nan")},
            export=CADExport(format="step", filename="test.step"),
        )


def test_constraint_evaluation():
    """Test constraint evaluation"""
    constraint = Constraint(metric="temp", op=ConstraintOperator.LE, value=85.0)
    
    assert constraint.evaluate(80.0) is True
    assert constraint.evaluate(85.0) is True
    assert constraint.evaluate(90.0) is False


def test_objective_valid():
    """Test valid objective"""
    obj = Objective(name="minimize", metric="mass_g", weight=1.0)
    assert obj.name == "minimize"
    assert obj.metric == "mass_g"


def test_design_iteration_valid():
    """Test valid DesignIteration"""
    iteration = DesignIteration(
        model_choice=ModelChoice(primary="openai/gpt-4o"),
        cad=CADConfig(
            template="parametric_enclosure_v1",
            params={"L": 120.0},
            export=CADExport(format="step", filename="geometry.step"),
        ),
        simulation=SimulationConfig(
            type="thermal",
            matlab_entrypoint="run_sim.m",
            outputs_requested=["max_tempC"],
        ),
        objectives=[Objective(name="minimize", metric="mass_g")],
        constraints=[Constraint(metric="max_tempC", op=ConstraintOperator.LE, value=85)],
    )
    
    # Check that metrics are added to outputs_requested
    assert "mass_g" in iteration.simulation.outputs_requested
    assert "max_tempC" in iteration.simulation.outputs_requested


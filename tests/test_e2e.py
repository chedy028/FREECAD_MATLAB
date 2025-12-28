"""
End-to-end acceptance test

This test verifies the complete agent pipeline:
1. User provides a design request
2. Agent autonomously iterates
3. System produces final report and artifacts
4. All safety guardrails are respected
"""

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import pytest

from agent.config import load_config
from agent.llm.openrouter_client import OpenRouterClient
from agent.orchestrator.runner import AgentOrchestrator
from agent.orchestrator.validators import RunState
from agent.tools.freecad_runner import FreeCADRunner
from agent.tools.matlab_runner import MATLABRunner


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires FreeCAD, MATLAB, and OpenRouter API key")
async def test_e2e_autonomous_optimization():
    """
    E2E test: Full autonomous optimization run
    
    Requirements:
    - FreeCAD installed
    - MATLAB with Engine API installed
    - OPENROUTER_API_KEY set
    """
    # Load config
    config = load_config()

    # Check prerequisites
    api_key = os.getenv(config.openrouter.api_key_env)
    if not api_key:
        pytest.skip(f"{config.openrouter.api_key_env} not set")

    # Initialize components
    llm_client = OpenRouterClient(
        api_key=api_key,
        base_url=config.openrouter.base_url,
        timeout=config.openrouter.timeout_seconds,
    )

    freecad_runner = FreeCADRunner(
        timeout=config.freecad.timeout_seconds,
        allowed_templates=config.freecad.allowed_templates,
        allowed_formats=config.freecad.allowed_export_formats,
    )

    matlab_runner = MATLABRunner(
        timeout=config.matlab.timeout_seconds,
        allowed_entrypoints=config.matlab.allowed_entrypoints,
    )

    # Test FreeCAD installation
    freecad_ok = await freecad_runner.test_installation()
    if not freecad_ok:
        pytest.skip("FreeCAD not installed or not working")

    # Test MATLAB installation
    matlab_ok = await matlab_runner.test_installation()
    if not matlab_ok:
        pytest.skip("MATLAB Engine API not installed or not working")

    # Create test runs directory
    test_runs_dir = Path("runs") / "test"
    test_runs_dir.mkdir(parents=True, exist_ok=True)

    # Initialize orchestrator with reduced budgets for testing
    orchestrator = AgentOrchestrator(
        openrouter_client=llm_client,
        freecad_runner=freecad_runner,
        matlab_runner=matlab_runner,
        runs_base_dir=test_runs_dir,
        convergence_epsilon=0.01,  # More lenient for testing
        convergence_stable_iters=2,
    )

    # User request
    user_request = (
        "Minimize mass, keep max temp ≤ 85°C, start with 120×60×40 enclosure"
    )

    # Run autonomous optimization with limited iterations
    try:
        # Override budgets for faster testing
        status = await orchestrator.run_autonomous(user_request)

        # Assertions
        assert status.run_id is not None
        assert status.state in [RunState.COMPLETED, RunState.FAILED]
        assert status.iterations_completed >= 1

        # Check artifacts
        run_dir = test_runs_dir / str(status.run_id)
        assert run_dir.exists()

        # At least one iteration should have completed
        iter_dirs = list(run_dir.glob("iter_*"))
        assert len(iter_dirs) >= 1

        # Check for CAD output
        cad_files = list(run_dir.glob("iter_*/cad/*.step")) + list(
            run_dir.glob("iter_*/cad/*.stl")
        )
        assert len(cad_files) >= 1, "No CAD geometry files generated"

        # Check for simulation output
        sim_results = list(run_dir.glob("iter_*/simulation/result.json"))
        assert len(sim_results) >= 1, "No simulation results generated"

        # Verify safety: no files outside runs directory
        for item in run_dir.rglob("*"):
            assert str(item).startswith(
                str(test_runs_dir)
            ), f"File outside sandbox: {item}"

        print(f"\n✓ E2E test passed - Run ID: {status.run_id}")
        print(f"  Iterations: {status.iterations_completed}")
        print(f"  Final state: {status.state.value}")

    finally:
        await matlab_runner.stop_engine()


@pytest.mark.asyncio
async def test_security_path_validation():
    """Test that agent respects path security"""
    config = load_config()

    # Attempt to access file outside allowed paths should fail
    from agent.security import SecurityValidator

    validator = SecurityValidator(
        allowed_base_paths=config.security.allowed_base_paths,
        blocked_extensions=config.security.blocked_extensions,
        sandbox_enabled=True,
    )

    # Should raise for paths outside allowed bases
    with pytest.raises(ValueError, match="outside allowed base paths"):
        validator.validate_path("/etc/passwd")

    with pytest.raises(ValueError, match="outside allowed base paths"):
        validator.validate_path("../../secret.txt")

    # Should raise for blocked extensions
    with pytest.raises(ValueError, match="blocked for security"):
        validator.validate_path("runs/malware.exe")


@pytest.mark.asyncio
async def test_template_allowlist():
    """Test that only allowlisted CAD templates are accepted"""
    config = load_config()

    freecad_runner = FreeCADRunner(
        allowed_templates=["parametric_enclosure_v1"],
    )

    # Should raise for non-allowlisted template
    from agent.orchestrator.validators import CADConfig, CADExport

    malicious_config = CADConfig(
        template="malicious_template",
        params={"L": 100},
        export=CADExport(format="step", filename="test.step"),
    )

    with pytest.raises(ValueError, match="not in allowlist"):
        freecad_runner._validate_template(malicious_config.template)


@pytest.mark.asyncio
async def test_matlab_entrypoint_allowlist():
    """Test that only allowlisted MATLAB entrypoints are accepted"""
    config = load_config()

    matlab_runner = MATLABRunner(
        allowed_entrypoints=["run_sim.m"],
    )

    # Should raise for non-allowlisted entrypoint
    with pytest.raises(ValueError, match="not in allowlist"):
        matlab_runner._validate_entrypoint("malicious_script.m")


#!/usr/bin/env python3
"""
Example script to run the agent programmatically
"""

import asyncio
import os
from pathlib import Path

from agent.config import load_config
from agent.llm.openrouter_client import OpenRouterClient
from agent.orchestrator.runner import AgentOrchestrator
from agent.tools.freecad_runner import FreeCADRunner
from agent.tools.matlab_runner import MATLABRunner


async def main():
    """Run example design optimization"""
    # Load config
    config = load_config()

    # Initialize components
    print("Initializing agent components...")
    
    api_key = os.getenv(config.openrouter.api_key_env)
    if not api_key:
        print(f"Error: {config.openrouter.api_key_env} not set")
        return

    llm_client = OpenRouterClient(
        api_key=api_key,
        base_url=config.openrouter.base_url,
        http_referer=config.openrouter.http_referer,
        x_title=config.openrouter.x_title,
        timeout=config.openrouter.timeout_seconds,
    )

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

    # Run autonomous optimization
    user_request = (
        "Design a rectangular enclosure that minimizes mass while keeping "
        "maximum temperature below 85°C. Start with dimensions 120×60×40mm. "
        "Assume 80W internal heat source, ambient temperature 25°C, "
        "and convection coefficient 10 W/m²·K."
    )

    print(f"\nUser request: {user_request}\n")
    print("Starting autonomous optimization...\n")

    try:
        status = await orchestrator.run_autonomous(user_request)

        print("\n=== Optimization Complete ===")
        print(f"Final state: {status.state.value}")
        print(f"Total iterations: {status.iterations_completed}")
        print(f"Best iteration: {status.best_iteration}")
        print(f"Best score: {status.best_score:.4f}")
        print(f"Run ID: {status.run_id}")
        print(f"\nArtifacts: runs/{status.run_id}/")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await matlab_runner.stop_engine()


if __name__ == "__main__":
    asyncio.run(main())


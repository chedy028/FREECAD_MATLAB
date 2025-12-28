"""MATLAB Engine runner for Python"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.orchestrator.validators import SimulationConfig, SimulationResult


class MATLABRunner:
    """Execute MATLAB simulations using MATLAB Engine API for Python"""

    def __init__(
        self,
        timeout: int = 600,
        allowed_entrypoints: Optional[List[str]] = None,
        startup_options: Optional[List[str]] = None,
        workspace_cleanup: bool = True,
    ):
        self.timeout = timeout
        self.allowed_entrypoints = allowed_entrypoints or ["run_sim.m"]
        self.startup_options = startup_options or ["-nodesktop", "-nosplash"]
        self.workspace_cleanup = workspace_cleanup
        self._engine = None

    def _validate_entrypoint(self, entrypoint: str) -> None:
        """Validate MATLAB entrypoint against allowlist"""
        if entrypoint not in self.allowed_entrypoints:
            raise ValueError(
                f"Entrypoint '{entrypoint}' not in allowlist: {self.allowed_entrypoints}"
            )

    async def _start_engine(self):
        """Start MATLAB engine (lazy initialization)"""
        if self._engine is not None:
            return self._engine

        try:
            import matlab.engine
        except ImportError:
            raise RuntimeError(
                "MATLAB Engine API for Python not installed. "
                "Install from matlabroot/extern/engines/python"
            )

        # Start engine in thread pool (blocking call)
        loop = asyncio.get_event_loop()
        self._engine = await loop.run_in_executor(
            None,
            lambda: matlab.engine.start_matlab()
        )
        
        return self._engine

    async def run_matlab(
        self,
        sim_config: SimulationConfig,
        geometry_path: Optional[str],
        output_dir: Path,
    ) -> SimulationResult:
        """
        Run MATLAB simulation.
        
        Args:
            sim_config: Simulation configuration
            geometry_path: Path to STEP/STL geometry file
            output_dir: Directory for outputs (plots, logs, results)
        
        Returns:
            SimulationResult with metrics, plots, logs
        """
        try:
            # Validate entrypoint
            self._validate_entrypoint(sim_config.matlab_entrypoint)

            # Prepare output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            plots_dir = output_dir / "plots"
            plots_dir.mkdir(exist_ok=True)
            logs_dir = output_dir / "logs"
            logs_dir.mkdir(exist_ok=True)

            # Start engine
            eng = await self._start_engine()

            # Clear workspace if requested
            if self.workspace_cleanup:
                await asyncio.get_event_loop().run_in_executor(
                    None, eng.clear, "all", "nargout", 0
                )

            # Set up workspace variables
            loop = asyncio.get_event_loop()

            # Add matlab directory to path
            matlab_dir = Path("matlab").absolute()
            if matlab_dir.exists():
                await loop.run_in_executor(
                    None,
                    lambda: eng.addpath(str(matlab_dir), nargout=0)
                )

            # Set input variables
            if geometry_path:
                eng.workspace["geometry_file"] = str(Path(geometry_path).absolute())
            
            eng.workspace["output_dir"] = str(output_dir.absolute())
            eng.workspace["plots_dir"] = str(plots_dir.absolute())
            
            # Set simulation inputs
            for key, value in sim_config.inputs.items():
                eng.workspace[key] = value

            # Prepare entrypoint
            entrypoint = sim_config.matlab_entrypoint
            if entrypoint.endswith(".m"):
                entrypoint = entrypoint[:-2]  # Remove .m extension

            # Run simulation with timeout
            log_file = logs_dir / "matlab.txt"
            
            async def run_sim():
                """Run simulation in executor"""
                # Redirect diary to log file
                eng.diary(str(log_file), nargout=0)
                eng.diary("on", nargout=0)
                
                try:
                    # Run the entrypoint
                    eng.eval(f"run('{entrypoint}')", nargout=0)
                finally:
                    eng.diary("off", nargout=0)

            try:
                await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: run_sim()),
                    timeout=self.timeout,
                )
            except asyncio.TimeoutError:
                return SimulationResult(
                    success=False,
                    error=f"MATLAB simulation timeout ({self.timeout}s)",
                )

            # Read results from workspace or file
            result_file = output_dir / "result.json"
            metrics = {}
            
            if result_file.exists():
                # Preferred: MATLAB wrote results to JSON
                with open(result_file, "r") as f:
                    metrics = json.load(f)
            else:
                # Fallback: read from workspace
                for metric_name in sim_config.outputs_requested:
                    try:
                        value = eng.workspace[metric_name]
                        # Convert MATLAB types to Python
                        if hasattr(value, '__float__'):
                            metrics[metric_name] = float(value)
                        elif hasattr(value, '__int__'):
                            metrics[metric_name] = int(value)
                        else:
                            metrics[metric_name] = str(value)
                    except KeyError:
                        # Metric not found in workspace
                        pass

            # Collect plot files
            plot_files = list(plots_dir.glob("*.png")) + list(plots_dir.glob("*.jpg"))
            plots = [str(p.relative_to(output_dir)) for p in plot_files]

            # Collect log files
            log_files = list(logs_dir.glob("*.txt"))
            logs = [str(l.relative_to(output_dir)) for l in log_files]

            # Read warnings from MATLAB (if available)
            warnings = []
            if "warnings" in eng.workspace:
                try:
                    warnings = list(eng.workspace["warnings"])
                except Exception:
                    pass

            return SimulationResult(
                success=True,
                metrics=metrics,
                plots=plots,
                logs=logs,
                warnings=warnings,
            )

        except Exception as e:
            return SimulationResult(
                success=False,
                error=f"MATLAB runner exception: {str(e)}",
            )

    async def stop_engine(self):
        """Stop MATLAB engine"""
        if self._engine is not None:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._engine.quit)
            self._engine = None

    async def test_installation(self) -> bool:
        """Test if MATLAB Engine is installed and working"""
        try:
            import matlab.engine
            
            # Try to start engine with short timeout
            loop = asyncio.get_event_loop()
            eng = await asyncio.wait_for(
                loop.run_in_executor(None, matlab.engine.start_matlab),
                timeout=30,
            )
            await loop.run_in_executor(None, eng.quit)
            return True
        except Exception:
            return False


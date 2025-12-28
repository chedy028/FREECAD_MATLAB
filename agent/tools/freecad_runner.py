"""FreeCAD headless runner"""

import asyncio
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from agent.orchestrator.validators import CADConfig, CADResult


class FreeCADRunner:
    """Execute FreeCAD in headless mode"""

    def __init__(
        self,
        freecad_cmd: Optional[str] = None,
        timeout: int = 300,
        allowed_templates: Optional[List[str]] = None,
        allowed_formats: Optional[List[str]] = None,
        param_ranges: Optional[Dict[str, List[float]]] = None,
    ):
        self.freecad_cmd = freecad_cmd or self._detect_freecad_cmd()
        self.timeout = timeout
        self.allowed_templates = allowed_templates or ["parametric_enclosure_v1"]
        self.allowed_formats = allowed_formats or ["step", "stl"]
        self.param_ranges = param_ranges or {}

    def _detect_freecad_cmd(self) -> str:
        """Auto-detect FreeCAD CLI executable"""
        system = platform.system()

        # Check environment variable first
        env_path = os.getenv("FREECAD_PATH")
        if env_path and os.path.exists(env_path):
            return env_path

        # Platform-specific defaults
        if system == "Windows":
            candidates = [
                r"C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe",
                r"C:\Program Files\FreeCAD 0.21\bin\FreeCADCmd.exe",
                r"C:\Program Files\FreeCAD 0.20\bin\FreeCADCmd.exe",
            ]
        elif system == "Linux":
            candidates = [
                "/usr/bin/freecadcmd",
                "/usr/local/bin/freecadcmd",
            ]
        elif system == "Darwin":  # macOS
            candidates = [
                "/Applications/FreeCAD.app/Contents/MacOS/FreeCADCmd",
            ]
        else:
            candidates = []

        for candidate in candidates:
            if os.path.exists(candidate):
                return candidate

        raise RuntimeError(
            f"FreeCAD CLI not found. Set FREECAD_PATH env var or install FreeCAD."
        )

    def _validate_template(self, template: str) -> None:
        """Validate template against allowlist"""
        if template not in self.allowed_templates:
            raise ValueError(
                f"Template '{template}' not in allowlist: {self.allowed_templates}"
            )

    def _validate_format(self, fmt: str) -> None:
        """Validate export format"""
        if fmt not in self.allowed_formats:
            raise ValueError(f"Format '{fmt}' not in allowlist: {self.allowed_formats}")

    def _validate_params(self, params: Dict[str, float]) -> None:
        """Validate parameter ranges"""
        for key, value in params.items():
            if key in self.param_ranges:
                min_val, max_val = self.param_ranges[key]
                if not (min_val <= value <= max_val):
                    raise ValueError(
                        f"Parameter '{key}' = {value} outside range [{min_val}, {max_val}]"
                    )

    async def build_cad(
        self, cad_config: CADConfig, output_dir: Path
    ) -> CADResult:
        """
        Build CAD model using FreeCAD CLI.
        
        Args:
            cad_config: CAD configuration
            output_dir: Directory to write outputs
        
        Returns:
            CADResult with geometry path, bbox, volume, warnings
        """
        try:
            # Validate inputs
            self._validate_template(cad_config.template)
            self._validate_format(cad_config.export.format)
            self._validate_params(cad_config.params)

            # Prepare output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Template script path
            template_path = Path("cad_templates") / f"{cad_config.template}.py"
            if not template_path.exists():
                return CADResult(
                    success=False,
                    error=f"Template script not found: {template_path}",
                )

            # Output paths
            geometry_path = output_dir / cad_config.export.filename
            meta_path = output_dir / "cad_meta.json"

            # Build command-line arguments
            # Format: freecadcmd script.py -- --param value ...
            cmd = [
                self.freecad_cmd,
                str(template_path.absolute()),
                "--",
                "--output", str(geometry_path.absolute()),
                "--format", cad_config.export.format,
                "--meta", str(meta_path.absolute()),
            ]

            # Add parameters as --key value pairs
            for key, value in cad_config.params.items():
                cmd.extend([f"--{key}", str(value)])

            # Run FreeCAD
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(Path.cwd()),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return CADResult(
                    success=False,
                    error=f"FreeCAD execution timeout ({self.timeout}s)",
                )

            # Check return code
            if process.returncode != 0:
                return CADResult(
                    success=False,
                    error=f"FreeCAD exited with code {process.returncode}: {stderr.decode()}",
                )

            # Read metadata
            if not meta_path.exists():
                return CADResult(
                    success=False,
                    error="FreeCAD did not produce metadata file",
                )

            with open(meta_path, "r") as f:
                meta = json.load(f)

            # Verify geometry file exists
            if not geometry_path.exists():
                return CADResult(
                    success=False,
                    error=f"Geometry file not created: {geometry_path}",
                )

            return CADResult(
                success=True,
                path=str(geometry_path),
                bbox=meta.get("bbox"),
                volume=meta.get("volume"),
                warnings=meta.get("warnings", []),
            )

        except Exception as e:
            return CADResult(
                success=False,
                error=f"FreeCAD runner exception: {str(e)}",
            )

    async def test_installation(self) -> bool:
        """Test if FreeCAD is installed and working"""
        try:
            process = await asyncio.create_subprocess_exec(
                self.freecad_cmd,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
            return process.returncode == 0
        except Exception:
            return False


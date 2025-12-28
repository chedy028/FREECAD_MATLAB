"""
Simple cantilever beam design test (without LLM)
Demonstrates FreeCAD + MATLAB integration
"""

import asyncio
from pathlib import Path
from uuid import uuid4

from agent.config import load_config
from agent.orchestrator.validators import (
    CADConfig,
    CADExport,
    SimulationConfig,
)
from agent.tools.freecad_runner import FreeCADRunner
from agent.tools.matlab_runner import MATLABRunner


async def main():
    """Run simple cantilever beam test"""
    
    print("\n" + "="*70)
    print("CANTILEVER BEAM CAD + STRUCTURAL ANALYSIS TEST")
    print("="*70 + "\n")
    
    # Load config
    config = load_config()
    
    # Create run directory
    run_id = uuid4()
    run_dir = Path("runs") / str(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Run ID: {run_id}")
    print(f"Output directory: {run_dir}\n")
    
    # Step 1: Generate CAD with FreeCAD
    print("="*70)
    print("STEP 1: CAD GENERATION (FreeCAD)")
    print("="*70 + "\n")
    
    cad_config = CADConfig(
        template="cantilever_beam_v1",
        units="mm",
        params={
            "length": 200.0,   # 200mm cantilever
            "width": 20.0,     # 20mm wide
            "height": 10.0,    # 10mm tall
        },
        export=CADExport(format="step", filename="beam.step")
    )
    
    print(f"Beam dimensions: {cad_config.params['length']}mm × {cad_config.params['width']}mm × {cad_config.params['height']}mm")
    
    freecad = FreeCADRunner(
        allowed_templates=config.freecad.allowed_templates + ["cantilever_beam_v1"],
        allowed_formats=config.freecad.allowed_export_formats,
    )
    
    cad_dir = run_dir / "cad"
    cad_result = await freecad.build_cad(cad_config, cad_dir)
    
    if cad_result.success:
        print(f"✓ CAD Generation: SUCCESS")
        print(f"  Geometry file: {cad_result.path}")
        print(f"  Volume: {cad_result.volume:.2f} mm³")
        if cad_result.bbox:
            print(f"  Bounding box: {cad_result.bbox}")
    else:
        print(f"✗ CAD Generation: FAILED")
        print(f"  Error: {cad_result.error}")
        return
    
    # Step 2: Run structural analysis with MATLAB
    print("\n" + "="*70)
    print("STEP 2: STRUCTURAL ANALYSIS (MATLAB)")
    print("="*70 + "\n")
    
    sim_config = SimulationConfig(
        type="structural_static",
        matlab_entrypoint="run_cantilever_analysis.m",
        inputs={
            "force_N": 100.0,      # 100N load at free end
            "E_MPa": 69000.0,      # Aluminum Young's modulus
            "nu": 0.33,            # Aluminum Poisson's ratio
        },
        outputs_requested=[
            "max_stress_MPa",
            "max_deflection_mm",
            "mass_g",
            "safety_factor"
        ]
    )
    
    print(f"Applied load: {sim_config.inputs['force_N']} N")
    print(f"Material: Aluminum (E={sim_config.inputs['E_MPa']} MPa)")
    
    matlab = MATLABRunner(
        allowed_entrypoints=config.matlab.allowed_entrypoints + ["run_cantilever_analysis.m"],
        timeout=config.matlab.timeout_seconds,
    )
    
    sim_dir = run_dir / "simulation"
    sim_result = await matlab.run_matlab(sim_config, cad_result.path, sim_dir)
    
    if sim_result.success:
        print(f"\n✓ Structural Analysis: SUCCESS")
        print(f"\nResults:")
        for key, value in sim_result.metrics.items():
            if isinstance(value, (int, float)):
                print(f"  {key}: {value:.3f}")
            else:
                print(f"  {key}: {value}")
        
        if sim_result.plots:
            print(f"\nPlots generated:")
            for plot in sim_result.plots:
                print(f"  - {plot}")
    else:
        print(f"\n✗ Structural Analysis: FAILED")
        print(f"  Error: {sim_result.error}")
        return
    
    # Step 3: Evaluate results
    print("\n" + "="*70)
    print("STEP 3: EVALUATION")
    print("="*70 + "\n")
    
    max_stress = sim_result.metrics.get("max_stress_MPa", 0)
    max_deflection = sim_result.metrics.get("max_deflection_mm", 0)
    mass = sim_result.metrics.get("mass_g", 0)
    safety_factor = sim_result.metrics.get("safety_factor", 0)
    
    # Check constraints
    stress_ok = max_stress <= 200  # 200 MPa limit
    deflection_ok = max_deflection <= 2.0  # 2mm limit
    
    print(f"Constraints:")
    print(f"  Max stress:      {max_stress:.1f} MPa {'✓' if stress_ok else '✗'} (limit: 200 MPa)")
    print(f"  Max deflection:  {max_deflection:.3f} mm {'✓' if deflection_ok else '✗'} (limit: 2.0 mm)")
    print(f"  Safety factor:   {safety_factor:.2f}")
    print(f"\nObjective:")
    print(f"  Mass: {mass:.2f} g (minimize)")
    
    if stress_ok and deflection_ok:
        print(f"\n✓ All constraints satisfied!")
        print(f"  Next iteration: Try reducing dimensions to minimize mass")
    else:
        print(f"\n✗ Constraints violated!")
        if not stress_ok:
            print(f"  → Increase cross-section to reduce stress")
        if not deflection_ok:
            print(f"  → Increase beam height to reduce deflection")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70 + "\n")
    
    print(f"Run completed successfully!")
    print(f"\nFiles saved to: {run_dir.absolute()}")
    print(f"  - CAD model:     {cad_dir / 'beam.step'}")
    print(f"  - Results:       {sim_dir / 'result.json'}")
    print(f"  - Plots:         {sim_dir / 'plots'}")
    print(f"\nThis demonstrates ONE iteration of the autonomous loop.")
    print(f"The full agent would:")
    print(f"  1. Parse your requirements with LLM")
    print(f"  2. Generate initial design")
    print(f"  3. Run FEA analysis")
    print(f"  4. Evaluate constraints")
    print(f"  5. Adjust dimensions intelligently")
    print(f"  6. Repeat until converged\n")


if __name__ == "__main__":
    asyncio.run(main())


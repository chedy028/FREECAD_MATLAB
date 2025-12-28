# Cantilever Beam Design Request

Use this request with the API at http://127.0.0.1:8000/docs

## PowerShell Command:

```powershell
$beamRequest = @{
    message = @"
Design a cantilever beam for structural analysis. 

Requirements:
- Minimize mass while maintaining structural integrity
- Maximum stress must be ≤ 200 MPa (aluminum yield ~275 MPa, use safety factor)
- Maximum deflection must be ≤ 2 mm at free end
- Applied load: 100 N downward at free end
- Material: Aluminum (E=69 GPa, ν=0.33)
- Starting dimensions: 200mm length × 20mm width × 10mm height

Iterate to find optimal dimensions that minimize mass while meeting stress and deflection constraints.
"@
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" `
                  -Method POST `
                  -Body $beamRequest `
                  -ContentType "application/json"
```

## Or use curl:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Design a cantilever beam for structural analysis. Requirements: minimize mass, max stress ≤ 200 MPa, max deflection ≤ 2mm, 100N load, aluminum material. Start with 200mm × 20mm × 10mm."
  }'
```

## Expected Results:

The autonomous agent will:

1. **Iteration 1**: Generate initial beam (200×20×10mm)
   - Create CAD model with FreeCAD
   - Run structural FEA with MATLAB
   - Calculate stress, deflection, mass
   - Evaluate against constraints

2. **Iteration 2-N**: Optimize dimensions
   - If stress too high → increase cross-section
   - If deflection too high → increase height (most effective)
   - If both constraints met → reduce dimensions to minimize mass
   - Continue until converged

3. **Final Output**:
   - Optimized beam dimensions
   - von Mises stress distribution
   - Deflection plot
   - Mass calculation
   - Safety factor
   - All artifacts in `runs/<run_id>/`

## What Gets Analyzed:

- **Stress Analysis**: von Mises stress distribution
- **Deflection**: Maximum tip deflection
- **Mass**: Based on aluminum density (2.7 g/cm³)
- **Safety Factor**: Yield strength / Max stress

## View Results:

```powershell
# After the run completes
$latestRun = Get-ChildItem runs/ -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 1

# View results
explorer $latestRun.FullName

# Check plots
explorer "$($latestRun.FullName)\iter_000\simulation\plots\"
```

Files you'll find:
- `geometry.step` - CAD model
- `stress_distribution.png` - von Mises stress plot
- `deflection.png` - Deflection visualization
- `mesh.png` - FEA mesh
- `result.json` - All metrics


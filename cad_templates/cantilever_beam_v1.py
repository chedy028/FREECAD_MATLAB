"""
Parametric cantilever beam CAD template for FreeCAD.

Parameters:
  --length: Beam length (mm)
  --width: Beam width (mm)
  --height: Beam height (mm)
  --output: Output file path
  --format: Export format (step or stl)
  --meta: Metadata JSON output path
"""

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Generate parametric cantilever beam")
    parser.add_argument("--length", type=float, required=True, help="Beam length (mm)")
    parser.add_argument("--width", type=float, required=True, help="Beam width (mm)")
    parser.add_argument("--height", type=float, required=True, help="Beam height (mm)")
    parser.add_argument("--output", type=str, required=True, help="Output file path")
    parser.add_argument("--format", type=str, required=True, choices=["step", "stl"])
    parser.add_argument("--meta", type=str, required=True, help="Metadata JSON path")
    
    return parser.parse_args()


def build_cantilever_beam(length, width, height):
    """Build cantilever beam using FreeCAD"""
    import FreeCAD
    import Part

    # Create rectangular beam
    beam = Part.makeBox(length, width, height)
    
    return beam


def compute_bbox(shape):
    """Compute bounding box"""
    bbox = shape.BoundBox
    return {
        "xmin": bbox.XMin,
        "xmax": bbox.XMax,
        "ymin": bbox.YMin,
        "ymax": bbox.YMax,
        "zmin": bbox.ZMin,
        "zmax": bbox.ZMax,
    }


def compute_volume(shape):
    """Compute volume in mm³"""
    return shape.Volume


def main():
    """Main entry point"""
    args = parse_args()
    
    warnings = []
    
    try:
        # Build geometry
        beam = build_cantilever_beam(args.length, args.width, args.height)
        
        # Compute properties
        bbox = compute_bbox(beam)
        volume = compute_volume(beam)
        
        # Calculate mass (assuming aluminum: 2.7 g/cm³)
        density_g_per_mm3 = 0.0027  # 2.7 g/cm³ = 0.0027 g/mm³
        mass_g = volume * density_g_per_mm3
        
        # Export geometry
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if args.format == "step":
            beam.exportStep(str(output_path))
        elif args.format == "stl":
            beam.exportStl(str(output_path))
        else:
            raise ValueError(f"Unsupported format: {args.format}")
        
        # Write metadata
        meta = {
            "template": "cantilever_beam_v1",
            "params": {
                "length": args.length,
                "width": args.width,
                "height": args.height,
            },
            "bbox": bbox,
            "volume": volume,
            "mass_g": mass_g,
            "warnings": warnings,
        }
        
        meta_path = Path(args.meta)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        
        print(f"Successfully generated {args.format} geometry: {output_path}")
        print(f"Volume: {volume:.2f} mm³")
        print(f"Mass: {mass_g:.2f} g (aluminum)")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


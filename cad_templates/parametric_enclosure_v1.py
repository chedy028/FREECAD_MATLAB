"""
Parametric enclosure CAD template for FreeCAD.

Parameters:
  --L: Length (mm)
  --W: Width (mm)
  --H: Height (mm)
  --wall_t: Wall thickness (mm)
  --fillet_r: Fillet radius (mm), optional
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
    parser = argparse.ArgumentParser(description="Generate parametric enclosure")
    parser.add_argument("--L", type=float, required=True, help="Length (mm)")
    parser.add_argument("--W", type=float, required=True, help="Width (mm)")
    parser.add_argument("--H", type=float, required=True, help="Height (mm)")
    parser.add_argument("--wall_t", type=float, required=True, help="Wall thickness (mm)")
    parser.add_argument("--fillet_r", type=float, default=0.0, help="Fillet radius (mm)")
    parser.add_argument("--output", type=str, required=True, help="Output file path")
    parser.add_argument("--format", type=str, required=True, choices=["step", "stl"])
    parser.add_argument("--meta", type=str, required=True, help="Metadata JSON path")
    
    return parser.parse_args()


def build_enclosure(L, W, H, wall_t, fillet_r=0.0):
    """Build parametric enclosure using FreeCAD"""
    import FreeCAD
    import Part

    # Create outer box
    outer_box = Part.makeBox(L, W, H)
    
    # Create inner box (hollowed out)
    inner_L = L - 2 * wall_t
    inner_W = W - 2 * wall_t
    inner_H = H - wall_t  # Open top
    
    if inner_L <= 0 or inner_W <= 0 or inner_H <= 0:
        raise ValueError(f"Wall thickness too large for dimensions")
    
    inner_box = Part.makeBox(inner_L, inner_W, inner_H)
    inner_box.translate(FreeCAD.Vector(wall_t, wall_t, wall_t))
    
    # Cut inner from outer
    enclosure = outer_box.cut(inner_box)
    
    # Apply fillets if requested
    if fillet_r > 0:
        try:
            # Fillet all edges
            edges = enclosure.Edges
            enclosure = enclosure.makeFillet(fillet_r, edges)
        except Exception as e:
            # Fillet might fail for some geometries, continue without it
            print(f"Warning: Fillet failed: {e}", file=sys.stderr)
    
    return enclosure


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
        enclosure = build_enclosure(
            args.L, args.W, args.H, args.wall_t, args.fillet_r
        )
        
        # Compute properties
        bbox = compute_bbox(enclosure)
        volume = compute_volume(enclosure)
        
        # Export geometry
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if args.format == "step":
            enclosure.exportStep(str(output_path))
        elif args.format == "stl":
            enclosure.exportStl(str(output_path))
        else:
            raise ValueError(f"Unsupported format: {args.format}")
        
        # Write metadata
        meta = {
            "template": "parametric_enclosure_v1",
            "params": {
                "L": args.L,
                "W": args.W,
                "H": args.H,
                "wall_t": args.wall_t,
                "fillet_r": args.fillet_r,
            },
            "bbox": bbox,
            "volume": volume,
            "warnings": warnings,
        }
        
        meta_path = Path(args.meta)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        
        print(f"Successfully generated {args.format} geometry: {output_path}")
        print(f"Volume: {volume:.2f} mm³")
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())


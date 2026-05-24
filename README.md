# pip-hinge

A fully-parametric print-in-place piano hinge in [build123d](https://github.com/gumyr/build123d).

Lifted from a working FreeCAD design (`hinge-03.fcstd`) with every sketch coordinate
re-expressed as a function of named parameters. No magic numbers in the geometry.

## Quick start

```bash
uv pip install build123d
python hinge.py    # writes examples/hinge_default.{step,stl}
```

## Usage

```python
from hinge import HingeParams, make_hinge
from build123d import export_stl

# Default 40 × 30 × 10 mm hinge, 7 alternating knuckles, claspClearance=0.6
hinge = make_hinge()
export_stl(hinge, "hinge.stl")

# Scaled up 2x, with tighter clearance for fine-tuned printers
hinge = make_hinge(HingeParams(
    hinge_height=80, hinge_width=60,
    clasp_clearance=0.3, pivot_clearance=0.6,
))
```

## Parameters

| Parameter           | Default        | Meaning                                        |
| ------------------- | -------------- | ---------------------------------------------- |
| `hinge_height`      | 40             | Total length along the hinge axis (Y)          |
| `hinge_width`       | 30             | Depth of each leaf from the hinge axis (X)     |
| `hinge_thickness`   | 5              | Leaf paddle thickness (Z)                      |
| `pivot_inner`       | 5              | Bore diameter                                  |
| `pivot_outer`       | 2 × inner      | Knuckle diameter                               |
| `pivot_clearance`   | 1.0            | Radial pin/bore gap                            |
| `clasp_width`       | hinge_height/6 | Comb tooth width along Y                       |
| `clasp_clearance`   | 0.6            | Y-axis gap between meshing teeth               |
| `clasp_center`      | hinge_height/3 | Used in pin centring                           |
| `pin_cyl_extra`     | 1.5            | Pin cyl length excess over `clasp_width`       |
| `pin_end_offset`    | 0.5            | Pin tip offset inside the end-tab              |
| `pin_short_cyl_factor` | 1/3         | Short-cylinder length as fraction of clasp_width |

The default produces a hinge bit-for-bit identical to translating
`hinge-03.fcstd` (with the printable `claspClearance=0.6`) via fcstd2b123d:
`cylinder_side=6060.7 mm³`, `pin_side=6728.9 mm³`, 0.3 mm clearance everywhere.

## Printing

Lay flat on the bed with the hinge axis along Y (parallel to bed). Print at 0.2 mm
layers, fan on, brim recommended. After printing, gently flex the leaves to break
the 0.3 mm clearance gaps free. No supports needed — the 5 mm-radius knuckle
crowns prints with the usual minor layer ridges on the top arc, but stays
within typical FDM overhang tolerance.

## Provenance

This is a direct port of the comb-tooth piano hinge in `hinge-03.fcstd`. The
spreadsheet-driven FreeCAD original used these parameter relations:

- `pivot_outer = pivot_inner * 2`
- `clasp_width = hinge_height / 6`
- `clasp_center = hinge_height / 3`

Three small constants in the pin sketch (`pin_cyl_extra=1.5`, `pin_end_offset=0.5`,
`pin_short_cyl_factor=1/3`) were hand-tuned by the original designer for pin/bore
engagement and don't follow a derivation from the size parameters. They're exposed
as tunables — leave at defaults unless you know what you're adjusting.

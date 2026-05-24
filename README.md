# pip-hinge

A fully-parametric print-in-place piano hinge in [build123d](https://github.com/gumyr/build123d).

Lifted from a FreeCAD design with every sketch coordinate re-expressed as a function of
named parameters. No magic numbers in the geometry.

## Provenance

This is a port of **["Parametric print-in-place hinge. FreeCAD."](https://www.printables.com/model/1395662-parametric-print-in-place-hinge-freecad)**
by **[r0berts](https://www.printables.com/@r0berts_1183620)** on Printables,
licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The original is a spreadsheet-driven FreeCAD model (`hinge-03.fcstd`); r0berts notes
they followed [this YouTube tutorial](https://www.youtube.com/watch?v=BD_iP7djo7Q)
to build it. This repository:

1. Translates the FreeCAD geometry into build123d Python via
   [fcd2b123d](https://github.com/pzfreo/fcd2b123d).
2. Replaces every literal sketch coordinate with a derivation from the FreeCAD
   spreadsheet parameters (`hingeHeight`, `hingeWidth`, `pivotInner`, `pivotOuter`,
   `pivotClearance`, `claspWidth`, `claspClearance`, `claspCenter`), so the design
   is genuinely parametric end-to-end rather than only at the top level.
3. Bumps `claspClearance` from the original 0.2 mm (too tight for typical FDM) to
   0.6 mm by default, giving 0.3 mm of axial gap per side — printable on a standard
   PLA-tuned printer without supports.

Per the CC BY 4.0 terms, modifications include the geometry reparameterisation and
the build123d port; the underlying design and dimensional relationships are r0berts'.

## Quick start

```bash
uv pip install build123d
python hinge.py    # writes examples/hinge_default.{step,stl}
```

## Usage

```python
from hinge import HingeParams, make_hinge
from build123d import export_stl

# Default 40 × 30 × 10 mm hinge, printable on FDM
hinge = make_hinge()
export_stl(hinge, "hinge.stl")

# Scaled up, with tighter clearance for a fine-tuned printer
hinge = make_hinge(HingeParams(
    hinge_height=80, hinge_width=60,
    clasp_clearance=0.3, pivot_clearance=0.6,
))
```

## Parameters

The six you'll typically change:

| Parameter         | Default | Meaning                                                  |
| ----------------- | ------- | -------------------------------------------------------- |
| `hinge_height`    | 40      | Total length along the hinge axis (Y)                    |
| `hinge_width`     | 30      | Depth of each leaf from hinge axis to outer edge (X)     |
| `hinge_thickness` | 5       | Leaf paddle thickness (Z)                                |
| `pivot_inner`     | 5       | Bore diameter                                            |
| `pivot_clearance` | 1.0     | Radial pin/bore gap                                      |
| `clasp_clearance` | 0.6     | Y-axis gap between meshing teeth (the FDM tolerance)     |

Derived defaults (override only if you know what you're doing):

| Parameter      | Default            | Notes                                          |
| -------------- | ------------------ | ---------------------------------------------- |
| `pivot_outer`  | `2 × pivot_inner`  | Knuckle diameter                               |
| `clasp_width`  | `hinge_height / 6` | Comb tooth width along Y                       |
| `clasp_center` | `hinge_height / 3` | Used in pin centring                           |

Three pin-engagement constants from the original design (`pin_cyl_extra=1.5`,
`pin_end_offset=0.5`, `pin_short_cyl_factor=1/3`) were hand-tuned by r0berts for
pin/bore feel — exposed as tunables, leave at defaults unless deliberately tuning.

## Default verification

The defaults reproduce r0berts' geometry bit-for-bit (with `claspClearance` set to
the printable 0.6 mm value):

```
cylinder_side vol = 6060.7123 mm³
pin_side vol      = 6728.8937 mm³
inter-leaf clearance = 0.3 mm everywhere
```

## Printing

Lay flat on the bed with the hinge axis along Y (parallel to bed). Print at 0.2 mm
layers, fan on, brim recommended. After printing, gently flex the leaves to break
the 0.3 mm clearance gaps free. No supports needed — the 5 mm-radius knuckle crowns
print with minor layer ridges on the top arc but stay within typical FDM overhang
tolerance.

## License

This work is licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/),
matching the upstream Printables source. See [LICENSE](LICENSE).

When using or redistributing, please credit:

- **r0berts** — original FreeCAD design ([Printables](https://www.printables.com/model/1395662-parametric-print-in-place-hinge-freecad))
- **Paul Fremantle** (pzfreo) — build123d port and parameterisation

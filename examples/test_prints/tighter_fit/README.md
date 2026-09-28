# Tighter conical-hinge fit trial

This trial followed the [original plate](../README.md), which released but
had noticeable rocking around both pins. The small case also slid along the
hinge axis. Both tighter cases have now printed successfully. The
[combined STL](conical_clamshell_pair.stl) contains the same two case sizes,
both with `Knuckle.SMALL` and `PinStyle.CONICAL`. `pivot_clearance` changes
from 0.6 to 0.4 mm on both cases, so the modeled radial pin-to-bore gap
drops from 0.3 to **0.2 mm**. The small case's axial tab gap drops from
0.3 to **0.2 mm**; the large case keeps the proven **0.3 mm** axial gap.

| Case | Half footprint | Hinge length | Radial gap | Axial gap | Individual STL |
| --- | --- | ---: | ---: | ---: | --- |
| Small | 35 × 28 mm | 24 mm | 0.2 mm | 0.2 mm | [STL](conical_clamshell_small.stl) |
| Large | 60 × 42 mm | 48 mm | 0.2 mm | 0.3 mm | [STL](conical_clamshell_large.stl) |

The combined plate occupies about **158.1 × 60 mm** before any brim. To save
material, print the small case alone first. Keep the same material, slicer
settings, and orientation used for the original print; use 100% scale and no
generated supports. Inspect the pin gaps in the slicer preview. These two
prints supplied the evidence for `FitProfile.TIGHT`; try the small case first
when testing on a different printer.
The [combined STEP](conical_clamshell_pair.step) and individual STEP files
are for CAD inspection.

After cooling, compare the new small case against the original: does the
hinge release, rotate through its range without binding, and rock less when
the lid is lifted at its far edge? Check whether the small lid also slides
less along the hinge axis. A 0.2 mm modeled gap can still fuse on another
printer, so do not treat CAD validity or one successful setup as a guarantee.

Regenerate these files from the repository root:

```bash
.venv/bin/python examples/conical_test_print.py --fit tighter
```

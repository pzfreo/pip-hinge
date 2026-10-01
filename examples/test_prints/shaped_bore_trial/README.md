# Shaped conical bore trial — unprinted

This small clamshell tests the revised conical bore. The bore follows the pin's
straight shank and 45° tip, leaving a 0.2 mm modeled gap normal to the cone.
This may reduce rocking compared with the earlier cylindrical bore, but that
has **not** been verified by a physical print. The [earlier tighter-fit
plate](../tighter_fit/README.md) is the one that printed successfully; its
STL uses the original cylindrical bore and remains available for comparison.

The trial uses `Knuckle.SMALL`, a 24 mm hinge with four stations, and
`FitProfile.TIGHT`. Its case halves each measure 35 × 28 × 6 mm. Print the
[STL](conical_shaped_bore_small.stl) at 100% scale, flat on the bed with the
open sides up and generated supports off. Start with a 0.4 mm nozzle and
0.2 mm layers; check the bore and pin in the slicer preview before printing.
The [STEP file](conical_shaped_bore_small.step) is for CAD inspection.

After cooling, check that the hinge releases and rotates without binding.
Compare lid rocking and axial sliding against the earlier tighter-fit print.
Record printer, material, nozzle, line width, layer height, and slicer settings
alongside the result. A valid CAD clearance does not guarantee release.

Regenerate from the repository root:

```bash
.venv/bin/python examples/conical_bore_trial.py
```

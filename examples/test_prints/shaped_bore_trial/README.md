# Shaped conical bore trial — printed

This small clamshell tests the revised conical bore. The bore follows the pin's
straight shank and 45° tip, leaving a 0.2 mm modeled gap normal to the cone.
The printed small case released and the hinge felt good. In the same print, a
small `BRIDGED` case with a teardrop-roof bore also released, but was very
loose and rocked around its pin. This is one print result, not a fit guarantee
for other sizes or printers. The [earlier tighter-fit
plate](../tighter_fit/README.md) is the one that printed successfully; its
STL uses the original cylindrical bore and remains available for comparison.

The comparison used the same 24 mm, four-station SMALL hinge on both cases.
The conical case used `FitProfile.TIGHT` (0.2 mm radial and axial gaps); the
bridged case used `FitProfile.STANDARD` (0.3 mm radial and axial gaps). Printer,
material, line width, and layer height were not recorded with this result.

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

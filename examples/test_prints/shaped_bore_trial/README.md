# Shaped conical bore trial — printed

This small clamshell tests the revised conical bore. The bore follows the pin's
straight shank and 45° tip, leaving a 0.2 mm modeled gap normal to the cone.
The printed small case released and the hinge felt good. In the same print, a
small `BRIDGED` case with a teardrop-roof bore also released, but was very
loose and rocked around its pin. This is one print result, not a fit guarantee
for other sizes or printers. The [earlier tighter-fit
plate](../tighter_fit/README.md) also printed successfully; its
STL uses the original cylindrical bore and remains available for comparison.

The comparison used the same 24 mm, four-station SMALL hinge on both cases.
The conical case used `FitProfile.TIGHT` (0.2 mm radial and axial gaps); the
bridged case used `FitProfile.STANDARD` (0.3 mm radial and axial gaps). Printer,
material, line width, and layer height were not recorded with this result.
The teardrop roof leaves about 0.74 mm of modeled space above the bridged
pin at its peak, which helps explain the rocking despite the 0.3 mm gap at
the round sides.

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
python examples/conical_bore_trial.py
```

To reproduce **both** printed cases from Python, including the two dots that
mark the bridged base, run:

```bash
python examples/shaped_bore_pair.py
```

This writes individual STEP files and a 130 × 35 mm pair with a 6 mm gap in
the current directory: conical on the left, bridged on the right. The script
defaults to the printed gaps above; it does not change the library's default
fit settings.

If the pin fuses to its bore, try increasing only that case's radial gap by
0.05 mm, for example `--conical-radial-gap 0.25`. The script sets
`pivot_clearance` to twice the requested radial gap. If adjacent knuckle
faces fuse, increase that case's axial gap by 0.05–0.1 mm, for example
`--conical-axial-gap 0.25`. For the bridged case, inspect the unsupported
pin spans and bore roof in the slicer and check its bridge settings; more
clearance may release it but will add to its already noticeable play.

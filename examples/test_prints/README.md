# Conical-pin clamshell test print

The [combined STL](conical_clamshell_pair.stl) contains two flat-open,
print-in-place clamshells, side by side with a 6 mm gap. Both use explicit
`PinStyle.CONICAL`, `Knuckle.SMALL`, and the library's default 0.3 mm axial
tab gap and 0.3 mm radial pin-to-bore gap.
The small knuckle is 5.0 mm in diameter on the smaller case and 5.1 mm on
the larger case.

Both cases have now been physically printed: the hinges released and worked,
but their rocking play was more than expected. The small case also slid along
the hinge axis. A [tighter fit trial](tighter_fit/README.md) subsequently
printed well: it reduces the radial pin gap on both cases and the axial tab
gap on the small case. Keep this original plate as the baseline for comparison.
These exported files retain the earlier cylindrical bore. The current code
uses a shaped conical bore; the [new small trial](shaped_bore_trial/README.md)
tested that change and printed well. The prints were on a **Bambu Lab P1S**.
The nozzle and layer values below are suggested starting settings, not a
record of the successful printer setup; material, nozzle diameter, line
width, layer height, and slicer profile were not captured.

| Case | Half footprint | Wall height | Hinge length | Stations | Flat-open footprint |
| --- | --- | ---: | ---: | ---: | --- |
| [Small](conical_clamshell_small.stl) | 35 × 28 mm | 6 mm | 24 mm | 4 | 62.0 × 35 mm |
| [Large](conical_clamshell_large.stl) | 60 × 42 mm | 10 mm | 48 mm | 6 | 90.1 × 60 mm |

The combined footprint is about **158.1 × 60 mm** before any brim. Import
the combined STL once, keep its open sides facing up and its flat bottoms on
the bed, and print without generated supports. Start at 0.2 mm layers with a
0.4 mm nozzle, and leave the slicer scale at 100%. Start without a brim; if
adhesion needs one, keep it at 2 mm or less and inspect the hinge gaps in the
slicer preview. The [STEP assembly](conical_clamshell_pair.step) is provided for CAD
inspection; use the STL for slicing.

After cooling, gently move each lid to free the print-in-place clearance.
Record whether each hinge releases, whether it rotates without binding, and
whether the lids close without a gap caused by the hinge. CAD checks cannot
predict all printer effects, so treat this as a fit test before printing a
larger case.

The command below exports the **current** geometry and will replace these
historical test files if run in this directory. To reproduce the original
exports exactly, run it from commit `502896f` instead.

From the repository root:

```bash
.venv/bin/python examples/conical_test_print.py
```

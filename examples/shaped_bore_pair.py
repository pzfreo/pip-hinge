"""Export the two small clamshells from the successful shaped-bore print.

Run from the repository root with ``python examples/shaped_bore_pair.py``.
The bridged base has two raised dots to distinguish it after printing.
"""

import argparse
from pathlib import Path

from build123d import Align, Compound, Cylinder, Pos, export_step

from conical_test_print import SMALL, case_half
from pip_hinge import Knuckle, PinStyle, PrintInPlaceHinge


def make_case(style: PinStyle, radial_gap: float, axial_gap: float) -> Compound:
    """Build one case; radial_gap is half of pivot_clearance."""
    hinge = PrintInPlaceHinge(
        case_h=SMALL.wall_height,
        hinge_length=SMALL.hinge_length,
        stations=SMALL.stations,
        knuckle=Knuckle.SMALL,
        pin_style=style,
        pivot_clearance=2 * radial_gap,
        clasp_clearance=axial_gap,
    )
    base = case_half(SMALL, +1, hinge.leaf_width) + hinge.cylinder_side
    lid = case_half(SMALL, -1, hinge.leaf_width) + hinge.pin_side
    if style is PinStyle.BRIDGED:
        marker_x = hinge.leaf_width + SMALL.depth - SMALL.wall - 4
        for marker_y in (-3, 3):
            base += Pos(marker_x, marker_y, SMALL.wall) * Cylinder(
                1.2, 0.8, align=(Align.CENTER, Align.CENTER, Align.MIN)
            )
    case = Compound([base, lid])
    if not case.is_valid or len(case.solids()) != 2:
        raise RuntimeError(f"{style.name} case must have two valid, separate leaves")
    return case


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conical-radial-gap", type=float, default=0.2)
    parser.add_argument("--conical-axial-gap", type=float, default=0.2)
    parser.add_argument("--bridged-radial-gap", type=float, default=0.3)
    parser.add_argument("--bridged-axial-gap", type=float, default=0.3)
    parser.add_argument("--out", type=Path, default=Path.cwd())
    args = parser.parse_args()

    conical = make_case(PinStyle.CONICAL, args.conical_radial_gap,
                        args.conical_axial_gap)
    bridged = make_case(PinStyle.BRIDGED, args.bridged_radial_gap,
                        args.bridged_axial_gap)
    # Each case is 62 mm wide. Leave 6 mm between them, conical on the left.
    spacing = 6.0
    shift = (conical.bounding_box().size.X + spacing) / 2
    pair = Compound([Pos(-shift, 0, 0) * conical,
                     Pos(shift, 0, 0) * bridged])
    if not pair.is_valid or len(pair.solids()) != 4:
        raise RuntimeError("pair must have four valid, separate leaves")

    args.out.mkdir(parents=True, exist_ok=True)
    export_step(conical, str(args.out / "conical_shaped_bore_small.step"))
    export_step(bridged, str(args.out / "bridged_shaped_bore_small.step"))
    export_step(pair, str(args.out / "conical_bridged_small_pair.step"))
    print(f"exported two cases and pair to {args.out}; "
          f"pair {pair.bounding_box().size.X:.1f} × "
          f"{pair.bounding_box().size.Y:.1f} mm")


if __name__ == "__main__":
    main()

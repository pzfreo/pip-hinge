"""Export two sizes of clamshell for a conical-pin print test.

Run from the repository root with ``.venv/bin/python examples/conical_test_print.py``.
Use ``--fit tighter`` to test less play on the same cases.
The cases are laid flat, open side up, with a 6 mm gap between them.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path

from build123d import Align, Box, Compound, Pos, export_step, export_stl

from pip_hinge import Knuckle, PinStyle, PrintInPlaceHinge


@dataclass(frozen=True)
class CaseSize:
    name: str
    width: float      # Y direction, mm
    depth: float      # X direction, mm, for each closed half
    wall_height: float
    wall: float
    hinge_length: float
    stations: int


SMALL = CaseSize("small", 35, 28, 6, 2, 24, 4)
LARGE = CaseSize("large", 60, 42, 10, 2.5, 48, 6)
BED_GAP = 6.0


def case_half(size: CaseSize, sign: int, leaf_width: float):
    """Make an open-top tray extending from the hinge in the X direction."""
    x_min = leaf_width if sign > 0 else -leaf_width - size.depth
    align = (Align.MIN, Align.CENTER, Align.MIN)
    outer = Pos(x_min, 0, 0) * Box(
        size.depth, size.width, size.wall_height, align=align
    )
    inner = Pos(x_min + size.wall, 0, size.wall) * Box(
        size.depth - 2 * size.wall,
        size.width - 2 * size.wall,
        size.wall_height - size.wall,
        align=align,
    )
    return outer - inner


def build_case(
    size: CaseSize,
    pivot_clearance: float = 0.6,
    clasp_clearance: float | None = None,
) -> Compound:
    hinge = PrintInPlaceHinge(
        case_h=size.wall_height,
        hinge_length=size.hinge_length,
        stations=size.stations,
        knuckle=Knuckle.SMALL,
        pin_style=PinStyle.CONICAL,
        pivot_clearance=pivot_clearance,
        clasp_clearance=clasp_clearance,
    )
    base = case_half(size, +1, hinge.leaf_width) + hinge.cylinder_side
    lid = case_half(size, -1, hinge.leaf_width) + hinge.pin_side
    return Compound([base, lid])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fit", choices=("baseline", "tighter"), default="baseline",
        help="baseline uses 0.3 mm gaps; tighter reduces the gaps with observed play",
    )
    args = parser.parse_args()
    pivot_clearance = 0.6 if args.fit == "baseline" else 0.4
    out = Path(__file__).parent / "test_prints"
    if args.fit == "tighter":
        out /= "tighter_fit"
    out.mkdir(parents=True, exist_ok=True)
    cases = []
    for size in (SMALL, LARGE):
        clasp_clearance = 0.2 if args.fit == "tighter" and size is SMALL else None
        case = build_case(
            size,
            pivot_clearance=pivot_clearance,
            clasp_clearance=clasp_clearance,
        )
        if not case.is_valid or len(case.solids()) != 2:
            raise RuntimeError(f"{size.name} case is not two valid, separate leaves")
        if abs(case.bounding_box().min.Z) > 1e-6:
            raise RuntimeError(f"{size.name} case does not rest on Z=0")
        stem = out / f"conical_clamshell_{size.name}"
        export_step(case, str(stem) + ".step")
        export_stl(case, str(stem) + ".stl")
        cases.append(case)
        print(f"{size.name}: {case.bounding_box().size.X:.1f} × "
              f"{case.bounding_box().size.Y:.1f} × "
              f"{case.bounding_box().size.Z:.1f} mm; {len(case.solids())} solids")

    small, large = cases
    small_width = small.bounding_box().size.X
    large_width = large.bounding_box().size.X
    plate_width = small_width + BED_GAP + large_width
    small_x = -plate_width / 2 + small_width / 2
    large_x = plate_width / 2 - large_width / 2
    plate = Compound([
        Pos(small_x, 0, 0) * small,
        Pos(large_x, 0, 0) * large,
    ])
    if not plate.is_valid or len(plate.solids()) != 4:
        raise RuntimeError("plate is not four valid, separate leaves")
    export_step(plate, str(out / "conical_clamshell_pair.step"))
    export_stl(plate, str(out / "conical_clamshell_pair.stl"))
    print(f"plate: {plate.bounding_box().size.X:.1f} × "
          f"{plate.bounding_box().size.Y:.1f} × "
          f"{plate.bounding_box().size.Z:.1f} mm; {len(plate.solids())} solids")


if __name__ == "__main__":
    main()

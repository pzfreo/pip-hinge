"""Worked example: a small clamshell box with an integrated print-in-place hinge.

Generates two variants (one per knuckle option) to make the geometric
difference visible:

  examples/clamshell_full.{step,stl}   — Knuckle.FULL, bump-on-top knuckle
  examples/clamshell_half.{step,stl}   — Knuckle.HALF, smaller knuckle + ramp

Both halves are coplanar on the bed (Z = 0), with the hinge axis along Y
through (X = 0, Z = case_h). Base extends in +X, lid in −X. Print as one
piece — no supports needed for either variant.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build123d import Align, Box, Compound, export_step, export_stl

from hinge import HingeParams, Knuckle, make_hinge


# ── case dimensions ───────────────────────────────────────────────────────
CASE_H = 10.0           # wall height (mm)
CASE_W = 80.0           # width along the hinge axis (Y)
CASE_D = 50.0           # depth front-to-back (X), per half
WALL_T = 2.5            # wall thickness
HINGE_LENGTH = 60.0     # leave ~10mm of solid wall at each Y end
STATIONS = 6


def hollow_half(x_sign: int, leaf_outer_x: float):
    """Open-top box, half extends in given X sign from the hinge axis.

    ``leaf_outer_x`` is where the case back wall sits (= W from HingeParams).
    """
    x_min = x_sign * leaf_outer_x if x_sign > 0 else x_sign * (leaf_outer_x + CASE_D)
    align = (Align.MIN, Align.CENTER, Align.MIN)
    outer = Box(CASE_D, CASE_W, CASE_H, align=align).translate((x_min, 0, 0))
    inner = Box(
        CASE_D - 2 * WALL_T, CASE_W - 2 * WALL_T, CASE_H - WALL_T,
        align=align,
    ).translate((x_min + WALL_T, 0, WALL_T))
    return outer - inner


def build_clamshell(knuckle: Knuckle):
    params = HingeParams(
        case_h=CASE_H,
        hinge_length=HINGE_LENGTH,
        stations=STATIONS,
        knuckle=knuckle,
    )
    # leaf outer face at X = Ro + mounting_flat
    leaf_outer = CASE_H * knuckle.value / 100 + params.mounting_flat

    cs, ps = make_hinge(params).solids()
    cs = cs.translate((0, 0, CASE_H))    # axis sits on top of base wall
    ps = ps.translate((0, 0, CASE_H))

    base = hollow_half(+1, leaf_outer) + cs
    lid = hollow_half(-1, leaf_outer) + ps
    return Compound([base, lid])


def main():
    out = Path(__file__).parent
    for name, knuckle in [("clamshell_full", Knuckle.FULL), ("clamshell_half", Knuckle.HALF)]:
        clamshell = build_clamshell(knuckle)
        stem = out / name
        export_step(clamshell, str(stem) + ".step")
        export_stl(clamshell, str(stem) + ".stl")
        print(f"Exported {stem}.step / .stl")


if __name__ == "__main__":
    main()

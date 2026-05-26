"""Worked example: small clamshell boxes with an integrated print-in-place hinge.

Generates three variants:

  examples/clamshell_full.{step,stl}     — Knuckle.FULL, bump-on-top knuckle
  examples/clamshell_half.{step,stl}     — Knuckle.HALF, smaller knuckle + ramp
  examples/clamshell_magnets.{step,stl}  — Knuckle.HALF + 4 corner magnet pockets,
                                            a useful little case on its own

All three share two settings that came out of real printing & assembly:

  PIVOT_Z_OFFSET = 0.2 mm
      Raises the hinge axis 0.2 mm above the wall top. The closed lid then
      sits 2·δ = 0.4 mm above the base instead of meeting it on a 0-tolerance
      plane, so a high spot anywhere along the seam doesn't spring the
      front jaw open. Without this the case rests slightly open under its
      own elastic tension; with it, the front closes cleanly (and magnets,
      if fitted, latch it shut).

      The HingeParams call below uses ``case_h = WALL_H + PIVOT_Z_OFFSET``
      rather than ``WALL_H``. This sizes the knuckle to the pivot height
      rather than the wall height, so the knuckle bottom always lands on
      the bed (= the FULL-knuckle "rests on bed, no support" guarantee
      still holds even with the offset). The wall stays WALL_H tall; the
      leaf top sits OFFSET above the wall, which is exactly what raising
      the pivot means.

  MAGNET pockets (6 × 3 mm) at the four front corners of the magnet
      variant. The pockets sit inside cylindrical bosses pushed into the
      interior corners so the boss radius fillets the wall corner —
      visually a solid rounded corner rather than a free-standing pillar.
      Install lid magnets with the opposite polarity to the base magnets,
      or they'll repel when closed.

Both halves are coplanar on the bed (Z = 0), with the hinge axis along Y
through (X = 0, Z = case_h + PIVOT_Z_OFFSET). Base extends in +X, lid in −X.
Print as one piece — no supports needed.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from build123d import Align, Box, Compound, Cylinder, export_step, export_stl

from hinge import HingeParams, Knuckle, make_hinge


# ── case dimensions ───────────────────────────────────────────────────────
WALL_H = 10.0           # actual wall height of one case half
CASE_W = 80.0
CASE_D = 50.0
WALL_T = 2.5
HINGE_LENGTH = 60.0
STATIONS = 6

# ── empirical tweak: see module docstring ─────────────────────────────────
PIVOT_Z_OFFSET = 0.2
HINGE_WALL_H = WALL_H + PIVOT_Z_OFFSET    # passed to HingeParams

# ── magnet pocket geometry (6 mm × 3 mm neodymium discs) ──────────────────
MAGNET_R = 3.0
MAGNET_D = 3.0
BOSS_R = MAGNET_R + 1.5            # 1.5 mm of wall around the magnet


def hollow_half(x_sign: int, leaf_outer_x: float):
    """Open-top box, half extends in given X sign from the hinge axis."""
    x_min = x_sign * leaf_outer_x if x_sign > 0 else x_sign * (leaf_outer_x + CASE_D)
    align = (Align.MIN, Align.CENTER, Align.MIN)
    outer = Box(CASE_D, CASE_W, WALL_H, align=align).translate((x_min, 0, 0))
    inner = Box(
        CASE_D - 2 * WALL_T, CASE_W - 2 * WALL_T, WALL_H - WALL_T,
        align=align,
    ).translate((x_min + WALL_T, 0, WALL_T))
    return outer - inner


def add_corner_magnet_pockets(half, x_sign: int, leaf_outer_x: float):
    """Add 6 × 3 mm magnet pockets at the two front corners.

    Each boss is positioned along the diagonal from the interior corner so
    it is tangent to the corner — after fusion with the case walls the boss
    radius shows up as a quarter-circle fillet on the inside of the case.
    """
    x_corner = x_sign * (leaf_outer_x + CASE_D - WALL_T)
    for y_sign in (-1, +1):
        y_corner = y_sign * (CASE_W / 2 - WALL_T)
        x_boss = x_corner - x_sign * BOSS_R / math.sqrt(2)
        y_boss = y_corner - y_sign * BOSS_R / math.sqrt(2)
        boss = Cylinder(
            radius=BOSS_R, height=WALL_H,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        ).translate((x_boss, y_boss, 0))
        pocket = Cylinder(
            radius=MAGNET_R, height=MAGNET_D + 0.05,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        ).translate((x_boss, y_boss, WALL_H - MAGNET_D))
        half = (half + boss) - pocket
    return half


def build_clamshell(knuckle: Knuckle, magnets: bool = False):
    params = HingeParams(
        case_h=HINGE_WALL_H,                    # = WALL_H + PIVOT_Z_OFFSET
        hinge_length=HINGE_LENGTH,
        stations=STATIONS,
        knuckle=knuckle,
    )
    leaf_outer = HINGE_WALL_H * knuckle.value / 100 + params.mounting_flat

    cs, ps = make_hinge(params).solids()
    cs = cs.translate((0, 0, HINGE_WALL_H))    # pivot sits OFFSET above wall top
    ps = ps.translate((0, 0, HINGE_WALL_H))

    base = hollow_half(+1, leaf_outer) + cs
    lid = hollow_half(-1, leaf_outer) + ps
    if magnets:
        base = add_corner_magnet_pockets(base, +1, leaf_outer)
        lid = add_corner_magnet_pockets(lid, -1, leaf_outer)
    return Compound([base, lid])


def main():
    out = Path(__file__).parent
    variants = [
        ("clamshell_full", Knuckle.FULL, False),
        ("clamshell_half", Knuckle.HALF, False),
        ("clamshell_magnets", Knuckle.HALF, True),
    ]
    for name, knuckle, magnets in variants:
        clamshell = build_clamshell(knuckle, magnets=magnets)
        stem = out / name
        export_step(clamshell, str(stem) + ".step")
        export_stl(clamshell, str(stem) + ".stl")
        print(f"Exported {stem}.step / .stl")


if __name__ == "__main__":
    main()

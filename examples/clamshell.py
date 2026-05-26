"""Worked example: small clamshell boxes with an integrated print-in-place hinge.

Generates four variants:

  examples/clamshell_full.{step,stl}     — Knuckle.FULL, bump-on-top knuckle
  examples/clamshell_half.{step,stl}     — Knuckle.HALF, smaller knuckle + ramp
  examples/clamshell_small.{step,stl}    — Knuckle.SMALL, smallest printable
                                            knuckle (1/4 of FULL, floored at
                                            Po = 5 mm). Default mounting_flat
                                            (0.5 mm); the smaller knuckle
                                            naturally gives a steeper, more
                                            self-supporting ramp.
  examples/clamshell_magnets.{step,stl}  — Knuckle.HALF + 4 corner magnet pockets,
                                            a useful little case on its own

All three share two settings that came out of real printing & assembly:

  pivot_z_offset = 0.2 mm  (default on HingeParams)
      Raises the hinge axis 0.2 mm above the wall top. The closed lid
      then sits 2·δ = 0.4 mm above the base instead of meeting it on a
      0-tolerance plane, so a high spot anywhere along the seam doesn't
      spring the front jaw open. Without this the case rests slightly
      open under its own elastic tension; with it, the front closes
      cleanly (and magnets, if fitted, latch it shut).

      The HingeParams call below passes ``case_h = WALL_H`` (the actual
      wall height) and relies on the default ``pivot_z_offset = 0.2`` to
      handle the lift. The hinge internally extends the leaf by
      pivot_z_offset and lifts the disc so the axis sits at
      ``WALL_H + pivot_z_offset`` once the hinge is positioned at the
      wall top.

  MAGNET pockets (6 × 3 mm) at the four front corners of the magnet
      variant. The pockets sit inside cylindrical bosses pushed into the
      interior corners so the boss radius fillets the wall corner —
      visually a solid rounded corner rather than a free-standing pillar.
      Install lid magnets with the opposite polarity to the base magnets,
      or they'll repel when closed.

Both halves are coplanar on the bed (Z = 0), with the hinge axis along Y
through (X = 0, Z = WALL_H + pivot_z_offset). Base extends in +X, lid
in −X. Print as one piece — no supports needed.
"""

from __future__ import annotations

import math
from pathlib import Path

from build123d import Align, Box, Compound, Cylinder, export_step, export_stl

from pip_hinge import HingeParams, Knuckle, make_hinge


# ── case dimensions ───────────────────────────────────────────────────────
WALL_H = 10.0           # actual wall height of one case half
CASE_W = 80.0
CASE_D = 50.0
WALL_T = 2.5
HINGE_LENGTH = 60.0
STATIONS = 6

# HingeParams has pivot_z_offset = 0.2 mm by default — see module docstring.

# ── magnet pocket geometry (6 mm × 3 mm neodymium discs) ──────────────────
# Pocket slightly larger than the magnet: 0.1 mm radial clearance (0.2 mm
# on diameter) is enough on a typical 0.4 mm-nozzle FDM to give a snug
# press fit without rattle. Depth gets a 0.1 mm margin too so the magnet
# sits flush. The previous zero-clearance version was too tight to fit.
MAGNET_OD = 6.0                    # actual magnet outer diameter
MAGNET_T = 3.0                     # actual magnet thickness
POCKET_RADIAL_CLEARANCE = 0.1      # radial, FDM-tested
POCKET_R = MAGNET_OD / 2 + POCKET_RADIAL_CLEARANCE
POCKET_DEPTH = MAGNET_T + 0.1      # tiny depth margin to sit flush
BOSS_R = POCKET_R + 1.5            # 1.5 mm of wall around the pocket


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
    """Add pockets sized for 6 × 3 mm magnets at the two front corners.

    Pocket is 6.2 mm Ø × 3.1 mm — a 0.1 mm radial clearance (0.2 mm on
    diameter) and a 0.1 mm depth margin are enough on a typical 0.4 mm-
    nozzle FDM. The previous "0 clearance" version printed too tight for
    the magnets to fit at all. Each boss is positioned along the diagonal from the
    interior corner so it is tangent to the corner — after fusion with
    the case walls the boss radius shows up as a quarter-circle fillet
    on the inside of the case.
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
            radius=POCKET_R, height=POCKET_DEPTH,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        ).translate((x_boss, y_boss, WALL_H - POCKET_DEPTH))
        half = (half + boss) - pocket
    return half


def _split_hinge_by_side(hinge):
    """Sort the hinge's solids into cs-side (+X bias) and ps-side (-X bias).

    For most parameter combinations make_hinge() returns exactly 2 solids
    and unpacking ``cs, ps = .solids()`` would suffice. But for small
    ``mounting_flat`` (specifically ``mounting_flat < pivot_clearance``)
    the cs leaf strip collapses to zero/negative width — the cs body then
    fragments into N/2 disc tabs and the ps body similarly into several
    pieces. The fragments are still valid: in a clamshell they each fuse
    into the case wall and the printed solid is fine. We just have to
    classify by bbox X-centre instead of unpacking.
    """
    cs, ps = [], []
    for s in hinge.solids():
        bb = s.bounding_box()
        (cs if (bb.min.X + bb.max.X) >= 0 else ps).append(s)
    return Compound(cs), Compound(ps)


def build_clamshell(knuckle: Knuckle, magnets: bool = False):
    # All three variants use the default mounting_flat = 0.5 mm. The leaf
    # strip vanishes (mflat < pivot_clearance = 0.6) so the bare hinge
    # comes back fragmented, but each fragment fuses to the case wall
    # cleanly via _split_hinge_by_side() above. Ramp self-support scales
    # in our favour as the knuckle shrinks. Ramp angle from vertical:
    #   FULL:  n/a (no ramp, knuckle bottom on bed)
    #   HALF:  ~48° — past the strict 45° rule, but well within FDM's cooled
    #          overhang capability (matches the user's printed-confirmed result)
    #   SMALL: ~22° — comfortably self-supporting
    params = HingeParams(
        case_h=WALL_H,                          # actual wall height
        hinge_length=HINGE_LENGTH,
        stations=STATIONS,
        knuckle=knuckle,
        # pivot_z_offset defaults to 0.2 mm — see module docstring
    )
    # W is the leaf's outer face (X = Ro + mounting_flat), which is exactly
    # where the case back wall sits. Pull it from the resolved params so we
    # don't duplicate the knuckle-sizing formula here.
    leaf_outer = params._resolve()["W"]

    cs, ps = _split_hinge_by_side(make_hinge(params))
    cs = cs.translate((0, 0, WALL_H))           # hinge positions to wall top;
    ps = ps.translate((0, 0, WALL_H))           # axis ends up at WALL_H + pivot_z_offset

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
        ("clamshell_small", Knuckle.SMALL, False),
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

"""Print-in-place hinged snap clasp for the front of a clamshell case.

The clasp is the front-of-case partner to ``make_hinge``: a flap that hinges
on the lid, swings down over the seam, and snaps behind a tooth on the base.

  * ``lid_mount``  a small FULL-knuckle hinge leaf (with bores), fused to the
                   lid's front wall
  * ``flap``       the pin leaf plus a flat plate with a window; it prints
                   lying flat on the bed, captured on the pin, and stays a
                   separate moving body
  * ``catch``      a block on the base's front wall with a slot and a tooth

How it holds
------------
Closed, the flap's bottom edge (the *bar*) sits in the slot between the tooth
and the base wall. Pulling the flap outward pushes the bar into the tooth's
chamfered inner edge. The chamfer turns that into an upward push on the
middle of the bar, which bows up into the window above it. Once it has
bowed by ``engage``, it slides over the tooth and the clasp opens. Closing
is the same in reverse over the shallower outer chamfer.

The bar bends in the plane of the flap. Because the flap prints flat, that
bending runs along the layer lines, which is the strong direction for FDM.

Print orientation
-----------------
Everything prints in the flat-open clamshell orientation with no supports:
the knuckle rests on the bed (``Knuckle.FULL``), the flap lies flat, and the
catch block rises straight up from the bed with only upward-facing chamfers.

Coordinate frames
-----------------
``lid_mount`` and ``flap`` come back in the *lid's* print frame and ``catch``
in the *base's* print frame. Both frames use the same convention:

  * the front wall's outer face is the plane X = 0, the case body is in +X,
    and the outside of the case is −X
  * the bed is Z = 0 and the wall top is Z = ``case_h``
  * the clasp is centred on Y = 0 and ``width`` long in Y

For the flat-open clamshell in ``examples/clamshell.py`` (lid in −X, base in
+X) that means translating ``lid_mount`` and ``flap`` to the lid's front face
as they are, and rotating ``catch`` 180° about Z before translating it to the
base's front face.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import NamedTuple

from build123d import (
    Align,
    Axis,
    Box,
    Compound,
    Plane,
    Polyline,
    Pos,
    extrude,
    make_face,
)

from pip_hinge import HingeParams, Knuckle, make_hinge


# Above roughly this peak bending strain the bar risks cracking after a few
# cycles in PLA. PETG copes with more.
BAR_STRAIN_WARN = 0.03


@dataclass(frozen=True)
class ClaspParams:
    """User-facing parameters for the print-in-place snap clasp."""

    case_h: float                    # wall height of each case half (mm)
    width: float = 30.0              # clasp width along the wall (Y, mm)
    seam_gap: float = 0.4
    """Gap between the lid rim and the base rim when the case is closed (mm).

    Matches the ``2 × pivot_z_offset`` seam the main hinge leaves at the back
    (0.4 mm at the default ``pivot_z_offset = 0.2``).
    """
    knuckle_d: float = 6.0           # pivot knuckle diameter (mm)
    stations: int = 6                # alternating knuckle tabs (even, ≥ 2)
    mounting_flat: float = 1.0
    """Flat past the knuckle disc (mm).

    Kept above ``pivot_clearance`` so the flap's pin leaf is one solid that
    the plate fuses onto.
    """
    pivot_clearance: float = 0.6     # radial pin/bore gap (mm)
    flap_t: float = 2.0              # flap plate thickness (mm)
    rail_w: float = 3.0              # side rails either side of the window (mm)
    window_h: float = 2.0            # window height above the bar (mm)
    bar_h: float = 1.4               # bar height, the part that flexes (mm)
    engage: float = 0.8
    """How far the tooth overlaps the bar (mm).

    This is how far the bar has to bow to open or close the clasp. More
    holds tighter but strains the bar harder.
    """
    drop: float = 4.0                # bar bottom sits this far below the base rim (mm)
    tooth_t: float = 2.0             # tooth thickness, outward from the bar (mm)
    tooth_w: float = 0.5
    """Tooth width as a fraction of the window width.

    The tooth has to push on the middle of the bar only. A tooth as wide as
    the window would push next to the stiff rails, and the bar couldn't bow.
    """
    release_angle: float = 60.0      # tooth's inner chamfer, degrees from horizontal
    entry_angle: float = 35.0        # tooth's outer chamfer, degrees from horizontal
    clearance: float = 0.3           # gap between the bar and the slot/tooth (mm)

    def _resolve(self) -> dict:
        if self.case_h <= 0:
            raise ValueError(f"case_h must be > 0 (got {self.case_h})")
        if self.width <= 0:
            raise ValueError(f"width must be > 0 (got {self.width})")
        if self.knuckle_d > self.case_h:
            raise ValueError(
                f"knuckle_d ({self.knuckle_d}) is taller than the wall "
                f"(case_h = {self.case_h}); the knuckle wouldn't fit on the lid"
            )
        if self.mounting_flat <= self.pivot_clearance:
            raise ValueError(
                f"mounting_flat ({self.mounting_flat}) must be > pivot_clearance "
                f"({self.pivot_clearance}) so the flap's pin leaf stays one solid"
            )
        Ro = self.knuckle_d / 2
        if not 0 < self.flap_t <= Ro:
            raise ValueError(
                f"flap_t must be in (0, knuckle_d / 2 = {Ro}] (got {self.flap_t}); "
                f"the plate attaches to the pin leaf, which is only knuckle_d / 2 tall"
            )
        if not 0 < self.engage < self.bar_h:
            raise ValueError(
                f"engage must be in (0, bar_h = {self.bar_h}) (got {self.engage})"
            )
        if self.window_h <= self.engage:
            raise ValueError(
                f"window_h ({self.window_h}) must exceed engage ({self.engage}) "
                f"so the bar has room to bow"
            )
        window_w = self.width - 2 * self.rail_w
        if window_w <= 0:
            raise ValueError(
                f"width ({self.width}) leaves no window between two "
                f"{self.rail_w} mm rails"
            )
        if not 0 < self.tooth_w < 1:
            raise ValueError(f"tooth_w must be in (0, 1) (got {self.tooth_w})")
        for name in ("release_angle", "entry_angle"):
            a = getattr(self, name)
            if not 0 < a < 90:
                raise ValueError(f"{name} must be in (0, 90) degrees (got {a})")

        W = Ro + self.mounting_flat              # hinge leaf outer face offset
        # Flap plate position once closed, in the base frame: it stands
        # W + Ro out from the wall (the pin leaf swings up around the axis),
        # with its inner face flap_t closer in.
        x_out = -(W + Ro)
        x_in = x_out + self.flap_t
        # Flap length from the pin leaf to the bar's bottom edge. In the
        # closed lid frame the plate starts at height Ro + W above the lid's
        # outer face, and the base floor is at 2·case_h + seam_gap.
        z_end = self.case_h - self.drop          # bar bottom, base frame
        z_floor = z_end - self.clearance         # slot floor
        if z_floor <= 0:
            raise ValueError(
                f"drop ({self.drop}) puts the bar below the base floor; "
                f"reduce drop or increase case_h"
            )
        if self.drop <= self.bar_h:
            warnings.warn(
                f"drop ({self.drop}) ≤ bar_h ({self.bar_h}): the bar sits partly "
                f"above the base rim, so the tooth is short.",
                stacklevel=3,
            )
        flap_len = 2 * self.case_h + self.seam_gap - Ro - W - z_end
        solid_len = flap_len - self.bar_h - self.window_h
        if solid_len < 1.0:
            raise ValueError(
                f"flap is too short ({flap_len:.2f} mm) for a {self.window_h} mm "
                f"window and a {self.bar_h} mm bar; increase drop or case_h"
            )

        # Tooth profile: inner face, release chamfer, flat top, entry chamfer.
        run_rel = self.engage / math.tan(math.radians(self.release_angle))
        run_ent = self.engage / math.tan(math.radians(self.entry_angle))
        if run_rel + run_ent >= self.tooth_t:
            raise ValueError(
                f"tooth_t ({self.tooth_t}) is too thin for its chamfers "
                f"({run_rel + run_ent:.2f} mm); increase tooth_t or the angles"
            )

        # Peak bending strain in the bar, treated as a fixed-fixed beam of
        # span window_w and depth bar_h, bowed by `engage` at the middle.
        strain = 12 * self.bar_h * self.engage / window_w ** 2
        if strain > BAR_STRAIN_WARN:
            warnings.warn(
                f"bar strain ≈ {strain:.1%} at full bow; above ~{BAR_STRAIN_WARN:.0%} "
                f"it may crack in PLA. Widen the clasp, or reduce engage or bar_h.",
                stacklevel=3,
            )

        return {
            "Ro": Ro,
            "W": W,
            "x_out": x_out,
            "x_in": x_in,
            "z_end": z_end,
            "z_floor": z_floor,
            "flap_len": flap_len,
            "window_w": window_w,
            "run_rel": run_rel,
            "run_ent": run_ent,
            "strain": strain,
        }


class ClaspParts(NamedTuple):
    """The three bodies of a clasp. See the module docstring for their frames."""

    lid_mount: Compound   # fuse into the lid's front wall
    flap: Compound        # the moving flap; keep it a separate body
    catch: Compound       # fuse into the base's front wall


def _hinge_params(p: ClaspParams) -> HingeParams:
    return HingeParams(
        case_h=p.knuckle_d / 2,
        hinge_length=p.width,
        stations=p.stations,
        knuckle=Knuckle.FULL,
        mounting_flat=p.mounting_flat,
        pivot_clearance=p.pivot_clearance,
        pivot_z_offset=0.0,
    )


def pivot_axis(params: ClaspParams) -> Axis:
    """The flap's pivot axis, in the lid's print frame."""
    r = params._resolve()
    return Axis((-r["W"], 0, r["Ro"]), (0, 1, 0))


def close_flap(flap, params: ClaspParams, angle: float = 90.0):
    """Swing ``flap`` from its print pose to ``angle`` degrees (90 = closed).

    Works in the lid's print frame: the flap folds up against the lid's
    front wall.
    """
    # Positive rotation about +Y takes −X towards +Z, lifting the flap.
    return flap.rotate(pivot_axis(params), angle)


def make_clasp(params: ClaspParams) -> ClaspParts:
    """Build the clasp's lid mount, flap and catch."""
    r = params._resolve()
    Ro, W = r["Ro"], r["W"]
    half_w = params.width / 2

    # ── pivot: a FULL-knuckle hinge, bored leaf on the lid ──────────────────
    # make_hinge puts the axis at the origin with the leaf bottoms at Z = −Ro.
    # Shift so the bored (+X) leaf's outer face lands on the wall at X = 0 and
    # the knuckle rests on the bed.
    hinge = make_hinge(_hinge_params(params))
    hinge = Pos(-W, 0, Ro) * hinge
    lid_side = [s for s in hinge.solids() if s.center().X > -W]
    pin_side = [s for s in hinge.solids() if s.center().X <= -W]
    if len(lid_side) != 1 or len(pin_side) != 1:
        raise RuntimeError(
            f"expected a 2-body pivot hinge, got {len(lid_side)} + {len(pin_side)}"
        )

    # ── flap: a flat plate off the pin leaf's outer face, with a window ─────
    # The plate overlaps a little into the pin leaf's solid strip
    # (X ∈ [−2W, −W − Ro − pivot_clearance]) so the two fuse cleanly.
    overlap = (params.mounting_flat - params.pivot_clearance) / 2
    x0 = -2 * W + overlap
    length = r["flap_len"] + overlap
    plate = Pos(x0, 0, 0) * Box(
        length, params.width, params.flap_t,
        align=(Align.MAX, Align.CENTER, Align.MIN),
    )
    # Window: between the rails, from bar_h in from the far edge.
    far = -2 * W - r["flap_len"]
    window = Pos(far + params.bar_h, 0, 0) * Box(
        params.window_h, r["window_w"], params.flap_t,
        align=(Align.MIN, Align.CENTER, Align.MIN),
    )
    flap = (pin_side[0] + plate) - window

    # ── catch: slot floor block + tooth, in the base frame ──────────────────
    z_floor, z_end = r["z_floor"], r["z_end"]
    z_top = z_end + params.engage
    x_ti = r["x_out"] - params.clearance        # tooth inner face
    x_to = x_ti - params.tooth_t                 # tooth outer face
    floor = Box(
        -x_to, params.width, z_floor,
        align=(Align.MAX, Align.CENTER, Align.MIN),
    )
    tooth_profile = Polyline(
        (x_ti, z_floor),
        (x_ti, z_end),
        (x_ti - r["run_rel"], z_top),            # release chamfer
        (x_to + r["run_ent"], z_top),            # flat top
        (x_to, z_end),                           # entry chamfer
        (x_to, z_floor),
        close=True,
    )
    tooth_w = r["window_w"] * params.tooth_w
    tooth = extrude(
        Plane.XZ * make_face(tooth_profile), amount=tooth_w / 2, both=True
    )
    # Plane.XZ's normal is −Y, so the profile's Z maps to world Z and the
    # extrusion is symmetric about Y = 0.
    catch = floor + tooth

    return ClaspParts(
        lid_mount=Compound(lid_side),
        flap=Compound(flap.solids()),
        catch=Compound(catch.solids()),
    )


__all__ = ["ClaspParams", "ClaspParts", "make_clasp", "close_flap", "pivot_axis"]

"""Parametric print-in-place piano hinge.

Derived from "Parametric print-in-place hinge. FreeCAD." by r0berts
(https://www.printables.com/model/1395662-parametric-print-in-place-hinge-freecad),
licensed CC BY 4.0. This file is a build123d port with every sketch
coordinate re-expressed as a function of named parameters. Same comb
geometry, fully parametric end-to-end. The FreeCAD source used these
spreadsheet cells:

    hingeHeight     total Y extent
    hingeWidth      leaf depth from hinge axis to outer edge
    hingeThickness  leaf thickness
    pivotInner      bore diameter
    pivotOuter      knuckle diameter (= pivotInner * 2 in the original)
    pivotClearance  radial pin/bore gap
    claspWidth      comb tooth width along Y (= hingeHeight / 6)
    claspClearance  Y-axis gap between meshing teeth
    claspCenter     used in pin centring (= hingeHeight / 3)

Two literal small numbers from the FreeCAD pin sketch (Sketch004) carry
across as ``pin_cyl_extra`` and ``pin_end_offset`` below — they were
hand-tuned by the original designer for the pin/bore engagement and
don't follow a derivation from the size parameters. Tweak them at your
own risk.

Print orientation: lay flat on the bed, hinge axis along Y (parallel
to bed). After printing, gently flex the leaves to break the clearance
gaps free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from build123d import (
    Axis,
    CenterArc,
    Circle,
    Compound,
    Line,
    Plane,
    Polyline,
    Sketch,
    export_step,
    export_stl,
    extrude,
    make_face,
    revolve,
)
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound


@dataclass(frozen=True)
class HingeParams:
    """Geometry parameters for the print-in-place hinge."""

    # ── primary dimensions ──────────────────────────────────────────
    hinge_height: float = 40.0      # total Y extent
    hinge_width: float = 30.0       # leaf depth (X) from axis to outer edge
    hinge_thickness: float = 5.0    # leaf thickness (Z)

    # ── pivot (pin + bore) ──────────────────────────────────────────
    pivot_inner: float = 5.0        # bore diameter
    pivot_outer: Optional[float] = None    # knuckle diameter; default 2× pivot_inner
    pivot_clearance: float = 1.0    # radial pin/bore gap

    # ── clasp (comb teeth) ──────────────────────────────────────────
    clasp_width: Optional[float] = None    # tooth width along Y; default hinge_height/6
    clasp_clearance: float = 0.6    # Y-axis gap between meshing teeth (printable)
    clasp_center: Optional[float] = None   # used in pin centring; default hinge_height/3

    # ── pin-segment geometry (from original Sketch004) ──────────────
    pin_cyl_extra: float = 1.5      # extra cylinder length above claspWidth (Constraint 4)
    pin_end_offset: float = 0.5     # end-cap offset (Constraint 21)
    pin_short_cyl_factor: float = 1 / 3   # short-cyl length = claspWidth * this (Constraint 23)

    # ── clamshell self-support ramp ────────────────────────────────
    self_support_ramp: bool = False
    """Extend each leaf downward with a 45° self-supporting ramp.

    When laid flat in a clamshell case (lid + base coplanar on the bed),
    the knuckle becomes a horizontal cylinder hovering above the gap
    between case halves. The bottom half of that cylinder overhangs into
    open air on the side away from each leaf.

    Setting this True extends each leaf from the disc bottom (Z=-T) down
    to Z=-(T+W) on the outer face, with a 45° inner ramp going from the
    outer-bottom corner up to the disc bottom apex. When both leaves are
    placed in a clamshell with their walls flanking the hinge, the two
    ramps converge at the disc bottom forming a teepee that supports the
    cylinder from below — the assembly prints supportless.

    Leave it False (default) for the standalone-print orientation,
    where the hinge is laid with its leaves perpendicular to the bed and
    no ramp is needed.

    The 45° constraint pins leaf_height = hinge_thickness + hinge_width
    (no new dimensional parameter required). For the ramp to actually
    reach the bed, the case wall height must equal hinge_thickness +
    hinge_width — see docs/clamshell-integration.md for the geometry.
    """

    def _resolve(self) -> dict:
        """Resolve all defaults and validate."""
        pivot_outer = self.pivot_outer if self.pivot_outer is not None else self.pivot_inner * 2
        clasp_width = self.clasp_width if self.clasp_width is not None else self.hinge_height / 6
        clasp_center = self.clasp_center if self.clasp_center is not None else self.hinge_height / 3
        if self.pivot_clearance >= self.pivot_inner:
            raise ValueError(
                f"pivot_clearance ({self.pivot_clearance}) must be < pivot_inner ({self.pivot_inner})"
            )
        if pivot_outer <= self.pivot_inner:
            raise ValueError(
                f"pivot_outer ({pivot_outer}) must be > pivot_inner ({self.pivot_inner})"
            )
        leaf_height = (
            self.hinge_thickness + self.hinge_width
            if self.self_support_ramp
            else self.hinge_thickness
        )
        return dict(
            H=self.hinge_height,
            W=self.hinge_width,
            T=self.hinge_thickness,
            Pi=self.pivot_inner,
            Po=pivot_outer,
            Pc=self.pivot_clearance,
            Cw=clasp_width,
            Cc=self.clasp_clearance,
            Cz=clasp_center,
            pin_cyl_extra=self.pin_cyl_extra,
            pin_end_offset=self.pin_end_offset,
            pin_short=self.pin_short_cyl_factor,
            leaf_height=leaf_height,
        )


def make_hinge(params: HingeParams = None) -> Compound:
    """Build the full print-in-place hinge as a 2-body Compound."""
    p = (params or HingeParams())._resolve()
    H, W, T = p["H"], p["W"], p["T"]
    Pi, Po, Pc = p["Pi"], p["Po"], p["Pc"]
    Cw, Cc, Cz = p["Cw"], p["Cc"], p["Cz"]
    Lh = p["leaf_height"]           # leaf height (= T when ramp off, T+W when on)

    Ro = Po / 2                     # knuckle outer radius
    Ri = Pi / 2                     # bore radius
    Rp = Ri - Pc / 2                # pin radius
    Xi = Ro + Pc                    # inner X boundary of comb (= pivot_outer/2 + pivot_clearance)
    pocket_extrude = Lh + Pc / 2    # = (Po + Pc)/2 when ramp off; deeper when on

    # ── cylinder-side leaf cross-section (Sketch in original) ──────
    # With self_support_ramp, the outer-bottom corner moves to (W, -Lh),
    # and the segment from there back to (0, -T) is the 45° self-support
    # ramp. With ramp off (Lh == T), this is the original profile.
    cs_profile = Polyline(
        (Ro, 0), (W, 0), (W, -Lh), (0, -T),
    ) + CenterArc(center=(0, 0), radius=Ro, start_angle=270, arc_size=-270)
    cs_sketch = Sketch() + Plane.XZ * (make_face(cs_profile) - Circle(Ri))
    cs_pad = extrude(cs_sketch, amount=H / 2, both=True)

    # ── cylinder-side pocket (Sketch002): 3 inward-pointing tabs ───
    # Y boundaries: pad ends at ±H/2; tab boundaries are derived from
    # claspWidth and claspClearance.  Three tabs of width (Cw - Cc),
    # separated by gaps of width (Cw + Cc), centred on Y=0.
    pad_max = 3.5 * Cw + Cc / 2     # outer polygon Y boundary
    tab1_o = 2.5 * Cw - Cc / 2      # outer edge of outer tabs (= H/2 - Cw/2 - Cc/2)
    tab1_i = 1.5 * Cw + Cc / 2      # inner edge of outer tabs
    tab0_o = Cw / 2 - Cc / 2        # half-width of centre tab (− margin)
    Xo_cs = Xi - W                  # outer X of pocket polygon (cylinder-side)

    cs_pocket_profile = Polyline(
        (Xo_cs,  pad_max),
        (Xo_cs, -pad_max),
        ( Xi,   -pad_max),
        ( Xi,   -tab1_o),  (-Xi, -tab1_o),
        (-Xi,   -tab1_i),  ( Xi, -tab1_i),
        ( Xi,   -tab0_o),  (-Xi, -tab0_o),
        (-Xi,    tab0_o),  ( Xi,  tab0_o),
        ( Xi,    tab1_i),  (-Xi,  tab1_i),
        (-Xi,    tab1_o),  ( Xi,  tab1_o),
        ( Xi,    pad_max),
        (Xo_cs,  pad_max),  # close back to start
    )
    cs_pocket = make_face(cs_pocket_profile)
    cylinder_side = cs_pad - extrude(cs_pocket, amount=pocket_extrude, both=True)

    # ── pin-side leaf cross-section (Sketch001) ────────────────────
    ps_profile = Polyline(
        (-Ro, 0), (-W, 0), (-W, -Lh), (0, -T),
    ) + CenterArc(center=(0, 0), radius=Ro, start_angle=270, arc_size=270)
    ps_sketch = Sketch() + Plane.XZ * make_face(ps_profile)
    ps_pad = extrude(ps_sketch, amount=H / 2, both=True)

    # ── pin-side pocket (Sketch003): mirror of cylinder-side, no clearance margin ──
    # Pin-side tabs claim the full segments (end-segments are half-width).
    ps_tab_outer = 2.5 * Cw         # = H/2 - Cw/2  (start of end tab)
    ps_tab_mid_o = 1.5 * Cw         # outer edge of inner tab
    ps_tab_mid_i = 0.5 * Cw         # inner edge of inner tab
    Xo_ps = 4 * Po - Xi             # outer X of pocket polygon (pin-side) = pivotOuter*4 - Xi

    ps_pocket_profile = Polyline(
        (-Xi,    -ps_tab_outer),
        ( Xo_ps, -ps_tab_outer),
        ( Xo_ps,  ps_tab_outer),
        (-Xi,     ps_tab_outer),
        (-Xi,     ps_tab_mid_o),  ( Xi,  ps_tab_mid_o),
        ( Xi,     ps_tab_mid_i),  (-Xi,  ps_tab_mid_i),
        (-Xi,    -ps_tab_mid_i),  ( Xi, -ps_tab_mid_i),
        ( Xi,    -ps_tab_mid_o),  (-Xi, -ps_tab_mid_o),
        (-Xi,    -ps_tab_outer),  # close
    )
    ps_pocket = make_face(ps_pocket_profile)
    pin_side = ps_pad - extrude(ps_pocket, amount=pocket_extrude, both=True)

    # ── pin segments (Sketch004) ───────────────────────────────────
    # Four revolution profiles in the (X, Y) plane, revolved around Y axis.
    # Loops 0 and 2 (inner): full capsule, centred at ±Cz/2.
    # Loops 1 and 3 (outer): partial capsule, near the hinge ends.
    cyl_long  = Cw + p["pin_cyl_extra"]                     # full-capsule cyl length
    cyl_short = Cw * p["pin_short"]                         # short-capsule cyl length
    half_long = cyl_long / 2
    y_centre_long  = Cz / 2                                 # Y centre of loops 0 / 2
    y_long_top    = y_centre_long + half_long               # = 10.75 for defaults
    y_long_bot    = y_centre_long - half_long               # = 2.583
    y_long_cap_t  = y_long_top + Rp                         # = 12.75
    y_long_cap_b  = y_long_bot - Rp                         # = 0.583

    # Loop 0: full capsule on +Y side
    loop0 = (
        Line((Rp, y_long_top), (Rp, y_long_bot))
        + CenterArc(center=(0, y_long_bot), radius=Rp, start_angle=360, arc_size=-90)
        + Line((0, y_long_cap_b), (0, y_long_cap_t))
        + CenterArc(center=(0, y_long_top), radius=Rp, start_angle=90, arc_size=-90)
    )

    # Loop 2: full capsule on −Y side (mirror of loop 0)
    loop2 = (
        CenterArc(center=(0, -y_long_bot), radius=Rp, start_angle=0, arc_size=90)
        + Line((0, -y_long_cap_b), (0, -y_long_cap_t))
        + CenterArc(center=(0, -y_long_top), radius=Rp, start_angle=270, arc_size=90)
        + Line((Rp, -y_long_top), (Rp, -y_long_bot))
    )

    # Loops 1 / 3: short capsule near hinge ends (one hemisphere, one flat end).
    # The hemisphere bottom (inner end) sits at (2.5*Cw - pin_end_offset), i.e.
    # ``pin_end_offset`` below pin_side's end-tab inner edge (= 2.5*Cw).
    y_short_cyl_bot    = 2.5 * Cw - p["pin_end_offset"]
    y_short_cyl_top    = y_short_cyl_bot + cyl_short
    y_short_outer_flat = y_short_cyl_top
    y_short_cap_bot    = y_short_cyl_bot - Rp

    loop1 = (
        Polyline(
            (0, y_short_outer_flat),
            (Rp, y_short_outer_flat),
            (Rp, y_short_cyl_bot),
        )
        + CenterArc(center=(0, y_short_cyl_bot), radius=Rp, start_angle=0, arc_size=-90)
        + Line((0, y_short_cap_bot), (0, y_short_outer_flat))
    )
    loop3 = (
        CenterArc(center=(0, -y_short_cyl_bot), radius=Rp, start_angle=0, arc_size=90)
        + Polyline(
            (0, -y_short_cap_bot),
            (0, -y_short_outer_flat),
            (Rp, -y_short_outer_flat),
            (Rp, -y_short_cyl_bot),
        )
    )

    pin_sketch = make_face(loop0) + make_face(loop1) + make_face(loop2) + make_face(loop3)
    pin_side = pin_side + revolve(pin_sketch, axis=Axis.Y, revolution_arc=-360)

    # ── assemble both bodies into a multi-body Compound ────────────
    builder = BRep_Builder()
    occ = TopoDS_Compound()
    builder.MakeCompound(occ)
    for solid in [*cylinder_side.solids(), *pin_side.solids()]:
        builder.Add(occ, solid.wrapped)
    return Compound(occ)


if __name__ == "__main__":
    hinge = make_hinge()
    out = Path(__file__).parent / "examples"
    out.mkdir(exist_ok=True)
    stem = out / "hinge_default"
    export_step(hinge, str(stem) + ".step")
    export_stl(hinge, str(stem) + ".stl")
    print(f"Exported {stem}.step / .stl")

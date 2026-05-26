"""Parametric print-in-place piano hinge for clamshell cases.

Four inputs, everything else derived:

  * ``case_h``        wall height of the case half (mm)
  * ``hinge_length``  total hinge length along its axis (mm)
  * ``stations``      number of alternating cs/ps tabs (even, ≥ 2)
  * ``knuckle``       Knuckle.FULL  → Po = 2 × case_h, knuckle rests on bed,
                                       no ramp needed
                      Knuckle.HALF  → Po = case_h, 45°-or-shallower ramp,
                                       prints supportless

The implicit constraints are documented in docs/clamshell-integration.md and
the diagrams under docs/diagrams/. Two leftover dimensional knobs are exposed
for tuning the pin/bore feel (``pivot_clearance``, ``clasp_clearance``) and
three small pin-engagement constants are kept tunable for backwards
compatibility with the original FreeCAD source.

Derived from "Parametric print-in-place hinge. FreeCAD." by r0berts
(https://www.printables.com/model/1395662-parametric-print-in-place-hinge-freecad),
licensed CC BY 4.0.

Print orientation: lay flat on the bed, hinge axis along Y (parallel to bed).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from enum import Enum
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
    Pos,
    Sketch,
    export_step,
    export_stl,
    extrude,
    make_face,
    revolve,
)
from OCP.BRep import BRep_Builder
from OCP.TopoDS import TopoDS_Compound


class Knuckle(Enum):
    """Knuckle size.

    FULL and HALF are percentages of the closed-case height (2 × case_h);
    SMALL is computed in ``_resolve()`` as max(case_h/2, 5 mm) — the 1/4-of-FULL
    ratio with a 5 mm absolute floor that keeps the bore + pin big enough to
    print reliably on a 0.4 mm-nozzle FDM regardless of case height.
    """

    FULL = 100   # Po = 2 × case_h; knuckle bottom touches bed, no ramp needed
    HALF = 50    # Po = case_h; 45°-or-shallower self-supporting ramp
    SMALL = -1   # sentinel — see _resolve() for the actual size formula


@dataclass(frozen=True)
class HingeParams:
    """User-facing parameters for the print-in-place hinge."""

    case_h: float                        # case wall height (mm)
    hinge_length: float                  # total hinge length along the axis (mm)
    stations: int = 6                    # alternating cs/ps tab count (even, ≥ 2)
    knuckle: Knuckle = Knuckle.FULL      # knuckle size
    mounting_flat: float = 0.5           # flat width past the disc edge (mm)
    pivot_clearance: float = 0.6         # radial pin/bore gap (mm)
    pivot_z_offset: float = 0.2
    """Empirical lift of the hinge axis above the case wall top (mm).

    The leaf grows by this much in Z so the bed-side end of the leaf
    still lands on the bed when the lifted axis is positioned at
    ``case_h``; the bottom face of the disc sits ``pivot_z_offset``
    above the wall top. When the case closes, the lid then sits
    ``2 × pivot_z_offset`` above the base instead of meeting it on a
    zero-tolerance plane — so a high spot anywhere along the seam
    can't spring the front of the case open under elastic tension.

    Default 0.2 mm matches the empirical value baked into the previous
    clamshell example. Set to 0 to disable (knuckle bottom rests
    directly on the wall top, no seam gap).
    """
    clasp_clearance: Optional[float] = None
    """Axial gap between cs and ps tabs (mm).

    Leave as ``None`` to auto-scale with knuckle diameter ``Po``: 0.2 mm
    at Po = 5 mm (matches the original r0berts FreeCAD value — the tighter
    fit matters more when the knuckle is small), linearly up to 0.4 mm at
    Po ≥ 10 mm (the relaxed value that prints reliably on a standard
    0.4 mm-nozzle FDM). Formula: ``clamp(0.04 × Po, 0.2, 0.4)``. Pass an
    explicit value to override.
    """

    # Pin-engagement constants hand-tuned in the original FreeCAD source.
    # Leave at defaults unless deliberately tweaking pin feel.
    pin_cyl_extra: float = 1.5
    pin_end_offset: float = 0.5
    pin_short_cyl_factor: float = 1 / 3

    def _resolve(self) -> dict:
        if self.case_h <= 0:
            raise ValueError(f"case_h must be > 0 (got {self.case_h})")
        if self.hinge_length <= 0:
            raise ValueError(f"hinge_length must be > 0 (got {self.hinge_length})")
        if self.stations < 2 or self.stations % 2 != 0:
            raise ValueError(
                f"stations must be an even integer ≥ 2 (got {self.stations})"
            )
        if self.mounting_flat < 0:
            raise ValueError(f"mounting_flat must be ≥ 0 (got {self.mounting_flat})")
        if self.pivot_z_offset < 0:
            raise ValueError(f"pivot_z_offset must be ≥ 0 (got {self.pivot_z_offset})")

        # Knuckle is sized to the LIFTED axis (case_h + pivot_z_offset), not just
        # case_h. This preserves the "FULL knuckle bottom rests on bed when flat
        # for printing" guarantee: with Ro = case_h + pz_off, the axis at Z =
        # case_h + pz_off and Ro the same means the disc bottom lands at exactly
        # Z = 0 (the bed). It also keeps the bottom segment of the leaf polyline
        # horizontal at FULL (no spurious slope from the offset).
        effective_case_h = self.case_h + self.pivot_z_offset
        if self.knuckle is Knuckle.SMALL:
            # 1/4 of FULL, floored at 5 mm so the pin & bore stay printable
            # at any case height. For case_h ≥ 10 mm the ratio dominates;
            # below that the 5 mm floor kicks in.
            Po = max(effective_case_h / 2, 5.0)
        else:
            Po = 2 * effective_case_h * self.knuckle.value / 100
        Ro = Po / 2
        Pi = Po / 2                                  # bore diameter (= Ro)
        if Pi <= self.pivot_clearance:
            raise ValueError(
                f"bore Ø ({Pi:.2f}) ≤ pivot_clearance ({self.pivot_clearance}); "
                f"increase case_h or reduce pivot_clearance"
            )

        Cw = self.hinge_length / self.stations
        if Cw < 3:
            warnings.warn(
                f"clasp_width = {Cw:.2f}mm is below ~3mm; likely too thin for FDM. "
                f"Reduce stations or increase hinge_length.",
                stacklevel=2,
            )

        # Size-aware clasp_clearance default: scales linearly with knuckle
        # diameter Po, from 0.2 mm at Po=5 mm to 0.4 mm at Po≥10 mm. The
        # tighter fit matters more when the knuckle is small (relative
        # play is bigger). Clamped both ends so very small or very large
        # knuckles stay in the printable / sensible range.
        if self.clasp_clearance is None:
            Cc = max(0.2, min(0.4, 0.04 * Po))
        else:
            Cc = self.clasp_clearance
        return {
            "case_h": self.case_h,
            "H": self.hinge_length,
            "stations": self.stations,
            "Po": Po,
            "Ro": Ro,
            "T": Ro,                                 # T = Ro by construction
            "Pi": Pi,
            "Pc": self.pivot_clearance,
            "W": Ro + self.mounting_flat,
            "Cw": Cw,
            "Cc": Cc,
            "pivot_z_offset": self.pivot_z_offset,
            "pin_cyl_extra": self.pin_cyl_extra,
            "pin_end_offset": self.pin_end_offset,
            "pin_short": self.pin_short_cyl_factor,
        }


# ── pocket polylines (parametric in N stations) ───────────────────────────────

def _cs_pocket_polyline(N: int, Cw: float, Cc: float, Xi: float, Xo_cs: float):
    """Pocket cut for the cs (cylinder-side) leaf. Excludes N/2 cs tabs.

    cs tabs (with bores in them) sit at Y centres spaced 2·Cw apart,
    symmetric around Y = 0. Each tab is Cw − Cc wide (the Cc/2 margin
    per side is the printable clearance between meshing cs and ps tabs).
    """
    k = N // 2
    half_tab = (Cw - Cc) / 2
    pad_max = (N + 1) * Cw / 2 + Cc / 2     # extends slightly past H/2

    pts = [(Xo_cs, pad_max), (Xo_cs, -pad_max), (Xi, -pad_max)]
    cs_centres = [(-(k - 1) + 2 * i) * Cw for i in range(k)]
    for Y_c in cs_centres:                  # ascending Y
        pts.extend([
            (Xi,  Y_c - half_tab),
            (-Xi, Y_c - half_tab),
            (-Xi, Y_c + half_tab),
            (Xi,  Y_c + half_tab),
        ])
    pts.extend([(Xi, pad_max), (Xo_cs, pad_max)])
    return Polyline(*pts)


def _ps_pocket_polyline(N: int, Cw: float, Xi: float, Xo_ps: float):
    """Pocket cut for the ps (pin-side) leaf. Excludes ps end-caps + middle tabs.

    Pattern along Y: ps_end_cap (Cw/2) | cs (Cw) | ps_middle (Cw) | cs | ... | ps_end_cap.
    The ends are half-width ps caps; in between, full-Cw alternating cs/ps tabs,
    starting and ending with cs.
    """
    k = N // 2
    ps_outer = (k - 0.5) * Cw                # inner edge of the ps end-caps
    ps_centres = [(-(k - 2) + 2 * i) * Cw for i in range(k - 1)]

    pts = [
        (-Xi,   -ps_outer),
        (Xo_ps, -ps_outer),
        (Xo_ps,  ps_outer),
        (-Xi,    ps_outer),
    ]
    for Y_c in reversed(ps_centres):         # walk back down with notches
        pts.extend([
            (-Xi, Y_c + Cw / 2),
            (Xi,  Y_c + Cw / 2),
            (Xi,  Y_c - Cw / 2),
            (-Xi, Y_c - Cw / 2),
        ])
    pts.append((-Xi, -ps_outer))
    return Polyline(*pts)


# ── pin segments (parametric in N stations) ───────────────────────────────────

def _pin_loops(N: int, Cw: float, Rp: float,
               pin_cyl_extra: float, pin_end_offset: float, pin_short: float):
    """2D pin profiles to be revolved around Y axis.

    One long capsule per ps middle tab (N/2 − 1 of them) plus a bullet at each
    end-cap (always 2). For N = 2 there are no middle tabs, so just 2 bullets.
    """
    k = N // 2
    long_centres = [(-(k - 2) + 2 * i) * Cw for i in range(k - 1)]
    cyl_long = Cw + pin_cyl_extra
    half_long = cyl_long / 2

    loops = []
    for Y_c in long_centres:
        y_top = Y_c + half_long
        y_bot = Y_c - half_long
        y_cap_t = y_top + Rp
        y_cap_b = y_bot - Rp
        loops.append(
            Line((Rp, y_top), (Rp, y_bot))
            + CenterArc(center=(0, y_bot), radius=Rp, start_angle=360, arc_size=-90)
            + Line((0, y_cap_b), (0, y_cap_t))
            + CenterArc(center=(0, y_top), radius=Rp, start_angle=90, arc_size=-90)
        )

    # End-cap bullets: hemisphere on the inner end (pointing toward the centre),
    # flat top buried inside the ps end-cap material.
    end_inner = (k - 0.5) * Cw
    cyl_short = Cw * pin_short
    y_short_cyl_b = end_inner - pin_end_offset
    y_short_cyl_t = y_short_cyl_b + cyl_short
    y_short_cap_b = y_short_cyl_b - Rp

    loops.append(                            # +Y end
        Polyline(
            (0, y_short_cyl_t),
            (Rp, y_short_cyl_t),
            (Rp, y_short_cyl_b),
        )
        + CenterArc(center=(0, y_short_cyl_b), radius=Rp, start_angle=0, arc_size=-90)
        + Line((0, y_short_cap_b), (0, y_short_cyl_t))
    )
    loops.append(                            # −Y end (mirror)
        CenterArc(center=(0, -y_short_cyl_b), radius=Rp, start_angle=0, arc_size=90)
        + Polyline(
            (0, -y_short_cap_b),
            (0, -y_short_cyl_t),
            (Rp, -y_short_cyl_t),
            (Rp, -y_short_cyl_b),
        )
    )
    return loops


# ── main constructor ──────────────────────────────────────────────────────────

def make_hinge(params: HingeParams = None) -> Compound:
    """Build the full print-in-place hinge as a 2-body Compound."""
    if params is None:
        params = HingeParams(case_h=10.0, hinge_length=60.0)
    p = params._resolve()
    case_h, H, N = p["case_h"], p["H"], p["stations"]
    pz_off = p["pivot_z_offset"]
    # The hinge is built in coords where the disc centre is at Z=0; after
    # construction we translate everything up by pz_off so the disc centre
    # ends up at the lifted axis height when the caller positions the hinge
    # to the wall top. The leaf must therefore extend down to Z = -leaf_h
    # = -(case_h + pz_off), so its bed-side end lands at world Z = 0.
    leaf_h = case_h + pz_off
    Ro, T, Po = p["Ro"], p["T"], p["Po"]
    Pi, Pc, W = p["Pi"], p["Pc"], p["W"]
    Cw, Cc = p["Cw"], p["Cc"]

    Ri = Pi / 2                              # bore radius
    Rp = Ri - Pc / 2                         # pin radius
    Xi = Ro + Pc                             # inner X boundary of pocket comb
    pocket_extrude = leaf_h + Pc / 2

    # ── cs (cylinder-side) leaf ──────────────────────────────────────────────
    # Unified polyline. At FULL the knuckle is sized to the lifted axis
    # (Ro = leaf_h), so T = leaf_h and the "ramp" segment from (W, -leaf_h)
    # to (0, -T) is horizontal — knuckle bottom touches the bed, no overhang.
    # At HALF/SMALL the disc bottom sits above the bed and the segment is a
    # 45°-or-shallower self-supporting ramp.
    cs_profile = (
        Polyline((Ro, 0), (W, 0), (W, -leaf_h), (0, -T))
        + CenterArc(center=(0, 0), radius=Ro, start_angle=270, arc_size=-270)
    )
    cs_sketch = Sketch() + Plane.XZ * (make_face(cs_profile) - Circle(Ri))
    cs_pad = extrude(cs_sketch, amount=H / 2, both=True)
    # Pocket polygon left edge must stay left of the notch jogs (which go to -Xi),
    # otherwise the polyline self-intersects and OCC misclassifies the interior.
    # Old defaults happened to satisfy Xi − W ≤ −Xi; the new API's small W doesn't.
    Xo_cs = min(Xi - W, -Xi - 1.0)
    cs_pocket = make_face(_cs_pocket_polyline(N, Cw, Cc, Xi, Xo_cs))
    cylinder_side = cs_pad - extrude(cs_pocket, amount=pocket_extrude, both=True)

    # ── ps (pin-side) leaf ───────────────────────────────────────────────────
    ps_profile = (
        Polyline((-Ro, 0), (-W, 0), (-W, -leaf_h), (0, -T))
        + CenterArc(center=(0, 0), radius=Ro, start_angle=270, arc_size=270)
    )
    ps_sketch = Sketch() + Plane.XZ * make_face(ps_profile)
    ps_pad = extrude(ps_sketch, amount=H / 2, both=True)
    Xo_ps = 4 * Po - Xi
    ps_pocket = make_face(_ps_pocket_polyline(N, Cw, Xi, Xo_ps))
    pin_side = ps_pad - extrude(ps_pocket, amount=pocket_extrude, both=True)

    # ── pin segments ────────────────────────────────────────────────────────
    loops = _pin_loops(N, Cw, Rp, p["pin_cyl_extra"], p["pin_end_offset"], p["pin_short"])
    pin_sketch = make_face(loops[0])
    for loop in loops[1:]:
        pin_sketch = pin_sketch + make_face(loop)
    pin_side = pin_side + revolve(pin_sketch, axis=Axis.Y, revolution_arc=-360)

    # ── lift everything by pivot_z_offset so the axis sits above the
    # leaf-top reference (= where the wall top will end up). Leaf top
    # stays at local Z=0 (= wall top); axis ends up at Z=+pz_off.
    if pz_off:
        cylinder_side = Pos(0, 0, pz_off) * cylinder_side
        pin_side = Pos(0, 0, pz_off) * pin_side

    # ── assemble into a 2-body Compound ─────────────────────────────────────
    builder = BRep_Builder()
    occ = TopoDS_Compound()
    builder.MakeCompound(occ)
    for solid in [*cylinder_side.solids(), *pin_side.solids()]:
        builder.Add(occ, solid.wrapped)
    return Compound(occ)


if __name__ == "__main__":
    out = Path(__file__).parent / "examples"
    out.mkdir(exist_ok=True)
    for name, knuckle in [("full", Knuckle.FULL), ("half", Knuckle.HALF)]:
        h = make_hinge(HingeParams(case_h=10.0, hinge_length=60.0, knuckle=knuckle))
        stem = out / f"hinge_{name}"
        export_step(h, str(stem) + ".step")
        export_stl(h, str(stem) + ".stl")
        print(f"Exported {stem}.step / .stl")

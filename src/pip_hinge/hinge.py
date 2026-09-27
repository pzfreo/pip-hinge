"""Parametric print-in-place piano hinge for clamshell cases.

:class:`PrintInPlaceHinge` builds the hinge from four primary inputs
(``case_h``, ``hinge_length``, ``stations``, ``knuckle``) with everything else
derived; :class:`HingeParams` + :func:`make_hinge` is the same thing as a
reusable parameter value. The two leaves are the *cylinder side* (bored
knuckle tabs; "cs" in the internals below) and the *pin side* (end caps and
the captured pin; "ps").

Derived from "Parametric print-in-place hinge. FreeCAD." by r0berts
(https://www.printables.com/model/1395662-parametric-print-in-place-hinge-freecad),
licensed CC BY 4.0.

Print orientation: lay flat on the bed, hinge axis along Y (parallel to bed).
"""

from __future__ import annotations

import math
import warnings
import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from build123d import (
    Axis,
    Location,
    RevoluteJoint,
    RigidJoint,
    CenterArc,
    Circle,
    Compound,
    Line,
    Plane,
    Polyline,
    Pos,
    Sketch,
    extrude,
    make_face,
    revolve,
)


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
    """Parameters for :class:`PrintInPlaceHinge`, as a reusable value.

    Fields are the keyword arguments of PrintInPlaceHinge; see its ``Args:``
    for what each one means. ``make_hinge(params)`` builds the hinge.

    Attributes:
        case_h (float): case wall height (mm).
        hinge_length (float): total hinge length along the axis (mm).
        stations (int): alternating cylinder-side / pin-side tab count
            (even, ≥ 2). Defaults to 6.
        knuckle (Knuckle): knuckle size. Defaults to Knuckle.FULL.
        mounting_flat (float): flat leaf width past the knuckle edge (mm).
            Defaults to 0.5.
        pivot_clearance (float): radial pin/bore gap (mm). Defaults to 0.6.
        pivot_z_offset (float): lift of the hinge axis above the wall top
            (mm). Defaults to 0.2.
        clasp_clearance (float | None): axial gap between meshing tabs (mm);
            None auto-scales with knuckle size. Defaults to None.
        pin_cyl_extra (float): pin-engagement constant. Defaults to 1.5.
        pin_end_offset (float): pin-engagement constant. Defaults to 0.5.
        pin_short_cyl_factor (float): pin-engagement constant.
            Defaults to 1/3.
    """

    case_h: float
    hinge_length: float
    stations: int = 6
    knuckle: Knuckle = Knuckle.FULL
    mounting_flat: float = 0.5
    pivot_clearance: float = 0.6
    pivot_z_offset: float = 0.2
    clasp_clearance: Optional[float] = None
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
        if self.mounting_flat <= 0:
            # W == Ro at 0 gives a degenerate leaf profile that OCC rejects with a
            # cryptic StdFail_NotDone; fail early with a clear message instead.
            raise ValueError(f"mounting_flat must be > 0 (got {self.mounting_flat})")
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
        if self.pivot_z_offset >= Ro:
            raise ValueError(
                f"pivot_z_offset ({self.pivot_z_offset}) must be < knuckle radius "
                f"({Ro:.2f})"
            )
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
                stacklevel=3,
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

def _build_leaves(p: dict) -> tuple[Compound, Compound]:
    """Build (cylinder_side, pin_side) in the placed frame: bed at Z = 0,
    axis along Y through (X = 0, Z = case_h + pivot_z_offset). ``p`` is
    ``HingeParams._resolve()``."""
    case_h, H, N = p["case_h"], p["H"], p["stations"]
    pz_off = p["pivot_z_offset"]
    # The hinge is built in coords where the disc centre is at Z=0; after
    # construction everything is lifted by leaf_h so the leaf bottom lands on
    # the bed (Z = 0) and the axis sits pz_off above the wall top.
    leaf_h = case_h + pz_off
    Ro, T, Po = p["Ro"], p["T"], p["Po"]
    Pi, Pc, W = p["Pi"], p["Pc"], p["W"]
    Cw, Cc = p["Cw"], p["Cc"]

    Ri = Pi / 2                              # bore radius
    Rp = Ri - Pc / 2                         # pin radius
    Xi = Ro + Pc                             # inner X boundary of pocket comb
    pocket_extrude = leaf_h + Pc / 2

    # ── leaf profiles ────────────────────────────────────────────────────────
    # Each leaf's underside must reach the bed self-supporting (no slicer support).
    # The knuckle disc sits at the wall top; on the MESHING side (the side with no
    # wall under it) its lower arc faces down and would sag. Two cases:
    #
    #  • small disc -> a tangent RAMP from the wall foot (±W, -leaf_h) up to the far
    #    tangent point cradles the underside; the exposed arc above is steeper still.
    #    The tangent is the steepest ramp that reaches the disc, so for a small disc
    #    it is >= 45° from horizontal and self-supports.
    #
    #  • big disc (e.g. Knuckle.HALF) -> that foot-anchored tangent comes out < 45°
    #    and would sag. Instead the support line meets the disc TANGENTIALLY on the
    #    meshing side at exactly SELF_SUPPORT_DEG and runs down to its own bed
    #    contact, replacing the disc's downward arc with a self-supporting TEARDROP.
    #
    #  • FULL -> the disc rests on the bed (no ramp, no teardrop).
    SELF_SUPPORT_DEG = 45.0
    use_tangent = T < leaf_h - 1e-6

    def _far_tangent(wall_x):
        """Angle (rad) of the tangent point on the side OPPOSITE the wall."""
        ex, ey = wall_x, -leaf_h
        d = math.hypot(ex, ey)
        a = math.asin(min(1.0, Ro / d))
        base = math.atan2(ey, ex)
        for s in (1.0, -1.0):
            th = base + s * (math.pi / 2 - a)
            if (math.cos(th) < 0) == (wall_x > 0):     # far side = opposite the wall
                return th
        return None

    def _knuckle_geo(wall_x):
        """('ramp'|'teardrop', tangent_angle_rad) for the meshing-side underside."""
        th = _far_tangent(wall_x)
        if th is not None:
            tp = (Ro * math.cos(th), Ro * math.sin(th))
            ang = math.degrees(math.atan2(abs(tp[1] + leaf_h), abs(tp[0] - wall_x)))
            if ang >= SELF_SUPPORT_DEG:
                return "ramp", th
        # teardrop: meshing-side tangent at exactly the self-support angle
        th_td = math.radians(180.0 + SELF_SUPPORT_DEG) if wall_x > 0 \
            else math.radians(360.0 - SELF_SUPPORT_DEG)
        return "teardrop", th_td

    def _leaf_profile(wall_x):
        """Outer profile: wall + self-supporting underside + exposed disc arc."""
        sgn = 1.0 if wall_x > 0 else -1.0
        # The leaf top is the wall top, pz_off below the axis, so the mounting
        # flat stays flush with the wall instead of standing proud of it.
        # `eq` is where that plane meets the disc on the wall side.
        top_deg = math.degrees(math.asin(pz_off / Ro))
        eq = (sgn * math.sqrt(Ro * Ro - pz_off * pz_off), -pz_off)
        bed = []
        if not use_tangent:                            # FULL: disc rests on the bed
            tp, start = (0.0, -T), 270.0
        else:
            mode, th = _knuckle_geo(wall_x)
            tp = (Ro * math.cos(th), Ro * math.sin(th))
            start = math.degrees(th) % 360.0
            if mode == "teardrop":                     # tangent line down to its own
                run = (leaf_h + tp[1]) / math.tan(math.radians(SELF_SUPPORT_DEG))
                bed = [(tp[0] + sgn * run, -leaf_h)]   # bed contact, then up to tp
        # arc sweeps from the tangent point over the EXPOSED side back to `eq`
        arc = -(start + top_deg) if wall_x > 0 else 540.0 + top_deg - start
        return (Polyline(eq, (wall_x, -pz_off), (wall_x, -leaf_h), *bed, tp)
                + CenterArc(center=(0, 0), radius=Ro, start_angle=start, arc_size=arc))

    cs_profile = _leaf_profile(W)
    cs_sketch = Sketch() + Plane.XZ * (make_face(cs_profile) - Circle(Ri))
    cs_pad = extrude(cs_sketch, amount=H / 2, both=True)
    # Pocket polygon left edge must stay left of the notch jogs (which go to -Xi),
    # otherwise the polyline self-intersects and OCC misclassifies the interior.
    # Old defaults happened to satisfy Xi − W ≤ −Xi; the new API's small W doesn't.
    Xo_cs = min(Xi - W, -Xi - 1.0)
    cs_pocket = make_face(_cs_pocket_polyline(N, Cw, Cc, Xi, Xo_cs))
    cylinder_side = cs_pad - extrude(cs_pocket, amount=pocket_extrude, both=True)

    # ── ps (pin-side) leaf ───────────────────────────────────────────────────
    ps_profile = _leaf_profile(-W)
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

    # ── lift so the leaf bottom sits on the bed ─────────────────────────────
    lift = Pos(0, 0, leaf_h)
    return (
        Compound((lift * cylinder_side).solids(), label="cylinder_side"),
        Compound((lift * pin_side).solids(), label="pin_side"),
    )


class PrintInPlaceHinge(Compound):
    """Print-in-place piano hinge, positioned ready to fuse into a case.

    The hinge is built flat-open in print orientation, in the frame of a case
    whose walls stand on the bed:

    * bed at Z = 0, wall top at Z = ``case_h``;
    * hinge axis along Y through (X = 0, Z = ``case_h + pivot_z_offset``);
    * ``cylinder_side`` leaf extends to X = +``leaf_width``, ``pin_side`` to
      X = −``leaf_width`` — those outer faces are where the case walls go;
    * Y spans ±``hinge_length`` / 2.

    So a case back wall whose outer face is at X = x0 takes
    ``Pos(x0 - hinge.leaf_width, y, 0) * hinge.cylinder_side`` (and the same
    for ``pin_side``). The leaves are children, located relative to the
    hinge, so move the leaves rather than the hinge when fusing into a case.

    Args:
        case_h (float): case wall height (mm); the hinge's scale reference.
        hinge_length (float): total hinge length along the axis (mm).
        stations (int, optional): number of alternating cylinder-side /
            pin-side tabs; even, ≥ 2. Defaults to 6.
        knuckle (Knuckle, optional): knuckle size. Defaults to Knuckle.FULL.
        mounting_flat (float, optional): flat leaf width past the knuckle edge,
            for fusing to the case wall (mm). At or below ``pivot_clearance``
            the bare hinge fragments into several solids per leaf, which is
            fine once fused into a case. Defaults to 0.5.
        pivot_clearance (float, optional): radial pin/bore gap (mm).
            Defaults to 0.6.
        pivot_z_offset (float, optional): lift of the hinge axis above the
            wall top (mm). When the case closes, the lid then sits
            2 × pivot_z_offset above the base instead of meeting it on a
            zero-tolerance plane, so a high spot along the seam can't spring
            the front open. The leaves stay flush with the wall top; only the
            knuckle is raised. 0 disables it. Defaults to 0.2.
        clasp_clearance (float, optional): axial gap between meshing tabs (mm).
            None scales it with knuckle diameter Po as
            ``clamp(0.04 × Po, 0.2, 0.4)``. Defaults to None.
        pin_cyl_extra (float, optional): pin-engagement constant from the
            original FreeCAD source. Defaults to 1.5.
        pin_end_offset (float, optional): pin-engagement constant from the
            original FreeCAD source. Defaults to 0.5.
        pin_short_cyl_factor (float, optional): pin-engagement constant from
            the original FreeCAD source. Defaults to 1/3.

    Attributes:
        params (HingeParams): the parameters the hinge was built from.
        cylinder_side (Compound): leaf with the bored knuckle tabs
            (label ``"cylinder_side"``). Joints: ``"pivot"``, a RevoluteJoint
            on the hinge axis.
        pin_side (Compound): leaf with the end caps and the captured pin
            (label ``"pin_side"``). Joints: ``"pivot"``, a RigidJoint on the
            hinge axis; ``cylinder_side.joints["pivot"].connect_to(
            pin_side.joints["pivot"], angle=a)`` swings it, 0 = flat-open,
            180 = closed.
        leaf_width (float): X distance from the axis to each leaf's outer face.
        axis_z (float): height of the hinge axis above the bed.

    Raises:
        ValueError: non-positive case_h, hinge_length or mounting_flat; odd or
            < 2 stations; negative pivot_z_offset or one not smaller than the
            knuckle radius; bore too small for pivot_clearance.
    """

    def __init__(
        self,
        case_h: float,
        hinge_length: float,
        stations: int = 6,
        knuckle: Knuckle = Knuckle.FULL,
        mounting_flat: float = 0.5,
        pivot_clearance: float = 0.6,
        pivot_z_offset: float = 0.2,
        clasp_clearance: Optional[float] = None,
        pin_cyl_extra: float = 1.5,
        pin_end_offset: float = 0.5,
        pin_short_cyl_factor: float = 1 / 3,
    ):
        self.params = HingeParams(
            case_h=case_h,
            hinge_length=hinge_length,
            stations=stations,
            knuckle=knuckle,
            mounting_flat=mounting_flat,
            pivot_clearance=pivot_clearance,
            pivot_z_offset=pivot_z_offset,
            clasp_clearance=clasp_clearance,
            pin_cyl_extra=pin_cyl_extra,
            pin_end_offset=pin_end_offset,
            pin_short_cyl_factor=pin_short_cyl_factor,
        )
        resolved = self.params._resolve()
        self.leaf_width = resolved["W"]
        self.axis_z = case_h + pivot_z_offset
        cylinder_side, pin_side = _build_leaves(resolved)
        # pin_side's rigid frame is the pivot axis's own frame, so the leaves
        # coincide at angle 0; the axis runs along +Y, so a positive angle
        # lifts pin_side up and over onto cylinder_side.
        pivot = Axis((0, 0, self.axis_z), (0, 1, 0))
        RevoluteJoint("pivot", cylinder_side, axis=pivot)
        RigidJoint("pivot", pin_side, pivot.location)
        super().__init__(label="PrintInPlaceHinge", children=[cylinder_side, pin_side])

    @property
    def cylinder_side(self) -> Compound:
        return self.children[0]

    @property
    def pin_side(self) -> Compound:
        return self.children[1]


def make_hinge(params: Optional[HingeParams] = None) -> PrintInPlaceHinge:
    """Build a PrintInPlaceHinge from a HingeParams.

    Args:
        params (HingeParams, optional): hinge parameters. Defaults to
            ``HingeParams(case_h=10, hinge_length=60)``.

    Returns:
        PrintInPlaceHinge: see its docstring for the frame, the two named
        leaves and the joints.
    """
    if params is None:
        params = HingeParams(case_h=10.0, hinge_length=60.0)
    return PrintInPlaceHinge(**dataclasses.asdict(params))

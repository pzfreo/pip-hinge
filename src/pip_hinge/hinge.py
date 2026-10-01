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

    FULL and HALF are percentages of twice the lifted wall height
    (``2 × (case_h + pivot_z_offset)``). SMALL has diameter
    ``max((case_h + pivot_z_offset)/2, 5 mm)``: one quarter of FULL with a
    5 mm floor that leaves room for the bore and pin on small cases.
    """

    FULL = 100   # diameter = 2 × lifted wall height; bottom rests on bed
    HALF = 50    # diameter = lifted wall height; self-supporting underside
    SMALL = -1   # sentinel — see _resolve() for the actual size formula


class PinStyle(Enum):
    """Shape of the pin captured inside the cylinder-side knuckles.

    CONICAL uses 45-degree tips and matching bores. ROUNDED retains the
    original hemispherical tips and round bores. BRIDGED runs one cylindrical
    pin through every knuckle under a teardrop bore roof. It is experimental:
    its roof and unsupported pin spans have not been print-tested together.
    """

    CONICAL = "conical"
    ROUNDED = "rounded"
    BRIDGED = "bridged"


class FitProfile(Enum):
    """Clearance defaults derived from a printed subset of hinge sizes.

    The successful prints used the earlier cylindrical bore; retest the
    current shaped bore before relying on the same fit. TIGHT narrows the
    clearance on approximately 5 mm conical SMALL knuckles. It also
    narrows the axial tab gap when the station pitch is at most 6 mm.
    Explicit pivot_clearance and clasp_clearance values always take priority.
    """

    STANDARD = "standard"
    TIGHT = "tight"


@dataclass(frozen=True)
class HingeParams:
    """Parameters for :class:`PrintInPlaceHinge`, as a reusable value.

    Fields are the keyword arguments of PrintInPlaceHinge; see its ``Args:``
    for what each one means. ``make_hinge(params)`` builds the hinge.

    Attributes:
        case_h (float): height in mm of the case wall that each leaf joins.
        hinge_length (float): total length in mm along the rotation axis (Y).
        stations (int): number of alternating tab positions along Y; even
            and at least 2. The two end tabs each occupy half a position.
        knuckle (Knuckle): outer diameter of the round hinge barrels,
            selected from FULL, HALF, or SMALL relative to the case height.
        pin_style (PinStyle): CONICAL tips, ROUNDED tips, or one continuous
            BRIDGED pin.
        knuckle_wall (float | None): radial wall thickness in mm around each
            bore at the widest round section.
            None uses at least 1 mm of wall for CONICAL while keeping adjacent
            tips separate, the original bore size for ROUNDED, and at least
            1 mm above the BRIDGED bore's teardrop roof.
            Short conical hinges may need a thicker wall to fit the tips.
        mounting_flat (float): width in mm of the flat attachment strip beyond
            each knuckle's outer edge, toward the case wall. It keeps the
            attached wall clear of the rotating barrel.
        pivot_clearance (float | None): difference in mm between bore and pin
            diameters at the straight shank. The radial gap there, and the
            normal gap between CONICAL slopes, is half this value. None
            selects the fit profile's default.
        pivot_z_offset (float): height in mm of the rotation axis above the
            case wall top. The closed seam gap is twice this value.
        clasp_clearance (float | None): gap in mm along Y between adjacent
            cylinder-side and pin-side tabs. None selects the fit profile's
            default.
        fit_profile (FitProfile): STANDARD retains the original clearances;
            TIGHT applies the tested small-conical-knuckle heuristic.
        pin_cyl_extra (float): amount in mm added to one station width to
            set each middle pin's straight shank length. Its protrusion
            beyond each neighbouring tab face is half this plus half the
            tab gap.
        pin_end_offset (float): distance in mm that each end pin's straight
            shank protrudes past its end cap face. Its reach beyond the
            neighbouring tab face is this value minus clasp_clearance.
        pin_short_cyl_factor (float): end pin shank length as a fraction of
            one tab position's width; the rest is buried in the end cap.
    """

    case_h: float
    hinge_length: float
    stations: int = 6
    knuckle: Knuckle = Knuckle.FULL
    mounting_flat: float = 0.5
    pivot_clearance: Optional[float] = None
    pivot_z_offset: float = 0.2
    clasp_clearance: Optional[float] = None
    pin_cyl_extra: float = 1.5
    pin_end_offset: float = 0.5
    pin_short_cyl_factor: float = 1 / 3
    pin_style: PinStyle = PinStyle.CONICAL
    knuckle_wall: Optional[float] = None
    fit_profile: FitProfile = FitProfile.STANDARD

    def _resolve(self) -> dict:
        if self.case_h <= 0:
            raise ValueError(f"case_h must be > 0 (got {self.case_h})")
        if self.hinge_length <= 0:
            raise ValueError(f"hinge_length must be > 0 (got {self.hinge_length})")
        if isinstance(self.stations, bool) or not isinstance(self.stations, int):
            raise ValueError(f"stations must be an even integer ≥ 2 (got {self.stations!r})")
        if self.stations < 2 or self.stations % 2 != 0:
            raise ValueError(
                f"stations must be an even integer ≥ 2 (got {self.stations})"
            )
        if not isinstance(self.knuckle, Knuckle):
            raise ValueError(f"knuckle must be a Knuckle (got {self.knuckle!r})")
        if not isinstance(self.pin_style, PinStyle):
            raise ValueError(f"pin_style must be a PinStyle (got {self.pin_style!r})")
        if not isinstance(self.fit_profile, FitProfile):
            raise ValueError(f"fit_profile must be a FitProfile (got {self.fit_profile!r})")
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
            # at any case height. For effective_case_h ≥ 10 mm the ratio
            # dominates; below that the 5 mm floor kicks in.
            Po = max(effective_case_h / 2, 5.0)
        else:
            Po = 2 * effective_case_h * self.knuckle.value / 100
        Ro = Po / 2
        if self.pivot_z_offset >= Ro:
            raise ValueError(
                f"pivot_z_offset ({self.pivot_z_offset}) must be < knuckle radius "
                f"({Ro:.2f})"
            )
        Cw = self.hinge_length / self.stations
        # The TIGHT rules cover only the printed conical SMALL barrels near
        # 5 mm diameter. The two successful test cases had pitches 6 and 8 mm;
        # only the 6 mm case needed less axial play.
        tight_small = (self.fit_profile is FitProfile.TIGHT
                       and self.pin_style is PinStyle.CONICAL
                       and self.knuckle is Knuckle.SMALL
                       and Po <= 5.5)
        Pc = ((0.4 if tight_small else 0.6)
              if self.pivot_clearance is None else self.pivot_clearance)
        Cc = ((0.2 if tight_small and Cw <= 6 else 0.3)
              if self.clasp_clearance is None else self.clasp_clearance)
        if Cc <= 0 or Cc >= Cw:
            raise ValueError(
                f"clasp_clearance must be > 0 and < station width {Cw:.2f} "
                f"(got {Cc})"
            )
        tab_width = Cw - Cc
        if tab_width < 3:
            warnings.warn(
                f"tab width = {tab_width:.2f}mm is below ~3mm; likely too thin for FDM. "
                "Reduce stations or increase hinge_length.",
                stacklevel=3,
            )
        if self.pin_style is not PinStyle.BRIDGED:
            if (self.pin_cyl_extra < 0 or self.pin_end_offset < 0
                    or not 0 < self.pin_short_cyl_factor <= 1):
                raise ValueError(
                    "pin shank lengths must be non-negative and "
                    "pin_short_cyl_factor in (0, 1]"
                )
            end_shank = Cw * self.pin_short_cyl_factor
            if not (self.pin_end_offset < end_shank
                    <= self.pin_end_offset + tab_width / 2):
                raise ValueError(
                    "end pin shank must reach into its end cap without "
                    "extending beyond the hinge end"
                )

        max_tip_radius = None
        if self.pin_style is not PinStyle.BRIDGED:
            k = self.stations // 2
            # Both conical and hemispherical tips extend along Y by their
            # radius. Keep even the outermost tip inside hinge_length.
            end_base = (k - 0.5) * Cw + Cc / 2 - self.pin_end_offset
            max_tip_radius = self.hinge_length / 2 + end_base
            if k > 1:
                outer_middle = (k - 2) * Cw
                middle_limit = (self.hinge_length / 2 - outer_middle
                                - (Cw + self.pin_cyl_extra) / 2)
                max_tip_radius = min(max_tip_radius, middle_limit)
            # A tip extends one radius along Y. Without this limit,
            # neighbouring tips can meet inside a bored tab. Conical pins
            # must retain a Cc gap so they do not form an unsupported span.
            if k == 1:
                separate_tip_limit = end_base - Cc / 2
            else:
                outer_middle_base = (k - 2) * Cw + (Cw + self.pin_cyl_extra) / 2
                separate_tip_limit = (end_base - outer_middle_base - Cc) / 2
                if k > 2:
                    separate_tip_limit = min(
                        separate_tip_limit,
                        (Cw - self.pin_cyl_extra - Cc) / 2,
                    )
            if self.pin_style is PinStyle.CONICAL:
                max_tip_radius = min(max_tip_radius, separate_tip_limit)
            if max_tip_radius <= 0:
                raise ValueError(
                    "pin shanks leave no room for pin tips within hinge_length; "
                    "reduce stations or pin_cyl_extra"
                )

        if self.knuckle_wall is None:
            # The 45-degree cone can use most of the barrel radius while
            # retaining at least 1 mm of material around the bore.
            # Short hinges may need a thicker wall to keep tips in bounds and
            # separate from the neighbouring segments.
            if self.pin_style is PinStyle.CONICAL:
                wall = max(1.0, 0.1 * Ro, Ro - max_tip_radius - Pc / 2)
            elif self.pin_style is PinStyle.BRIDGED:
                # The 45-degree bore roof rises to sqrt(2) times the round
                # bore radius. Preserve at least 1 mm of material above it.
                wall = max(Ro / 2, Ro - (Ro - 1.0) / math.sqrt(2))
            else:
                wall = Ro / 2
        else:
            wall = self.knuckle_wall
        if wall <= 0 or wall >= Ro:
            raise ValueError(
                f"knuckle_wall must be > 0 and < knuckle radius {Ro:.2f} "
                f"(got {wall})"
            )
        Pi = 2 * (Ro - wall)                       # bore diameter
        if Pc <= 0 or Pi <= Pc:
            raise ValueError(
                f"pivot_clearance must be > 0 and smaller than bore Ø "
                f"({Pi:.2f}); got {Pc}"
            )
        if (self.pin_style is PinStyle.BRIDGED
                and Ro - math.sqrt(2) * Pi / 2 < 1.0 - 1e-9):
            raise ValueError(
                "knuckle_wall leaves less than 1 mm above the bridged bore's "
                "self-supporting roof; increase knuckle_wall"
            )
        if (max_tip_radius is not None
                and Pi / 2 - Pc / 2 > max_tip_radius + 1e-9):
            raise ValueError(
                "pin tips exceed available space within hinge_length or touch "
                "neighbouring tips; increase hinge_length or knuckle_wall, "
                "or reduce pin_cyl_extra"
            )
        if (self.pin_style is PinStyle.ROUNDED
                and Pi / 2 - Pc / 2 > separate_tip_limit + Cc / 2 + 1e-9):
            warnings.warn(
                "rounded pin tips meet inside a bore at this station pitch; "
                "the joined span may sag or fuse during printing. Increase "
                "hinge_length or knuckle_wall to separate them.",
                stacklevel=3,
            )
        return {
            "case_h": self.case_h,
            "H": self.hinge_length,
            "stations": self.stations,
            "Po": Po,
            "Ro": Ro,
            "T": Ro,                                 # T = Ro by construction
            "Pi": Pi,
            "knuckle_wall": wall,
            "Pc": Pc,
            "W": Ro + self.mounting_flat,
            "Cw": Cw,
            "Cc": Cc,
            "pin_style": self.pin_style,
            "pivot_z_offset": self.pivot_z_offset,
            "pin_cyl_extra": self.pin_cyl_extra,
            "pin_end_offset": self.pin_end_offset,
            "pin_short": self.pin_short_cyl_factor,
        }


# ── pocket polylines (parametric in N stations) ───────────────────────────────

def _cs_pocket_polyline(N: int, Cw: float, Cc: float, Xi: float, Xo_cs: float):
    """Pocket cut for the cs (cylinder-side) leaf. Excludes N/2 cs tabs.

    cs tabs (with bores in them) sit at Y centres spaced 2·Cw apart,
    symmetric around Y = 0. Each tab is Cw − Cc wide; the matching ps tabs
    are the same width, leaving Cc between their neighbouring faces.
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


def _ps_pocket_polyline(N: int, Cw: float, Cc: float, Xi: float, Xo_ps: float):
    """Pocket cut for the ps (pin-side) leaf. Excludes ps end-caps + middle tabs.

    Pattern along Y: ps end cap | cs | ps middle | cs | ... | ps end cap.
    Middle ps and cs tabs are both Cw-Cc wide. Each end cap is
    (Cw-Cc)/2 wide, leaving Cc between every adjacent pair of tabs.
    """
    k = N // 2
    ps_outer = (k - 0.5) * Cw + Cc / 2       # inner edge of the ps end-caps
    ps_centres = [(-(k - 2) + 2 * i) * Cw for i in range(k - 1)]
    half_tab = (Cw - Cc) / 2

    pts = [
        (-Xi,   -ps_outer),
        (Xo_ps, -ps_outer),
        (Xo_ps,  ps_outer),
        (-Xi,    ps_outer),
    ]
    for Y_c in reversed(ps_centres):         # walk back down with notches
        pts.extend([
            (-Xi, Y_c + half_tab),
            (Xi,  Y_c + half_tab),
            (Xi,  Y_c - half_tab),
            (-Xi, Y_c - half_tab),
        ])
    pts.append((-Xi, -ps_outer))
    return Polyline(*pts)


# ── pin segments (parametric in N stations) ───────────────────────────────────

def _pin_loops(N: int, Cw: float, Cc: float, Rp: float, style: PinStyle,
               pin_cyl_extra: float, pin_end_offset: float, pin_short: float):
    """2D pin profiles to be revolved around Y axis.

    A continuous cylinder for BRIDGED; otherwise one pin with two tips per
    middle tab plus an inward-pointing pin at each end cap.
    """
    if style is PinStyle.BRIDGED:
        half_length = N * Cw / 2
        return [Polyline(
            (0, -half_length), (Rp, -half_length),
            (Rp, half_length), (0, half_length), (0, -half_length),
        )]

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
        if style is PinStyle.CONICAL:
            loops.append(Polyline(
                (Rp, y_top), (Rp, y_bot), (0, y_cap_b),
                (0, y_cap_t), (Rp, y_top),
            ))
        else:
            loops.append(
                Line((Rp, y_top), (Rp, y_bot))
                + CenterArc(center=(0, y_bot), radius=Rp, start_angle=360, arc_size=-90)
                + Line((0, y_cap_b), (0, y_cap_t))
                + CenterArc(center=(0, y_top), radius=Rp, start_angle=90, arc_size=-90)
            )

    # End-cap pins point toward the centre; their far ends are buried inside
    # the ps end-cap material.
    end_inner = (k - 0.5) * Cw + Cc / 2
    cyl_short = Cw * pin_short
    y_short_cyl_b = end_inner - pin_end_offset
    y_short_cyl_t = y_short_cyl_b + cyl_short
    y_short_cap_b = y_short_cyl_b - Rp

    if style is PinStyle.CONICAL:
        loops.append(Polyline(
            (0, y_short_cyl_t), (Rp, y_short_cyl_t),
            (Rp, y_short_cyl_b), (0, y_short_cap_b),
            (0, y_short_cyl_t),
        ))
        loops.append(Polyline(
            (0, -y_short_cyl_t), (Rp, -y_short_cyl_t),
            (Rp, -y_short_cyl_b), (0, -y_short_cap_b),
            (0, -y_short_cyl_t),
        ))
    else:
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


def _bridged_bore_profile(radius: float):
    """Round lower bore with a 45-degree roof above the continuous pin."""
    shoulder = radius / math.sqrt(2)
    return (CenterArc(center=(0, 0), radius=radius,
                      start_angle=135, arc_size=270)
            + Polyline((shoulder, shoulder), (0, 2 * shoulder),
                       (-shoulder, shoulder)))


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
    if p["pin_style"] is PinStyle.CONICAL:
        # The cut follows the actual shanks and 45-degree tips, expanded by
        # Pc/2 radially. The same slope puts the cavity apex Pc/2 beyond the
        # pin apex, providing both radial and axial tip clearance.
        cs_section = make_face(cs_profile)
    elif p["pin_style"] is PinStyle.BRIDGED:
        cs_section = make_face(cs_profile) - make_face(_bridged_bore_profile(Ri))
    else:
        cs_section = make_face(cs_profile) - Circle(Ri)
    cs_sketch = Sketch() + Plane.XZ * cs_section
    cs_pad = extrude(cs_sketch, amount=H / 2, both=True)
    # Pocket polygon left edge must stay left of the notch jogs (which go to -Xi),
    # otherwise the polyline self-intersects and OCC misclassifies the interior.
    # Old defaults happened to satisfy Xi − W ≤ −Xi; the new API's small W doesn't.
    Xo_cs = min(Xi - W, -Xi - 1.0)
    cs_pocket = make_face(_cs_pocket_polyline(N, Cw, Cc, Xi, Xo_cs))
    cylinder_side = cs_pad - extrude(cs_pocket, amount=pocket_extrude, both=True)
    if p["pin_style"] is PinStyle.CONICAL:
        # Moving the 45-degree cone base toward its tip by this distance
        # gives Pc/2 clearance measured normal to the cone, while retaining
        # Pc/2 radial clearance along the straight shanks.
        cone_shift = (math.sqrt(2) - 1) * Pc / 2
        for cavity in _pin_loops(N, Cw, Cc, Ri, PinStyle.CONICAL,
                                 p["pin_cyl_extra"] + 2 * cone_shift,
                                 p["pin_end_offset"] + cone_shift,
                                 p["pin_short"] + cone_shift / Cw):
            cylinder_side = cylinder_side - revolve(
                make_face(cavity), axis=Axis.Y, revolution_arc=-360)

    # ── ps (pin-side) leaf ───────────────────────────────────────────────────
    ps_profile = _leaf_profile(-W)
    ps_sketch = Sketch() + Plane.XZ * make_face(ps_profile)
    ps_pad = extrude(ps_sketch, amount=H / 2, both=True)
    Xo_ps = 4 * Po - Xi
    ps_pocket = make_face(_ps_pocket_polyline(N, Cw, Cc, Xi, Xo_ps))
    pin_side = ps_pad - extrude(ps_pocket, amount=pocket_extrude, both=True)

    # ── pin segments ────────────────────────────────────────────────────────
    loops = _pin_loops(N, Cw, Cc, Rp, p["pin_style"],
                       p["pin_cyl_extra"], p["pin_end_offset"], p["pin_short"])
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
        case_h (float): height in mm of the case wall each leaf attaches to.
        hinge_length (float): hinge length in mm along its rotation axis (Y).
        stations (int): number of alternating tab positions along Y; even
            and at least 2. The two end tabs each take half a position.
        knuckle (Knuckle): size of the round hinge barrels relative to case_h.
        pin_style (PinStyle): CONICAL tips for 45-degree slopes, ROUNDED tips
            as in the original hinge, or one continuous BRIDGED pin. BRIDGED
            needs a printer-specific bridge and clearance test.
        knuckle_wall (float | None): radial thickness in mm of the knuckle
            material around its bore at the widest round section. None gives
            CONICAL at least 1.0 mm of wall, uses the original half-radius
            wall for ROUNDED, and keeps at least 1.0 mm above the BRIDGED roof.
            On short hinges the conical wall grows to keep tips within the
            stated length and separate from neighbouring tips. Reduce only
            if your printer can make a thinner wall and the tips still fit.
        mounting_flat (float): width in mm of the flat leaf strip beyond the
            knuckle edge where the case wall attaches. This keeps the wall
            clear of the rotating barrel. At or below
            the resolved ``pivot_clearance`` the bare leaf may have separate solids; fusing
            it to the case wall joins them.
        pivot_clearance (float | None): difference in mm between the bore and
            pin diameters at the straight shank. The radial gap there, and
            the normal gap between CONICAL slopes, is half this value. None
            selects the fit profile's default.
        pivot_z_offset (float): height in mm of the axis above the case wall
            top. This leaves a closed seam gap twice as large; the leaf tops
            remain flush with the wall top. Zero removes the offset.
        clasp_clearance (float | None): gap in mm along Y between adjacent
            cylinder-side and pin-side tabs. None selects the fit profile's
            default. An explicit value overrides it.
        fit_profile (FitProfile): STANDARD uses 0.3 mm radial and axial gaps.
            TIGHT uses 0.2 mm radial gap on conical SMALL knuckles up to 5.5 mm
            diameter, and 0.2 mm axial gap when their station pitch is at most
            6 mm. Other sizes retain STANDARD gaps.
        pin_cyl_extra (float): amount in mm added to one station width to
            determine each middle pin's straight shank length. The shank
            protrudes ``(pin_cyl_extra + clasp_clearance) / 2`` beyond each
            middle tab face.
        pin_end_offset (float): distance in mm an end pin's straight shank
            protrudes past its end cap face. Its reach into the neighbouring
            bored tab is this value minus clasp_clearance.
        pin_short_cyl_factor (float): end pin's straight shank length as a
            fraction of one station width. The far end is buried in the cap.
            These three shank settings do not affect BRIDGED pins.

    Attributes:
        params (HingeParams): the parameters the hinge was built from.
        cylinder_side (Compound): leaf with the bored knuckle tabs
            (label ``"cylinder_side"``). Joints: ``"pivot"``, a RevoluteJoint
            on the hinge axis; ``"mount"``, a RigidJoint at the bottom centre
            of its outer face (X = +leaf_width, Y = 0, Z = 0), axes aligned
            with the hinge frame.
        pin_side (Compound): leaf with the end caps and the captured pin
            (label ``"pin_side"``). Joints: ``"pivot"``, a RigidJoint on the
            hinge axis; ``cylinder_side.joints["pivot"].connect_to(
            pin_side.joints["pivot"], angle=a)`` swings it, 0 = flat-open,
            180 = closed. ``"mount"``, as for cylinder_side but at
            X = −leaf_width.
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
        pivot_clearance: Optional[float] = None,
        pivot_z_offset: float = 0.2,
        clasp_clearance: Optional[float] = None,
        pin_cyl_extra: float = 1.5,
        pin_end_offset: float = 0.5,
        pin_short_cyl_factor: float = 1 / 3,
        pin_style: PinStyle = PinStyle.CONICAL,
        knuckle_wall: Optional[float] = None,
        fit_profile: FitProfile = FitProfile.STANDARD,
    ):
        self.params = HingeParams(
            case_h=case_h,
            hinge_length=hinge_length,
            stations=stations,
            knuckle=knuckle,
            pin_style=pin_style,
            knuckle_wall=knuckle_wall,
            fit_profile=fit_profile,
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
        # Mounting points: bottom centre of each leaf's outer face, axes
        # aligned with the hinge frame.
        RigidJoint("mount", cylinder_side, Location((self.leaf_width, 0, 0)))
        RigidJoint("mount", pin_side, Location((-self.leaf_width, 0, 0)))
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

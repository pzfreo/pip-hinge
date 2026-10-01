"""Tests for the print-in-place piano hinge.

The default hinge is designed to print flat without slicer support: SMALL
knuckles reach the bed with a tangent ramp, HALF knuckles with a self-supporting
teardrop, and FULL knuckles rest the disc on the bed. The optional BRIDGED pin
requires unsupported spans inside the bores. One small clamshell print released,
but its hinge rocked noticeably.
These tests build hinges across that range and assert:

  * the build succeeds and is a valid, manifold, multi-solid Compound;
  * the two leaves do not fuse or collide (a positive print-in-place gap);
  * no exterior face overhangs below the self-support angle.

Self-support is checked directly on the BREP (augura, the MCP printability
engine, is not importable here): we walk every face, orient its normal outward
with a solid classifier, and flag any downward-facing patch shallower than the
threshold. The pin and the bore it sits in are clearance features that print in
place; they are excluded by radius (inner cylinders smaller than the disc).
"""
import math

import pytest
from build123d import Compound

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepLProp import BRepLProp_SLProps
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.TopAbs import TopAbs_REVERSED, TopAbs_IN
from OCP.gp import gp_Pnt
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

from build123d import Box, Pos

from pip_hinge import FitProfile, HingeParams, Knuckle, PinStyle, PrintInPlaceHinge, make_hinge

# (knuckle, case_h) covering each underside strategy and a span of disc sizes.
CASES = [
    (Knuckle.SMALL, 12.0),
    (Knuckle.SMALL, 17.0),   # the gibson tuner case
    (Knuckle.SMALL, 30.0),
    (Knuckle.HALF, 20.0),
    (Knuckle.HALF, 30.0),    # teardrop territory
    (Knuckle.HALF, 40.0),
    (Knuckle.FULL, 12.0),
    (Knuckle.FULL, 24.0),
]

SELF_SUPPORT_DEG = 45.0
ANGLE_TOL = 1.0          # allow 1 deg of float slop at the 45 deg boundary
BED_TOL = 0.3            # faces this close to z=0 are the print bed, not overhangs
SAMPLES = 9              # parametric samples per face axis


def _params(knuckle, case_h):
    return HingeParams(case_h=case_h, hinge_length=96, stations=8,
                       knuckle=knuckle, mounting_flat=1.0)


def _leaf_solids(hinge):
    """Split the hinge into its two leaves by leaf-body X sign (pin sits at X=0
    and rides with the pin-side group)."""
    cs = [s for s in hinge.solids() if s.center().X > 0.05]
    ps = [s for s in hinge.solids() if s.center().X <= 0.05]
    return Compound(cs), Compound(ps)


def _overhangs(solid, bed_z, axis_z=None, disc_r=None):
    """Return (point, angle_deg) for every exterior, downward-facing surface
    sample shallower than the self-support angle.

    Excluded:
      * bed-contact faces (within BED_TOL of the bed plane bed_z -- the leaf
        bottom, which the pivot lift puts at z = -case_h, not z = 0);
      * everything inside the disc radius of the pivot axis (axis_z, disc_r):
        the bore and the captured pin, which are print-in-place clearance
        features. Every real self-support surface -- wall, ramp, teardrop
        underside, exposed disc arc -- lies at radius >= disc_r, so this masks
        only the clearance region while still scanning all load-bearing faces.
    """
    threshold = math.cos(math.radians(SELF_SUPPORT_DEG - ANGLE_TOL))  # |nz| above this = too flat
    classifier = BRepClass3d_SolidClassifier(solid.wrapped)
    inner = (disc_r - 0.3) if disc_r is not None else -1.0
    bad = []
    for face in solid.faces():
        surf = BRepAdaptor_Surface(face.wrapped)
        reversed_ = face.wrapped.Orientation() == TopAbs_REVERSED
        u0, u1 = surf.FirstUParameter(), surf.LastUParameter()
        v0, v1 = surf.FirstVParameter(), surf.LastVParameter()
        for i in range(SAMPLES):
            for j in range(SAMPLES):
                u = u0 + (u1 - u0) * (i + 0.5) / SAMPLES
                v = v0 + (v1 - v0) * (j + 0.5) / SAMPLES
                props = BRepLProp_SLProps(surf, u, v, 1, 1e-6)
                if not props.IsNormalDefined():
                    continue
                p = props.Value()
                if axis_z is not None and math.hypot(p.X(), p.Z() - axis_z) < inner:
                    continue                     # bore / pin clearance region
                n = props.Normal()
                if reversed_:
                    n.Reverse()
                # Orient outward: a hair along +n must be outside the solid.
                probe = gp_Pnt(p.X() + 0.02 * n.X(), p.Y() + 0.02 * n.Y(), p.Z() + 0.02 * n.Z())
                classifier.Perform(probe, 1e-7)
                if classifier.State() == TopAbs_IN:
                    n.Reverse()
                if n.Z() < 0 and abs(n.Z()) > threshold and p.Z() > bed_z + BED_TOL:
                    bad.append(((p.X(), p.Y(), p.Z()),
                                math.degrees(math.acos(min(1.0, abs(n.Z()))))))
    return bad


@pytest.fixture(scope="module")
def hinges():
    return {(k, h): make_hinge(_params(k, h)) for k, h in CASES}


@pytest.mark.parametrize("knuckle,case_h", CASES)
def test_builds_valid(hinges, knuckle, case_h):
    h = hinges[(knuckle, case_h)]
    assert h.is_valid
    assert h.volume > 0
    # All CASES use mounting_flat=1.0 > pivot_clearance, so each leaf must be a
    # single connected body: exactly two solids (cs leaf, ps leaf + captured pin).
    # `>= 2` would pass the fragmented pile a too-small mounting_flat produces;
    # `== 2` is what makes this catch a leaf that silently breaks apart.
    assert len(h.solids()) == 2, f"expected 2 connected leaves, got {len(h.solids())}"
    cs, ps = _leaf_solids(h)
    assert cs.volume > 0 and ps.volume > 0


@pytest.mark.parametrize("knuckle,case_h", CASES)
def test_leaves_have_print_gap(hinges, knuckle, case_h):
    """The leaves must stay separate so the hinge articulates after printing."""
    cs, ps = _leaf_solids(hinges[(knuckle, case_h)])
    dss = BRepExtrema_DistShapeShape(cs.wrapped, ps.wrapped)
    dss.Perform()
    gap = dss.Value()
    assert gap > 0.05, f"leaves nearly touching/fused: gap={gap:.3f} mm"


# SMALL (tangent ramp) and HALF (teardrop) make a crisp guarantee: the meshing
# underside reaches the bed at >= 45 deg. FULL rests the whole disc on the bed --
# a convex bed-supported surface that prints fine (augura agrees) but dips below
# 45 deg near the contact, which a flat-overhang scan would wrongly flag, so it is
# covered by the build/gap tests only.
SELF_CASES = [(k, h) for k, h in CASES if k is not Knuckle.FULL]


@pytest.mark.parametrize("knuckle,case_h", SELF_CASES)
def test_self_supporting(hinges, knuckle, case_h):
    """No exterior face on a ramp/teardrop leaf may overhang below 45 deg."""
    h = hinges[(knuckle, case_h)]
    res = _params(knuckle, case_h)._resolve()
    axis_z, disc_r = case_h + res["pivot_z_offset"], res["Ro"]
    bed_z = h.bounding_box().min.Z
    bad = []
    for solid in h.solids():
        bad += _overhangs(solid, bed_z, axis_z, disc_r)
    worst = min((a for _, a in bad), default=None)
    assert not bad, (
        f"{knuckle.name} case_h={case_h}: {len(bad)} overhang sample(s), "
        f"shallowest {worst:.1f} deg from horizontal (need >= {SELF_SUPPORT_DEG})")


def test_overhang_scanner_has_teeth():
    """Negative control: the scanner must flag a known overhang. A box lifted
    clear of the bed has a flat, downward-facing bottom (0 deg) that must trip."""
    box = Pos(0, 0, 10) * Box(8, 8, 4)        # bottom face at z=8, well above bed
    bad = _overhangs(box.solids()[0], bed_z=0.0)
    assert bad, "scanner failed to flag an obvious horizontal overhang"
    assert min(a for _, a in bad) < 1.0       # the flat bottom is ~0 deg


def test_scanner_sees_disc_on_bed_overhang():
    """Teeth on real hinge geometry: FULL rests its disc on the bed, whose lower
    arc (at radius = disc_r, so NOT masked by the bore/pin exclusion) dips below
    45 deg. The scanner must SEE it -- that detection is why FULL is excluded from
    test_self_supporting, confirming that exclusion is deliberate, not a blind
    spot that would also hide a broken SMALL/HALF underside."""
    h = make_hinge(_params(Knuckle.FULL, 12.0))
    res = _params(Knuckle.FULL, 12.0)._resolve()
    bed_z = h.bounding_box().min.Z
    bad = []
    for solid in h.solids():
        bad += _overhangs(solid, bed_z, 12.0 + res["pivot_z_offset"], res["Ro"])
    assert bad, "scanner missed the disc-on-bed overhang; the FULL exclusion would be a blind spot"


def test_half_no_longer_raises():
    """Regression: a big HALF disc once raised 'no self-supporting ramp'; it now
    builds a teardrop instead."""
    h = make_hinge(_params(Knuckle.HALF, 30.0))
    assert h.is_valid and h.volume > 0


def test_half_underside_meets_disc_at_tangent():
    """The teardrop's straight underside must meet the disc tangentially at the
    45 deg point, not cut a corner across it."""
    p = _params(Knuckle.HALF, 30.0)._resolve()
    Ro, leaf_h = p["Ro"], 30.0 + p["pivot_z_offset"]
    # foot-anchored far tangent for this disc is shallower than 45 -> teardrop path
    th = math.radians(180 + SELF_SUPPORT_DEG)
    tp = (Ro * math.cos(th), Ro * math.sin(th))
    # tangent point lies on the disc...
    assert abs(math.hypot(*tp) - Ro) < 1e-6
    # ...and the line from it to its bed contact descends at exactly the angle.
    run = (leaf_h + tp[1]) / math.tan(math.radians(SELF_SUPPORT_DEG))
    bed = (tp[0] + run, -leaf_h)
    drop_angle = math.degrees(math.atan2(abs(bed[1] - tp[1]), abs(bed[0] - tp[0])))
    assert abs(drop_angle - SELF_SUPPORT_DEG) < 1e-6


def test_zero_mounting_flat_rejected():
    """mounting_flat=0 makes W==Ro, a degenerate profile OCC rejects with a
    cryptic StdFail_NotDone; we must reject it up front with a clear message."""
    with pytest.raises(ValueError, match="mounting_flat"):
        make_hinge(HingeParams(case_h=20, hinge_length=96, stations=8,
                               knuckle=Knuckle.HALF, mounting_flat=0.0))


def test_bare_hinge_fragments_below_pivot_clearance():
    """Documented design point (see PrintInPlaceHinge.cylinder_side / pin_side):
    a BARE hinge with mounting_flat <= pivot_clearance fragments into many solids.
    That is intentional -- it is meant to be fused into a case, where the walls
    bridge the tabs -- so it must NOT be 'fixed' with a guard. Lock the threshold
    so it can't drift silently: at/below pivot_clearance it fragments, just above
    it is a clean 2-body hinge."""
    pc = 0.6
    common = dict(case_h=20, hinge_length=96, stations=8, knuckle=Knuckle.HALF,
                  pivot_clearance=pc)
    fragmented = make_hinge(HingeParams(mounting_flat=pc, **common))
    connected = make_hinge(HingeParams(mounting_flat=pc + 0.1, **common))
    assert len(fragmented.solids()) > 2          # intentional: fuses into a case
    assert len(connected.solids()) == 2          # bare hinge is whole above threshold


def test_placed_frame_and_named_leaves():
    """Bed at Z=0, leaves out to +/-leaf_width, axis at case_h + pivot_z_offset,
    and the two leaves reachable by name whatever the solid count."""
    h = PrintInPlaceHinge(case_h=10, hinge_length=60, knuckle=Knuckle.HALF,
                          mounting_flat=1.0)
    bb = h.bounding_box()
    assert bb.min.Z == pytest.approx(0, abs=1e-6)
    assert bb.max.X == pytest.approx(h.leaf_width)
    assert bb.min.X == pytest.approx(-h.leaf_width)
    assert h.axis_z == pytest.approx(10.2)
    assert [c.label for c in h.children] == ["cylinder_side", "pin_side"]
    assert h.cylinder_side.bounding_box().max.X == pytest.approx(h.leaf_width)
    assert h.pin_side.bounding_box().min.X == pytest.approx(-h.leaf_width)
    # fragmented leaves (mounting_flat <= pivot_clearance) still split cleanly
    f = PrintInPlaceHinge(case_h=10, hinge_length=60, knuckle=Knuckle.HALF)
    assert len(f.solids()) > 2
    assert f.cylinder_side.bounding_box().max.X == pytest.approx(f.leaf_width)
    assert f.pin_side.bounding_box().min.X == pytest.approx(-f.leaf_width)


def test_make_hinge_matches_class():
    p = HingeParams(case_h=10, hinge_length=60, knuckle=Knuckle.SMALL)
    h = make_hinge(p)
    assert isinstance(h, PrintInPlaceHinge) and h.params == p


def test_four_station_tabs_share_width_and_have_requested_gap():
    """Issue #16: the centre ps barrel must not consume two stations, and
    clasp_clearance must be the measured gap between adjacent tab faces."""
    h = PrintInPlaceHinge(case_h=10, hinge_length=20, stations=4,
                          knuckle=Knuckle.SMALL, mounting_flat=1.0)
    r = h.params._resolve()
    assert r["Cc"] == pytest.approx(0.3)
    assert r["Cw"] == pytest.approx(5.0)
    # Probe the barrel outside its bore and pin, at the height of the axis.
    x = (r["Pi"] / 2 + r["Ro"]) / 2
    probe = Pos(x, 0, h.axis_z) * Box(0.01, 22, 0.01)
    def spans(part):
        return sorted((s.bounding_box().min.Y, s.bounding_box().max.Y)
                      for s in (part & probe).solids())
    cs, ps = spans(h.cylinder_side), spans(h.pin_side)
    assert len(cs) == 2 and len(ps) == 3
    for actual, expected in zip(cs, [(-7.35, -2.65), (2.65, 7.35)]):
        assert actual == pytest.approx(expected, abs=0.01)
    for actual, expected in zip(ps, [(-10, -7.65), (-2.35, 2.35), (7.65, 10)]):
        assert actual == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize("style", list(PinStyle))
@pytest.mark.parametrize("stations", [2, 4, 6])
def test_pin_styles_are_valid_and_keep_leaves_separate(style, stations):
    """Issue #20: each pin option builds a captured pin with print clearance.
    Only BRIDGED must span the entire hinge axis without a gap."""
    h = PrintInPlaceHinge(case_h=10, hinge_length=stations * 5,
                          stations=stations, knuckle=Knuckle.SMALL,
                          pin_style=style, mounting_flat=1.0)
    assert h.is_valid and len(h.solids()) == 2
    dss = BRepExtrema_DistShapeShape(
        h.cylinder_side.solids()[0].wrapped, h.pin_side.solids()[0].wrapped)
    dss.Perform()
    assert dss.Value() > 0.05
    axis_probe = Pos(0, 0, h.axis_z) * Box(0.01, stations * 5 + 2, 0.01)
    axis_solids = (h.pin_side & axis_probe).solids()
    if style is PinStyle.BRIDGED:
        assert len(axis_solids) == 1
        assert axis_solids[0].bounding_box().size.Y == pytest.approx(stations * 5)
    else:
        assert len(axis_solids) == stations // 2 + 1


def test_clearance_inputs_reject_colliding_geometry():
    with pytest.raises(ValueError, match="pivot_clearance"):
        HingeParams(case_h=10, hinge_length=20, pivot_clearance=0)._resolve()
    with pytest.raises(ValueError, match="clasp_clearance"):
        HingeParams(case_h=10, hinge_length=20, stations=4,
                    clasp_clearance=5)._resolve()


@pytest.mark.parametrize(
    "case_h,hinge_length,stations,expected_axial",
    [(6, 24, 4, 0.2), (10, 48, 6, 0.3)],
)
def test_tight_fit_retains_clearance_values_from_printed_cases(
    case_h, hinge_length, stations, expected_axial
):
    """Printed old and new conical bores used these clearance values."""
    common = dict(case_h=case_h, hinge_length=hinge_length,
                  stations=stations, knuckle=Knuckle.SMALL,
                  pin_style=PinStyle.CONICAL)
    standard = HingeParams(**common)._resolve()
    tight = HingeParams(**common, fit_profile=FitProfile.TIGHT)._resolve()
    assert (standard["Pc"], standard["Cc"]) == pytest.approx((0.6, 0.3))
    assert (tight["Pc"], tight["Cc"]) == pytest.approx((0.4, expected_axial))

    h = PrintInPlaceHinge(**common, fit_profile=FitProfile.TIGHT,
                          mounting_flat=1.0)
    assert h.is_valid and len(h.solids()) == 2
    dss = BRepExtrema_DistShapeShape(
        h.cylinder_side.solids()[0].wrapped, h.pin_side.solids()[0].wrapped)
    dss.Perform()
    assert dss.Value() == pytest.approx(0.2, abs=0.01)


def test_conical_bore_follows_pin_tips():
    """The bore narrows into each knuckle rather than staying cylindrical."""
    h = PrintInPlaceHinge(case_h=10, hinge_length=60, stations=6,
                          knuckle=Knuckle.SMALL, mounting_flat=1.0)
    p = h.params._resolve()
    cs = h.cylinder_side.solids()[0]
    # The central cylinder-side tab runs from Y=-4.85 to +4.85. Near its
    # left face the bore admits the whole shank; farther in it follows the
    # cone, leaving material at the same radius.
    radius = p["Pi"] / 2 - 0.1
    assert not cs.is_inside((0, -4.7, h.axis_z + radius))
    assert cs.is_inside((0, -3.4, h.axis_z + radius))
    assert cs.is_inside((0, 0, h.axis_z))


def test_bridged_bore_has_self_supporting_roof_and_wall():
    h = PrintInPlaceHinge(case_h=10, hinge_length=60, stations=6,
                          knuckle=Knuckle.SMALL, pin_style=PinStyle.BRIDGED,
                          mounting_flat=1.0)
    p = h.params._resolve()
    cs = h.cylinder_side.solids()[0]
    top_of_round_bore = h.axis_z + p["Pi"] / 2
    roof_tip = h.axis_z + math.sqrt(2) * p["Pi"] / 2
    assert not cs.is_inside((0, 0, (top_of_round_bore + roof_tip) / 2))
    assert cs.is_inside((0, 0, roof_tip + 0.1))
    assert p["Ro"] - (roof_tip - h.axis_z) >= 1.0 - 1e-6


def test_tight_fit_is_narrow_and_explicit_clearances_override_it():
    common = dict(case_h=6, hinge_length=24, stations=4,
                  knuckle=Knuckle.SMALL, fit_profile=FitProfile.TIGHT)
    for changes in (
        dict(pin_style=PinStyle.ROUNDED),
        dict(knuckle=Knuckle.HALF),
        dict(case_h=14),  # SMALL barrel diameter exceeds the tested range.
    ):
        p = HingeParams(**(common | changes))._resolve()
        assert (p["Pc"], p["Cc"]) == pytest.approx((0.6, 0.3))
    explicit = HingeParams(**common, pivot_clearance=0.6,
                           clasp_clearance=0.3)._resolve()
    assert (explicit["Pc"], explicit["Cc"]) == pytest.approx((0.6, 0.3))
    with pytest.raises(ValueError, match="fit_profile"):
        HingeParams(**(common | {"fit_profile": "tight"}))._resolve()


def test_conical_pin_uses_more_of_knuckle_without_losing_wall_or_clearance():
    """With enough station pitch, conical tips can use more of the barrel
    while retaining at least 1 mm of modeled wall and the same pin/bore fit."""
    conical = HingeParams(case_h=10, hinge_length=120,
                          pin_style=PinStyle.CONICAL)._resolve()
    rounded = HingeParams(case_h=10, hinge_length=120,
                          pin_style=PinStyle.ROUNDED)._resolve()
    assert conical["knuckle_wall"] >= 1.0
    assert conical["Pi"] > rounded["Pi"]
    assert conical["Pi"] / 2 - conical["Pc"] / 2 > 0.8 * conical["Ro"]
    small = HingeParams(case_h=10, hinge_length=60,
                        knuckle=Knuckle.SMALL)._resolve()
    assert conical["Cc"] == rounded["Cc"] == small["Cc"] == pytest.approx(0.3)


@pytest.mark.parametrize("hinge_length,stations", [(20, 2), (20, 4), (60, 6)])
def test_conical_tips_remain_separate_on_short_full_hinges(hinge_length, stations):
    """Large pin radii once joined adjacent cones through the bored tabs,
    creating an unsupported span in the default print strategy."""
    h = PrintInPlaceHinge(case_h=10, hinge_length=hinge_length,
                          stations=stations, knuckle=Knuckle.FULL,
                          mounting_flat=1.0)
    assert h.is_valid and len(h.solids()) == 2
    probe = Pos(0, 0, h.axis_z) * Box(0.01, hinge_length + 2, 0.01)
    pin_sections = sorted((s.bounding_box().min.Y, s.bounding_box().max.Y)
                          for s in (h.pin_side & probe).solids())
    assert len(pin_sections) == stations // 2 + 1
    for left, right in zip(pin_sections, pin_sections[1:]):
        assert right[0] - left[1] >= h.params._resolve()["Cc"] - 0.02


def test_rounded_warns_when_legacy_tips_join():
    with pytest.warns(UserWarning, match="rounded pin tips meet"):
        HingeParams(case_h=10, hinge_length=60, stations=6,
                    knuckle=Knuckle.FULL,
                    pin_style=PinStyle.ROUNDED)._resolve()


def test_short_full_knuckle_cone_stays_within_hinge_length():
    """A 20 mm, four-station hinge must not grow a pin past its end caps."""
    h = PrintInPlaceHinge(case_h=10, hinge_length=20, stations=4,
                          knuckle=Knuckle.FULL, mounting_flat=1.0)
    assert h.is_valid
    assert h.bounding_box().min.Y == pytest.approx(-10)
    assert h.bounding_box().max.Y == pytest.approx(10)
    assert h.params._resolve()["knuckle_wall"] > 1.0
    with pytest.raises(ValueError, match="hinge_length"):
        HingeParams(case_h=10, hinge_length=20, stations=4,
                    knuckle_wall=1.0)._resolve()


def test_rounded_pin_rejects_length_overrun():
    """A short hinge must fail clearly if a rounded tip would cross its end."""
    with pytest.raises(ValueError, match="hinge_length"):
        HingeParams(case_h=10, hinge_length=20, stations=6,
                    knuckle=Knuckle.FULL, pin_style=PinStyle.ROUNDED)._resolve()


@pytest.mark.parametrize("stations", [2.0, True, "4"])
def test_station_count_requires_an_integer(stations):
    with pytest.raises(ValueError, match="stations"):
        HingeParams(case_h=10, hinge_length=20, stations=stations)._resolve()


def test_thin_tab_warning_uses_printed_width():
    # Pitch is 3.1 mm, but a 0.3 mm face gap leaves only 2.8 mm of material.
    with pytest.warns(UserWarning, match="tab width = 2.80mm"):
        HingeParams(case_h=10, hinge_length=12.4, stations=4)._resolve()


@pytest.mark.parametrize("knuckle", list(Knuckle))
def test_leaf_flush_with_wall_top(knuckle):
    """Issue #16: pivot_z_offset lifts the knuckle only; the mounting flat
    must not stand proud of the wall top (Z = case_h)."""
    h = PrintInPlaceHinge(case_h=10, hinge_length=60, knuckle=knuckle,
                          mounting_flat=1.0, pivot_z_offset=2.0)
    ro = h.params._resolve()["Ro"]
    x = (ro + h.leaf_width) / 2                  # middle of the mounting flat
    for leaf, sx in ((h.cylinder_side, 1), (h.pin_side, -1)):
        top = (leaf & (Pos(sx * x, 0, 0) * Box(0.01, 100, 100))).bounding_box().max.Z
        assert top == pytest.approx(10.0, abs=1e-6)


def test_pivot_joint_folds_closed():
    """Joint at 0 leaves pin_side where it was built; at 180 it folds onto
    cylinder_side with the lid's wall top 2 x pivot_z_offset above the base's."""
    h = PrintInPlaceHinge(case_h=10, hinge_length=60, knuckle=Knuckle.HALF,
                          mounting_flat=1.0)
    built = h.pin_side.bounding_box()
    h.cylinder_side.joints["pivot"].connect_to(h.pin_side.joints["pivot"], angle=0)
    at0 = h.pin_side.bounding_box()
    assert at0.min.X == pytest.approx(built.min.X, abs=1e-6)
    assert at0.min.Z == pytest.approx(built.min.Z, abs=1e-6)
    h.cylinder_side.joints["pivot"].connect_to(h.pin_side.joints["pivot"], angle=180)
    closed = h.pin_side.bounding_box()
    assert closed.max.Z == pytest.approx(2 * h.axis_z)       # old bed face on top
    assert closed.max.X == pytest.approx(h.leaf_width)       # over the base leaf


def test_pivot_z_offset_must_be_below_knuckle_radius():
    with pytest.raises(ValueError, match="pivot_z_offset"):
        PrintInPlaceHinge(case_h=10, hinge_length=60, knuckle=Knuckle.SMALL,
                          pivot_z_offset=4.0)   # Ro = 3.5


def test_mount_joint_places_leaves_on_a_wall():
    """A wall joint connected to cylinder_side's "mount" puts that leaf's
    outer face on it; the pivot joint at 0 then brings pin_side along, and
    the placed leaves fuse into the case where the joint put them."""
    from build123d import Align, Location, RigidJoint
    h = PrintInPlaceHinge(case_h=10, hinge_length=60, knuckle=Knuckle.HALF,
                          mounting_flat=1.0)
    wall = Box(20, 80, 10, align=(Align.MIN, Align.CENTER, Align.MIN))
    wall = Pos(50, 20, 0) * wall                 # back face at X = 50, centred Y = 20
    RigidJoint("hinge", wall, Location((50, 20, 0)))  # global: back face, bottom centre
    wall.joints["hinge"].connect_to(h.cylinder_side.joints["mount"])
    cs = h.cylinder_side.bounding_box()
    assert cs.max.X == pytest.approx(50)
    assert cs.center().Y == pytest.approx(20)
    assert cs.min.Z == pytest.approx(0, abs=1e-6)
    h.cylinder_side.joints["pivot"].connect_to(h.pin_side.joints["pivot"], angle=0)
    ps = h.pin_side.bounding_box()
    assert ps.min.X == pytest.approx(50 - 2 * h.leaf_width)
    assert ps.min.Z == pytest.approx(0, abs=1e-6)
    fused = wall + h.cylinder_side
    assert len(fused.solids()) == 1
    assert fused.bounding_box().min.X == pytest.approx(cs.min.X)   # leaf fused where placed

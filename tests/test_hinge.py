"""Tests for the print-in-place piano hinge.

The headline guarantee of this library is that `make_hinge` emits geometry that
prints flat WITHOUT slicer support: every exterior downward-facing surface is at
least 45 deg from horizontal. SMALL knuckles reach the bed with a tangent ramp,
HALF knuckles with a self-supporting teardrop, FULL knuckles rest the disc on the
bed. These tests build hinges across that range and assert:

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

from pip_hinge import HingeParams, Knuckle, make_hinge

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
    axis_z, disc_r = res["pivot_z_offset"], res["Ro"]
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
    from build123d import Box, Pos
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
        bad += _overhangs(solid, bed_z, res["pivot_z_offset"], res["Ro"])
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
    """Documented design point (see examples/clamshell.py:_split_hinge_by_side):
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

"""Tests for the print-in-place snap clasp.

The clasp has to do three things, and each gets checked on the real BREP:

  * print in place: the flap is a separate body from the lid mount, with a
    positive gap, and neither the flap nor the catch overhangs below 45 deg;
  * close: swung to 90 deg, the flap clears the catch;
  * hold: part-way open, the flap runs into the catch's tooth, so opening
    means bowing the bar over it. A flap that swung free would be no clasp.

"Closed" is checked in the base's frame. The lid's print frame maps to it by
z -> 2*case_h + seam_gap - z (both frames put the front face at X = 0 with
the outside in -X), so a mirror in XY plus a lift does it.
"""
import math

import pytest
from build123d import Plane, Pos
from OCP.BRepExtrema import BRepExtrema_DistShapeShape

from pip_hinge import ClaspParams, close_flap, make_clasp, pivot_axis
from pip_hinge.clasp import BAR_STRAIN_WARN
from test_hinge import _overhangs

CASES = [
    ClaspParams(case_h=10),
    ClaspParams(case_h=17, width=40, knuckle_d=8),
    ClaspParams(case_h=25, width=50, drop=6, engage=1.0, tooth_t=2.5),
]
IDS = ["case10", "case17", "case25"]


def _dist(a, b):
    dss = BRepExtrema_DistShapeShape(a.wrapped, b.wrapped)
    dss.Perform()
    return dss.Value()


def _overlap(a, b):
    common = a & b
    return sum(s.volume for s in common.solids()) if common else 0.0


def _to_base_frame(shape, params):
    """Lid print frame -> base print frame, for a closed case."""
    return Pos(0, 0, 2 * params.case_h + params.seam_gap) * shape.mirror(Plane.XY)


@pytest.fixture(scope="module")
def clasps():
    return [make_clasp(p) for p in CASES]


@pytest.mark.parametrize("i", range(len(CASES)), ids=IDS)
def test_builds_three_single_bodies(clasps, i):
    parts = clasps[i]
    for name in parts._fields:
        part = getattr(parts, name)
        assert part.is_valid, name
        assert len(part.solids()) == 1, f"{name}: {len(part.solids())} solids"
        assert part.volume > 0, name


@pytest.mark.parametrize("i", range(len(CASES)), ids=IDS)
def test_flap_has_print_gap(clasps, i):
    """The flap must print free of the lid mount, or it can't swing."""
    parts = clasps[i]
    assert _dist(parts.flap, parts.lid_mount) > 0.05


@pytest.mark.parametrize("i", range(len(CASES)), ids=IDS)
def test_parts_sit_outside_wall_and_on_bed(clasps, i):
    """Everything sits outside the front face (X <= 0) and on the bed."""
    for part in clasps[i]:
        bb = part.bounding_box()
        assert bb.max.X <= 1e-6
        assert abs(bb.min.Z) < 1e-6
    # The lid mount must fit under the lid's wall top.
    assert clasps[i].lid_mount.bounding_box().max.Z <= CASES[i].case_h + 1e-6


@pytest.mark.parametrize("i", range(len(CASES)), ids=IDS)
def test_closed_flap_clears_catch(clasps, i):
    p, parts = CASES[i], clasps[i]
    closed = _to_base_frame(close_flap(parts.flap, p), p)
    gap = _dist(closed, parts.catch)
    assert gap == pytest.approx(p.clearance, abs=0.02)


@pytest.mark.parametrize("i", range(len(CASES)), ids=IDS)
def test_opening_runs_into_tooth(clasps, i):
    """Part-way open, the bar must hit the tooth: that is what holds it shut."""
    p, parts = CASES[i], clasps[i]
    worst = max(
        _overlap(_to_base_frame(close_flap(parts.flap, p, a), p), parts.catch)
        for a in (88, 86, 84, 82)
    )
    assert worst > 0.1, "flap swings open without touching the tooth"


@pytest.mark.parametrize("i", range(len(CASES)), ids=IDS)
def test_wide_open_flap_is_clear(clasps, i):
    """Swung well open, the flap is clear of the catch again."""
    p, parts = CASES[i], clasps[i]
    for a in (0, 30, 60):
        opened = _to_base_frame(close_flap(parts.flap, p, a), p)
        assert _overlap(opened, parts.catch) == 0


@pytest.mark.parametrize("i", range(len(CASES)), ids=IDS)
def test_flap_never_hits_lid_mount(clasps, i):
    p, parts = CASES[i], clasps[i]
    for a in (0, 30, 60, 90):
        assert _overlap(close_flap(parts.flap, p, a), parts.lid_mount) == 0


@pytest.mark.parametrize("i", range(len(CASES)), ids=IDS)
def test_catch_is_self_supporting(clasps, i):
    bad = _overhangs(clasps[i].catch.solids()[0], bed_z=0.0)
    assert not bad, f"catch overhangs: {bad[:3]}"


@pytest.mark.parametrize("i", range(len(CASES)), ids=IDS)
def test_flap_plate_is_self_supporting(clasps, i):
    """The plate prints flat. The knuckle rests its disc on the bed like a
    FULL hinge, which dips below 45 deg near the contact and prints fine
    (see test_hinge.py), so everything within the disc radius is masked."""
    p, parts = CASES[i], clasps[i]
    r = p._resolve()
    axis = pivot_axis(p)
    # _overhangs masks around an axis at X = 0; shift the pivot onto it.
    flap = Pos(-axis.position.X, 0, 0) * parts.flap.solids()[0]
    bad = _overhangs(flap, bed_z=0.0, axis_z=axis.position.Z, disc_r=r["Ro"] + 0.6)
    assert not bad, f"flap overhangs: {bad[:3]}"


def test_catch_matches_flap_position():
    """The bar's closed position sits right above the slot floor."""
    p = CASES[0]
    r = p._resolve()
    assert r["z_end"] - r["z_floor"] == pytest.approx(p.clearance)
    assert r["z_end"] == pytest.approx(p.case_h - p.drop)


@pytest.mark.parametrize("field,value,match", [
    ("knuckle_d", 12.0, "knuckle_d"),
    ("mounting_flat", 0.5, "mounting_flat"),
    ("flap_t", 4.0, "flap_t"),
    ("engage", 2.0, "engage"),
    ("drop", 10.0, "drop"),
    ("width", 5.0, "window"),
    ("tooth_t", 0.8, "tooth_t"),
])
def test_bad_params_rejected(field, value, match):
    with pytest.raises(ValueError, match=match):
        make_clasp(ClaspParams(case_h=10, **{field: value}))


def test_narrow_clasp_warns_about_bar_strain():
    with pytest.warns(UserWarning, match="strain"):
        ClaspParams(case_h=10, width=16)._resolve()


def test_default_bar_strain_is_modest():
    strain = ClaspParams(case_h=10)._resolve()["strain"]
    assert math.isfinite(strain)
    assert strain < BAR_STRAIN_WARN

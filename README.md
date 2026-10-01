# pip-hinge

A parametric print-in-place piano hinge in [build123d](https://github.com/gumyr/build123d),
designed for clamshell cases.

![clamshell with HALF knuckle and corner magnet pockets, flat-open print orientation](https://raw.githubusercontent.com/pzfreo/pip-hinge/main/docs/diagrams/clamshell_half_preview.png)

Start with four main inputs; the [parameter table](#parameters) covers the remaining fit and geometry controls.

```python
from pip_hinge import Knuckle, PinStyle, PrintInPlaceHinge

hinge = PrintInPlaceHinge(
    case_h        = 10,             # case wall height (mm)
    hinge_length  = 60,             # total hinge length along the axis (mm)
    stations      = 6,              # alternating tab count (even, ≥ 2)
    knuckle       = Knuckle.FULL,   # FULL = "bump on top", no ramp needed
)
base_leaf, lid_leaf = hinge.cylinder_side, hinge.pin_side
```

The default pin has 45° conical tips. Choose `PinStyle.ROUNDED` or the
experimental `PinStyle.BRIDGED` with the `pin_style` argument when needed.

`PrintInPlaceHinge` is a build123d `Compound` with two labelled children,
one per leaf:

- **`cylinder_side`** — the leaf whose knuckle tabs carry the bores;
- **`pin_side`** — the leaf with the end caps and the captured pin.

(Internally these are abbreviated *cs* and *ps*.) Each child is a `Compound`,
because a bare leaf can be several solids — see `mounting_flat` below.

`make_hinge(HingeParams(...))` builds the same thing from a reusable
parameter value.

### Where the hinge comes out

The hinge is built flat-open, in print orientation, ready to fuse into a case
whose walls stand on the bed:

- bed at **Z = 0**, wall top at **Z = `case_h`**;
- hinge axis along **Y** through X = 0, Z = `case_h + pivot_z_offset`;
- `cylinder_side` reaches X = +`hinge.leaf_width`, `pin_side` X = −`hinge.leaf_width`
  — those outer faces are where the two case back walls go;
- Y spans ±`hinge_length / 2`.

So for a base whose back wall's outer face is at X = x0, place the leaves
(build123d children are relative to their parent, so move the leaves
themselves, not the hinge):

```python
from build123d import Pos

at = Pos(x0 - hinge.leaf_width, y_centre, 0)
base = base + at * hinge.cylinder_side
lid = lid + at * hinge.pin_side
```

### Joints

`cylinder_side.joints["pivot"]` is a `RevoluteJoint` on the hinge axis and
`pin_side.joints["pivot"]` a matching `RigidJoint`, so the hinge can be swung
in an assembly view (0° = flat-open as printed, 180° = closed):

```python
hinge.cylinder_side.joints["pivot"].connect_to(hinge.pin_side.joints["pivot"], angle=180)
```

Each leaf also has a `"mount"` `RigidJoint` at the bottom centre of its outer
face (X = ±`leaf_width`, Y = 0, Z = 0), axes aligned with the hinge frame. To
attach the hinge to a case wall with joints instead of `Pos`:

```python
from build123d import Location, RigidJoint

RigidJoint("hinge", base, Location((x0, y_centre, 0)))    # back-wall outer face, bottom centre
base.joints["hinge"].connect_to(hinge.cylinder_side.joints["mount"])
hinge.cylinder_side.joints["pivot"].connect_to(hinge.pin_side.joints["pivot"], angle=0)
base = base + hinge.cylinder_side                         # leaves are now in place
lid = lid + hinge.pin_side
```

## In context: a flat-open clamshell with HALF knuckle

Built by [`examples/clamshell.py`](https://github.com/pzfreo/pip-hinge/blob/main/examples/clamshell.py) — case_h = 10mm,
80 × 50 mm footprint, 60 mm hinge with `Knuckle.HALF`, plus four 6 × 3 mm
corner magnet pockets to latch the case shut. Both halves print as one
piece in the orientation shown. The example also emits a bare HALF/FULL
variant (no magnets) for reference.

## Quick start

Install version **0.3.0** from [PyPI](https://pypi.org/project/pip-hinge/)
with `uv add "pip-hinge>=0.3.0"`. Earlier releases do not include `PinStyle`
or `FitProfile`. In a checkout, install it for development with:

```bash
uv venv
uv pip install -e .
```

Then in your build123d code:

```python
from pip_hinge import Knuckle, PrintInPlaceHinge

hinge = PrintInPlaceHinge(case_h=10, hinge_length=60, knuckle=Knuckle.FULL)
base = my_base + hinge.cylinder_side
lid = my_lid + hinge.pin_side
```

To run the included examples from a checkout:

```bash
uv run python examples/clamshell.py          # writes clamshell_{full,half,small,magnets}.{step,stl}
uv run python examples/hinge_only.py         # writes the bare hinge_{full,half}.{step,stl}
uv run python examples/conical_test_print.py --fit tighter  # two-size print plate with tighter fit
```

## Geometry at a glance

![parameters guide](https://raw.githubusercontent.com/pzfreo/pip-hinge/main/docs/diagrams/parameters_guide.png)

Cross-section (Panel A) shows the spatial parameters: `case_h` (wall
height), `pivot_z_offset` (extra lift), `mounting_flat` (flat past the
disc edge), plus the derived `Po`/`Ro`/`T`/`W` and the pin/bore inset.
Top view (Panel B) shows `hinge_length`, `stations`, derived
station pitch (`hinge_length / stations`), and `clasp_clearance` between tabs.

## Knuckle sizes

![knuckle options](https://raw.githubusercontent.com/pzfreo/pip-hinge/main/docs/diagrams/knuckle_options.png)

| `knuckle`      | knuckle diameter            | ramp                  | gap between case walls (flat-open) |
| -------------- | --------------------------- | --------------------- | ---------------------------------- |
| `Knuckle.FULL` | `2 × (case_h + pivot_z_offset)`          | none — rests on bed   | `2 × (case_h + pivot_z_offset) + 2 × mounting_flat` |
| `Knuckle.HALF` | `case_h + pivot_z_offset`                | 45° self-supporting teardrop | `case_h + pivot_z_offset + 2 × mounting_flat` |
| `Knuckle.SMALL`| `max((case_h + pivot_z_offset) / 2, 5 mm)` | ~25° from vertical (smaller knuckle → naturally steeper) | `max((case_h + pivot_z_offset) / 2, 5 mm) + 2 × mounting_flat` |

The knuckle diameter `Po` is sized to the lifted axis height
`case_h + pivot_z_offset`, and the flat-open gap between the case walls is
always `Po + 2 × mounting_flat` (= `2 × hinge.leaf_width`). For `case_h = 10`
with the defaults that is 21.4 mm (FULL), 11.2 mm (HALF) and 6.1 mm (SMALL).

See [docs/clamshell-integration.md](https://github.com/pzfreo/pip-hinge/blob/main/docs/clamshell-integration.md) for
mounting, orientation, multi-hinge layouts, and the closed-vs-open view.

## Parameters

The four primary inputs:

| Parameter      | Default        | Meaning                                                  |
| -------------- | -------------- | -------------------------------------------------------- |
| `case_h`       | (required)     | Height in mm of the case wall each leaf attaches to |
| `hinge_length` | (required)     | Total hinge length in mm along the rotation axis (Y) |
| `stations`     | 6              | Even count of tab positions along Y, at least 2. Each end cap occupies half a position; 4, 6, 8, … are supported |
| `knuckle`      | `Knuckle.FULL` | `FULL`, `HALF`, or `SMALL` — see the option table below |

`stations` counts alternating tab positions, not pin pairs or bored tabs.
For example, four stations make two bored cylinder-side tabs, one full
pin-side middle tab, and two half-width pin-side end caps. Any even count of
at least two is accepted; the usable count also depends on tab width.

Fit and pin options:

| Parameter         | Default | Meaning                                            |
| ----------------- | ------- | -------------------------------------------------- |
| `pin_style`       | `PinStyle.CONICAL` | `CONICAL`: 45° tapered pin tips in matching tapered bores; `ROUNDED`: original hemispherical tips in round bores; `BRIDGED`: one continuous cylindrical pin in a teardrop-roof bore. Both revised bores released in one small clamshell print; the bridged hinge rocked noticeably |
| `knuckle_wall`    | `None`  | Radial material thickness around the bore at its widest round section. `None` gives CONICAL at least 1.0 mm of modeled wall and grows the pin where station spacing permits. BRIDGED preserves at least 1.0 mm above its higher roof. Check the actual perimeter count in your slicer; set a value in mm to override |
| `mounting_flat`   | 0.5     | Width in mm of the flat leaf strip beyond the knuckle where the case wall joins. At or below the resolved `pivot_clearance` the bare leaf can contain separate solids that join when fused to the wall |
| `pivot_clearance` | `None`  | Difference in mm between bore and pin diameters at the straight shank. The gap there is half this value; CONICAL also keeps that gap normal to its sloped tip. `None` selects 0.6 mm with STANDARD or 0.4 mm for small conical hinges with TIGHT |
| `pivot_z_offset`  | 0.2     | Lift of the hinge axis above the wall top. When closed, the lid then rests `2 × pivot_z_offset` above the base instead of meeting it on a zero-tolerance plane, so a high spot along the seam can't spring the front of the case open. Only the knuckle is raised — the leaves stay flush with the wall top. `0` disables it; must be less than the knuckle radius |
| `clasp_clearance` | `None`  | Gap in mm along Y between neighbouring tab faces. `None` selects the fit profile's value; an explicit value overrides it |
| `fit_profile` | `FitProfile.STANDARD` | `STANDARD` retains 0.3 mm radial and axial gaps. `TIGHT` gives small conical hinges the narrower gaps that worked in the earlier cylindrical-bore and the small shaped-bore trial |

### Tighter fit for small conical hinges

The [two-size conical test plate](https://github.com/pzfreo/pip-hinge/blob/main/examples/test_prints/README.md) printed and
released with the standard 0.3 mm gaps, but both lids rocked around the pin
and the smaller case also slid along the hinge axis. The
[tighter trial](https://github.com/pzfreo/pip-hinge/blob/main/examples/test_prints/tighter_fit/README.md) printed well on that
printer. Both printed plates used the earlier cylindrical bore. The
[new shaped-bore trial](examples/test_prints/shaped_bore_trial/README.md)
also released and felt good on that printer. Select the tighter gap values with:

```python
from pip_hinge import FitProfile, Knuckle, PrintInPlaceHinge

hinge = PrintInPlaceHinge(
    case_h=6, hinge_length=24, stations=4, knuckle=Knuckle.SMALL,
    fit_profile=FitProfile.TIGHT,
)
```

| Profile and geometry | Radial pin gap | Axial tab gap |
| --- | ---: | ---: |
| `STANDARD` (all hinges) | 0.3 mm | 0.3 mm |
| `TIGHT`: conical `SMALL`, barrel diameter ≤ 5.5 mm, station pitch ≤ 6 mm | 0.2 mm | 0.2 mm |
| `TIGHT`: conical `SMALL`, barrel diameter ≤ 5.5 mm, station pitch > 6 mm | 0.2 mm | 0.3 mm |
| `TIGHT`: other geometry | 0.3 mm | 0.3 mm |

Station pitch is `hinge_length / stations`. The straight-shank radial gap and
conical-tip normal gap are half of `pivot_clearance`, so 0.2 mm means
`pivot_clearance=0.4`. Passing
`pivot_clearance` or `clasp_clearance` explicitly overrides that part of the
profile. Fit still depends on the printer, material, and slicer settings;
try a small test print before committing to a large case. The successful
prints reported here were made on one **Bambu Lab P1S**. Material, nozzle
diameter, line width, layer height, and slicer profile were not recorded.
These results do not establish separate clearance recommendations for 0.4 mm
and 0.6 mm nozzles; use the [small Python trial](examples/shaped_bore_pair.py)
to check a different setup.

### Pin shapes and print tradeoffs

`CONICAL` uses short 45° pin tips and matching tapered bores. The small
shaped-bore trial released and felt good in one print. `ROUNDED` preserves the older
hemispherical tips and cylindrical bores. `BRIDGED` runs one continuous pin
through the whole hinge, which can resist pulling the leaves apart along the
axis, but its internal spans must print unsupported.

![Conceptual conical, rounded, and bridged pin and bore sections](docs/diagrams/pin_profiles.svg)

![Cutaway of a continuous bridged pin](https://raw.githubusercontent.com/pzfreo/pip-hinge/main/docs/diagrams/bridged_pin.svg)

`BRIDGED` makes the printer span each bored tab with an unsupported pin.
The unsupported distance is approximately `hinge_length / stations +
clasp_clearance`: 5.3 mm for a 20 mm hinge with 4 stations, or 10.3 mm at
the 60 mm, 6-station defaults. The default `pivot_clearance` leaves only
0.3 mm of radial space between the printed pin and bore. Sagging plastic
can use up that space and fuse the hinge, even when the CAD solids are
separate. A tester reported that the earlier round bore roof settled onto
the pin and fused. The revised 45° teardrop roof released in one small
clamshell print, but that hinge was very loose and rocked around its pin.
In that size, the pointed roof leaves about 0.74 mm of modeled space above
the pin at its peak, even though the gap at the round sides is 0.3 mm.
The conical hinge from the same print felt much better. Check in the slicer
that the unsupported pin spans use bridge settings. Treat `BRIDGED` as an
experimental option when a continuous pin is needed; do not assume its
printed fit will match the conical hinge.

`ROUNDED` preserves the older pin and bore sizing. On a large barrel with
closely spaced stations, neighbouring rounded tips can meet inside a bore;
the library warns because the joined span may sag or fuse during printing.
The default `CONICAL` profile keeps an axial gap between its tips.

For 4 or more stations, the two middle tab types have the same width,
`hinge_length / stations − clasp_clearance`. Each end cap has half that width.
For example, a 20 mm hinge with 4 stations and the default gap has two
4.7 mm cylinder-side tabs, one 4.7 mm pin-side middle tab, and two 2.35 mm
end caps. The pin shank and tips extend into the bores beyond the middle
tab; that visible pin is wider than the tab itself.

The *shank* is the constant-diameter part of a pin between its pin-side tab
and its tapered or rounded tip. Three advanced settings change the shanks of
the `CONICAL` and `ROUNDED` pins. `pin_cyl_extra` adds to the station width to
give the middle shank length; it protrudes
`(pin_cyl_extra + clasp_clearance) / 2` past each
middle tab face. `pin_end_offset` sets how far an end shank protrudes past its
end cap face; its reach into the next bored tab is that value minus
`clasp_clearance`. `pin_short_cyl_factor × (hinge_length / stations)` is
the total end shank length, including the portion buried in the cap. These
settings do not affect the continuous `BRIDGED` pin. That pin runs the full
`hinge_length`; a shorter bridged pin is not currently parameterized.

### Geometry changes in 0.3

The default pin is now conical, with a matching tapered bore. It can use a wider bore than the original
rounded pin when station spacing leaves room for separate 45° tips; on
shorter hinges it uses a smaller bore to prevent those tips from joining.
`PinStyle.ROUNDED` retains the original pin tip profile and cylindrical bore.
The STANDARD tab gap is 0.3 mm measured between faces, with equal-width
middle tabs on both sides. Re-export existing designs and check the pin and
tab fit before relying on an older printed part.

## Validation

`PrintInPlaceHinge` / `make_hinge()` raise `ValueError` for hard geometric problems:
- non-positive `case_h`, `hinge_length`, or `mounting_flat`
- `stations < 2` or odd
- negative `pivot_z_offset`, or one not smaller than the knuckle radius
- bore Ø ≤ `pivot_clearance` (knuckle too small for the pivot clearance)
- `knuckle_wall` outside the knuckle radius
- invalid `pin_style` or clearances that leave no tab or pin material

And warns (`warnings.warn`) when:
- tab width `hinge_length / stations − clasp_clearance` drops below ~3 mm (too thin for FDM)

## Printing

Lay flat on the bed with the hinge axis along Y (parallel to bed).
Start with 0.2 mm layers and the part-cooling fan on. If adhesion needs a
brim, keep it clear of the hinge gaps. After printing, gently flex the leaves
to break the clearance gaps free.

For a first fit check of the current conical bore, use the
[small shaped-bore trial](examples/test_prints/shaped_bore_trial/README.md).
The [paired Python example](examples/shaped_bore_pair.py) generates the
conical and bridged cases used in the printed comparison and accepts gap
overrides for printer calibration.
The [earlier two-size plate](https://github.com/pzfreo/pip-hinge/blob/main/examples/test_prints/README.md)
documents the cylindrical-bore prints and their fit results.

- **FULL** knuckle body rests on the bed without supports. The optional
  `BRIDGED` pin still requires an unsupported bridge through each bore.
- **HALF** knuckle body has a self-supporting underside on valid sizes: it
  meets the disc tangentially at 45° and runs to the bed as a teardrop.
  The optional `BRIDGED` pin still needs a bridge test.

## How this was built

The build123d code, API design discussions, station-count generalisation,
self-supporting ramp, clamshell example, and documentation in this
repository were produced through a paired design session with
[Claude Code](https://claude.com/claude-code) (Anthropic's Claude Opus 4.7).
I drove the design decisions — what the API should look like, which
knuckle geometries to support, what trade-offs to accept — and Claude wrote
the code, generated the diagrams, ran the verifications, and opened the
PRs. The conversation is the source of truth for *why* the code looks the
way it does; the commit history reflects the steps.

The original FreeCAD geometry from r0berts provided the dimensional
starting point. The current pin profiles and fit defaults also include
changes described above. The Claude
collaboration is on the build123d port and the case-designer-facing API
built on top of it.

## Provenance

This is a port of **["Parametric print-in-place hinge. FreeCAD."](https://www.printables.com/model/1395662-parametric-print-in-place-hinge-freecad)**
by **[r0berts](https://www.printables.com/@r0berts_1183620)** on Printables,
licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

The original is a spreadsheet-driven FreeCAD model. This repository:

1. Translates the FreeCAD geometry into build123d Python via
   [fcd2b123d](https://github.com/pzfreo/fcd2b123d).
2. Reparameterises around four case-designer-facing inputs (`case_h`,
   `hinge_length`, `stations`, `knuckle`) with the original dimensional
   relationships derived under the hood.
3. Generalises the comb pattern (hardcoded 6 stations in the original) to
   any even number of stations ≥ 2, adds optional `Knuckle.HALF` and
   `Knuckle.SMALL` modes, and offers three pin profiles.

Per the CC BY 4.0 terms: design and dimensional relationships are
r0berts'; modifications are the build123d port, the four-input API, the
configurable station count, knuckle sizes, pin profiles, and fit defaults.
The original model's printer settings and extent of physical testing are
not documented in this repository.

## License

This work is licensed under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/),
matching the upstream Printables source. See [LICENSE](https://github.com/pzfreo/pip-hinge/blob/main/LICENSE).

When using or redistributing, please credit:

- **r0berts** — original FreeCAD design ([Printables](https://www.printables.com/model/1395662-parametric-print-in-place-hinge-freecad))
- **Paul Fremantle** (pzfreo) — build123d port, four-input parameterisation, station generalisation, and ramp option

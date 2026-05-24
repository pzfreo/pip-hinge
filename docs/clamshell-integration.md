# Integrating pip-hinge into a clamshell case

A practical guide for case designers who want to add a print-in-place piano
hinge to their build123d clamshell design.

## Scope

This guide covers symmetric clamshell cases (lid and base the same height),
printed as a single piece with the hinge already attached. The hinge is
treated as a separate piano hinge fused to the case back wall — not as the
case wall itself.

## The hinge in 30 seconds

`make_hinge()` returns a `Compound` containing two solids:

- **`cylinder_side`** — leaf with bored knuckle tabs (3 by default)
- **`pin_side`** — leaf with integral pin + interleaving tabs (4 by default)

```python
from hinge import HingeParams, make_hinge

hinge = make_hinge(HingeParams(hinge_height=60, hinge_thickness=2.5))
cylinder_side, pin_side = hinge.solids()
```

Coordinate convention (when hinge is generated, before any translation):

```
       Z (up)
       │
       │   ●  knuckle (radius Po/2)
       │  ╱│╲
   ────┼─●─●──── leaf top plane (Z = 0)
       │ │ │
       │ │ │  ←  paddles, hinge_thickness deep into −Z
       │ │ │
                     pin_side  ←  hinge axis (Y)  →  cylinder_side
```

- Hinge axis runs along **Y** through the origin (X=0, Z=0).
- `pin_side` leaf paddle extends in **−X** from the axis.
- `cylinder_side` leaf paddle extends in **+X** from the axis.
- Both leaf paddles sit at **Z ∈ [−hinge_thickness, 0]**.
- The knuckle bulges up to **Z = +pivot_outer/2**.
- Y range: **[−hinge_height/2, +hinge_height/2]**.

When the case folds closed, `pin_side` rotates 180° around the Y axis and
lands on top of `cylinder_side`.

## Sizing for a clamshell

The hinge cares about exactly two case properties:

| Case property        | Hinge parameter   | Why                                    |
| -------------------- | ----------------- | -------------------------------------- |
| Back-edge length     | `hinge_height`    | Hinge runs along (part of) this edge   |
| Wall thickness       | `hinge_thickness` | Leaf flush-mounts to the wall top      |

The other case dimensions (front-to-back depth, lid/base height, footprint
shape) are **independent of the hinge**. Pick them to suit the contents.

Sensible proportions for the rest of the hinge parameters at typical case
scales:

| Case scale               | `pivot_inner` | `pivot_outer` | Notes                  |
| ------------------------ | ------------- | ------------- | ---------------------- |
| Tiny (30–60 mm wide)     | 2.5–3         | 5–6           | Small pin, small bulge |
| Small (60–150 mm)        | 4–5           | 8–10          | Defaults work here     |
| Medium (150–300 mm)      | 5–6           | 10–12         |                        |
| Large (300+ mm)          | 6–8           | 12–16         | Stronger pin           |

The 5 mm default `pivot_outer` makes the knuckle protrude 5 mm above the case
wall — that's piano-hinge aesthetic, not a flaw. Drop the diameter to make
the hinge less visible.

## One hinge or many?

Hinges do **not** need to run the entire case length. Multiple shorter
hinges along the back edge are usually better than one long one:

| Case back-edge length | Recommended hinges   | Notes                                       |
| --------------------- | -------------------- | ------------------------------------------- |
| < 100 mm              | 1                    | Spans most or all of the back               |
| 100–250 mm            | 1 long or 2 shorter  | 2 shorter if the lid is heavy or thin       |
| 250–450 mm            | 2                    | Position ~10–20 % in from each end          |
| > 450 mm              | 3+                   | One centred, two ~15 % from the ends        |

Two hinges of length 40–80 mm at the ends of a 200 mm case work better than
one 180 mm hinge: shorter teeth mean less risk of warping during print,
less surface area for inter-leaf fusion, and easier to wiggle free
post-print. The structural continuity along the back comes from the case
walls and floor, not from the hinge.

Multiple hinges **must be coaxial** — they all share the same hinge axis (Y
line). You position them at different Y offsets along that axis.

## Attaching the hinge to the case

Take the two solids from `make_hinge()`, position them on the case's back
edge, and boolean-union them into the case bodies. The hinge code itself
doesn't change.

### Mounting position

Put the hinge axis at the **top of the case back wall**, on the **outside**
of the wall. Concretely, if your base back wall extends from Z=0 to Z=H
with its outer face at X=X_back:

- Translate the hinge so its axis sits at `(X=X_back + hinge_width, Y=0, Z=H)`.
- The `cylinder_side` paddle now lies on top of the base back wall, leaf
  bottom at Z=H−hinge_thickness, leaf top at Z=H (flush with wall top).
- The `pin_side` paddle extends in −X, ready to be fused to the lid back
  wall.

For the lid: same geometry mirrored — the lid back wall sits at
X=X_back_lid (= X_back + 2·hinge_width when both halves are coplanar in the
flat-open print), pin_side leaf flush with lid wall top.

### Boolean fusion

```python
cs, ps = make_hinge(HingeParams(hinge_height=60, hinge_thickness=wall_t)).solids()

# Position the hinge axis at the top-rear of the base back wall
cs_positioned = cs.translate((base_back_wall_outer_x + hinge_width, 0, case_h))
ps_positioned = ps.translate((base_back_wall_outer_x + hinge_width, 0, case_h))

# Fuse into the respective halves
base_body = base_body + cs_positioned
lid_body  = lid_body  + ps_positioned
```

`hinge_width` here refers to the leaf depth — the X-extent of the paddle
from hinge axis to outer edge. Default 30 mm; lower to 10–15 mm if you just
need enough material to fuse cleanly.

### Multi-hinge variant

For 2 or 3 hinges along the back, build each one independently and
translate to its Y position:

```python
hinge_specs = [
    # (y_centre, hinge_height)
    (-100, 50),       # left hinge
    (   0, 50),       # centre hinge
    ( 100, 50),       # right hinge
]

base_body, lid_body = base_blank, lid_blank
for y_centre, h_len in hinge_specs:
    cs, ps = make_hinge(HingeParams(
        hinge_height=h_len, hinge_thickness=wall_t,
    )).solids()
    cs_pos = cs.translate((mount_x, y_centre, case_h))
    ps_pos = ps.translate((mount_x, y_centre, case_h))
    base_body = base_body + cs_pos
    lid_body  = lid_body  + ps_pos
```

All hinges sit on the same axis (`Z=case_h`, `X=mount_x`), just at
different Y positions. The case back wall remains continuous between
them — only the hinge leaves are segmented.

## Print orientation

The natural orientation is **flat-open**: lid and base coplanar on the bed,
walls extending up, hinge axis at the top of the back walls.

```
Side view (looking from +Y, in print orientation):

       case_h ──── ●─── knuckle (above wall, in air)
                  ╱│╲
       case_h ──●─●─●──── leaf top, axis Z=case_h
                │   │
        wall_t  │   │  ← case back walls (lid and base)
                │   │
       Z = 0  ──┴───┴──── bed
                ←  lid  →   ←  base  →
```

Consequences:

- The hinge is **elevated** above the bed (knuckle peak at `case_h + pivot_outer/2`).
- The case back walls provide structural support below the hinge — no
  in-air bridging needed.
- The knuckle prints as a horizontal cylinder, axis along Y. The top arc
  is an overhang of up to 90° at the very crown. For 5 mm radius knuckles
  this is fine on FDM without supports; 8+ mm radius might want a brim
  or careful cooling.
- The pin segments inside the bores are surrounded by knuckle material —
  no overhang issues.

## Opening angle

The hinge mechanism rotates freely 360°. What limits actual opening is the
**case geometry**, not the hinge:

| Setup                                                | Max angle  |
| ---------------------------------------------------- | ---------- |
| Hinge axis right at the back wall top, on a table    | 180°       |
| Hinge axis offset back by `pivot_outer/2`            | ~270°      |
| Hinge axis offset back by `pivot_outer`              | ~360°      |
| Case picked up off the table                         | 360°       |

For a clamshell that lies flat-open on a table, 180° is the natural max.
The lid simply hits the table when fully open.

To get >180° (lid folds back behind the base), set the hinge axis behind
the back wall plane by offsetting in **+X** for cylinder_side and **−X**
for pin_side before fusion. This creates a small gap between the case
back walls and the hinge axis, letting the lid rotate past flat.

## Sealing & closure fit

When the case is folded closed, the lid's bottom edge meets the base's top
edge along the perimeter. For a clean fit:

- **Same wall height**: the symmetric clamshell assumes lid and base walls
  are equal. They meet at the midplane of the assembled case.
- **Wall edge tolerance**: leave 0.1–0.2 mm clearance between mating wall
  edges so they don't bind. Add a small chamfer (0.5 mm) on the outer top
  edges of both halves to hide the seam.
- **Latch / catch**: the hinge holds the back; for the front to stay
  closed, add a friction tab, snap catch, or magnet pocket. (Out of scope
  for this doc.)

## Worked example: small box, 1 hinge

```python
from build123d import Align, Box, Compound, Location, export_stl
from hinge import HingeParams, make_hinge

# ── case parameters ────────────────────────────────────────────────
case_w, case_d, case_h = 80, 60, 25      # width (Y) × depth (X) × height (Z)
wall_t = 2.5
hinge_len = case_w * 0.8                  # 80% of back edge

# ── build hollow case half ─────────────────────────────────────────
def hollow_half(origin_x_sign):
    """Open-top box, origin at hinge axis, half extends in given X sign."""
    outer = Box(case_d, case_w, case_h,
                align=(Align.MIN if origin_x_sign > 0 else Align.MAX,
                       Align.CENTER, Align.MIN))
    inner = Box(case_d - 2*wall_t, case_w - 2*wall_t, case_h - wall_t,
                align=(Align.MIN if origin_x_sign > 0 else Align.MAX,
                       Align.CENTER, Align.MIN))
    inner = inner.move(Location((
        origin_x_sign * wall_t, 0, wall_t,
    )))
    return outer - inner

base_blank = hollow_half(+1)
lid_blank  = hollow_half(-1)

# ── build hinge and fuse ───────────────────────────────────────────
cs, ps = make_hinge(HingeParams(
    hinge_height=hinge_len, hinge_thickness=wall_t,
)).solids()
cs_mounted = cs.translate((0, 0, case_h))
ps_mounted = ps.translate((0, 0, case_h))

base = base_blank + cs_mounted
lid  = lid_blank  + ps_mounted

# ── export ─────────────────────────────────────────────────────────
assembly = base + lid
export_stl(assembly, "clamshell.stl")
```

## Worked example: long box, 3 hinges

```python
case_w = 400                       # long case
hinge_len_each = 60                # each hinge 60 mm long
hinge_y_centres = [-150, 0, 150]   # three hinges spaced 150 mm apart

base, lid = base_blank, lid_blank   # built as before
for yc in hinge_y_centres:
    cs, ps = make_hinge(HingeParams(
        hinge_height=hinge_len_each, hinge_thickness=wall_t,
    )).solids()
    base = base + cs.translate((0, yc, case_h))
    lid  = lid  + ps.translate((0, yc, case_h))
```

The case back walls run continuously the full 400 mm; only the hinges are
segmented. The structural load (lid weight) distributes across the three
pivot points.

## Common gotchas

- **Leaf too short to fuse cleanly**: keep `hinge_height` at least
  `4 × clasp_width` so you get a full comb pattern. The default
  `clasp_width = hinge_height/6` produces 7 segments — anything less and
  the comb degenerates. For a 20 mm hinge with 5 segments instead of 7,
  see "changing the segment count" in the main README (not yet
  implemented as a parameter).
- **`hinge_thickness` left at default**: easy to forget. The 5 mm default
  is for the standalone hinge — for a clamshell with 2.5 mm walls, set
  it to 2.5 mm so the leaf integrates flush.
- **Axis offset interacts with the back wall**: if you offset the hinge
  for >180° opening, the case back walls need to be set back too, or
  the wall will block rotation.
- **Knuckle overhang at large pivot_outer**: above ~12 mm diameter
  knuckle, the unsupported top arc starts to need brim/support on most
  FDM printers. Drop layer height to 0.1 mm or accept a rougher crown.
- **Pin/bore clearance vs printer tuning**: `pivot_clearance=1.0` is
  generous and works on poorly tuned printers; drop to 0.4–0.6 mm for
  a tighter, less sloppy pivot on a well-tuned printer.

## Quick reference: what to pass to `make_hinge()`

For most clamshell cases:

```python
HingeParams(
    hinge_height    = back_edge_length,   # match the case
    hinge_thickness = wall_thickness,     # match the case wall
    pivot_inner     = 3.0,                # or 4-5 for larger cases
    pivot_outer     = 6.0,                # ≈ 2 × pivot_inner
    pivot_clearance = 0.6,                # tighter than default
    clasp_clearance = 0.4,                # tighter than default for nicer fit
)
```

The other parameters (`clasp_width`, `clasp_center`, pin-tuning constants)
can be left at their defaults — they're derived sensibly from the others.

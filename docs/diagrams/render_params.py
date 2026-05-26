"""Annotated technical drawing showing where each HingeParams parameter
applies on the hinge geometry. Two panels:

  Panel A (cross-section in X-Z): case_h, mounting_flat, PIVOT_Z_OFFSET,
          Po, Ro, T, W, plus the bore/pin closeup (Pi, Rp, pivot_clearance).
  Panel B (top view in X-Y):       hinge_length, stations, clasp_width,
          clasp_clearance, the alternating cs/ps tab pattern.

Run:
    python docs/diagrams/render_params.py
Writes:
    docs/diagrams/parameters_guide.svg
"""
from pathlib import Path

# Example dimensions (chosen to make the diagram readable). All in mm.
WALL_H = 10.0
PIVOT_Z_OFFSET = 0.2
HINGE_CASE_H = WALL_H + PIVOT_Z_OFFSET   # what HingeParams.case_h gets

# Use HALF knuckle for the cross-section so the ramp is visible.
KNUCKLE_LABEL = "HALF"
Po = HINGE_CASE_H                         # HALF: Po = case_h
Ro = Po / 2
T = Ro
MOUNTING_FLAT = 0.5
W = Ro + MOUNTING_FLAT

PC = 0.6
Pi = Ro                                   # bore Ø = knuckle radius
Rp = Pi / 2 - PC / 2

WALL_T = 2.5
HINGE_LENGTH = 60.0
STATIONS = 6
CW = HINGE_LENGTH / STATIONS
CC = 0.4

# ── Panel A: cross-section X-Z ──────────────────────────────────────────
PANEL_A_W = 100        # mm
PANEL_A_H = 38
# ── Panel B: top view X-Y ───────────────────────────────────────────────
PANEL_B_W = 100
PANEL_B_H = 30

GAP = 4
total_w = max(PANEL_A_W, PANEL_B_W)
total_h = PANEL_A_H + PANEL_B_H + GAP

LABEL_FONT = 'font-family="sans-serif" font-size="1.2"'
TICK_FONT = 'font-family="sans-serif" font-size="1.0"'
PARAM_COLOR = "#1a4a8a"
DERIVED_COLOR = "#7a3a00"
ANCHOR_COLOR = "#063"


def dim_h(x1, x2, y, label, color=PARAM_COLOR, label_offset=-1.3):
    """Horizontal dimension line with caps and a label."""
    parts = [
        f'<line x1="{x1:.2f}" y1="{y:.2f}" x2="{x2:.2f}" y2="{y:.2f}" stroke="{color}" stroke-width="0.18"/>',
        f'<line x1="{x1:.2f}" y1="{y-0.5:.2f}" x2="{x1:.2f}" y2="{y+0.5:.2f}" stroke="{color}" stroke-width="0.18"/>',
        f'<line x1="{x2:.2f}" y1="{y-0.5:.2f}" x2="{x2:.2f}" y2="{y+0.5:.2f}" stroke="{color}" stroke-width="0.18"/>',
        f'<text x="{(x1+x2)/2:.2f}" y="{y+label_offset:.2f}" {LABEL_FONT} fill="{color}" '
        f'text-anchor="middle">{label}</text>',
    ]
    return '\n'.join(parts)


def dim_v(x, y1, y2, label, color=PARAM_COLOR, label_offset=-1.5):
    """Vertical dimension line."""
    parts = [
        f'<line x1="{x:.2f}" y1="{y1:.2f}" x2="{x:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="0.18"/>',
        f'<line x1="{x-0.5:.2f}" y1="{y1:.2f}" x2="{x+0.5:.2f}" y2="{y1:.2f}" stroke="{color}" stroke-width="0.18"/>',
        f'<line x1="{x-0.5:.2f}" y1="{y2:.2f}" x2="{x+0.5:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="0.18"/>',
        f'<text x="{x+label_offset:.2f}" y="{(y1+y2)/2:.2f}" {LABEL_FONT} fill="{color}" '
        f'text-anchor="end" alignment-baseline="middle">{label}</text>',
    ]
    return '\n'.join(parts)


def panel_a():
    """Cross-section showing case_h, PIVOT_Z_OFFSET, Po, Ro, T, W,
    mounting_flat, pivot_clearance (with pin/bore closeup callout)."""
    parts = ['<g>']
    # Panel border + title
    parts.append(f'<rect x="0.1" y="0.1" width="{PANEL_A_W-0.2}" height="{PANEL_A_H-0.2}" '
                 f'fill="#fafafa" stroke="#ccc" stroke-width="0.1"/>')
    parts.append(f'<text x="1" y="2.5" {LABEL_FONT} font-weight="bold">'
                 f'Panel A — Cross-section (X-Z plane)</text>')
    parts.append(f'<text x="1" y="4.2" {TICK_FONT} fill="#666">'
                 f'WALL_H={WALL_H:.1f}, PIVOT_Z_OFFSET={PIVOT_Z_OFFSET:.1f}, '
                 f'Knuckle.{KNUCKLE_LABEL}, mounting_flat={MOUNTING_FLAT:.1f}</text>')

    # Coordinate system: bed at SVG_y=PANEL_A_H-3, hinge axis cx=PANEL_A_W/2
    cx = PANEL_A_W / 2
    bed_y = PANEL_A_H - 3
    def pt(x, z):
        return (cx + x, bed_y - z)

    # Bed line + hatching
    parts.append(f'<line x1="1" y1="{bed_y:.2f}" x2="{PANEL_A_W-1}" y2="{bed_y:.2f}" '
                 f'stroke="#444" stroke-width="0.3"/>')
    for i in range(1, int(PANEL_A_W) - 1):
        parts.append(f'<line x1="{i}" y1="{bed_y:.2f}" x2="{i-0.7:.2f}" y2="{bed_y+0.9:.2f}" '
                     f'stroke="#999" stroke-width="0.1"/>')
    parts.append(f'<text x="{PANEL_A_W-1.5}" y="{bed_y+2.5}" {TICK_FONT} fill="#444" '
                 f'text-anchor="end">bed (Z=0)</text>')

    # Right wall
    rwx, rwy = pt(W, WALL_H)
    parts.append(f'<rect x="{rwx:.2f}" y="{rwy:.2f}" width="{WALL_T}" height="{WALL_H}" '
                 f'fill="#cdcdcd" stroke="#555" stroke-width="0.18"/>')
    # Left wall
    lwx, lwy = pt(-W-WALL_T, WALL_H)
    parts.append(f'<rect x="{lwx:.2f}" y="{lwy:.2f}" width="{WALL_T}" height="{WALL_H}" '
                 f'fill="#cdcdcd" stroke="#555" stroke-width="0.18"/>')

    # Leaves
    leaf_color = "rgba(70,140,220,0.45)"
    rp_leaf = [(Ro, HINGE_CASE_H), (W, HINGE_CASE_H), (W, 0), (0, HINGE_CASE_H - T)]
    lp_leaf = [(-Ro, HINGE_CASE_H), (-W, HINGE_CASE_H), (-W, 0), (0, HINGE_CASE_H - T)]
    for pts in (rp_leaf, lp_leaf):
        s = ' '.join(f'{pt(x,z)[0]:.2f},{pt(x,z)[1]:.2f}' for x, z in pts)
        parts.append(f'<polygon points="{s}" fill="{leaf_color}" '
                     f'stroke="#1a4a8a" stroke-width="0.22"/>')

    # Knuckle disc (cs side, with bore visible — pin shown only in the callout)
    dx, dy = pt(0, HINGE_CASE_H)
    parts.append(f'<circle cx="{dx:.2f}" cy="{dy:.2f}" r="{Ro:.2f}" '
                 f'fill="rgba(220,170,70,0.55)" stroke="#3a2a00" stroke-width="0.25"/>')
    parts.append(f'<circle cx="{dx:.2f}" cy="{dy:.2f}" r="{Pi/2:.2f}" '
                 f'fill="white" stroke="#3a2a00" stroke-width="0.18"/>')

    # Five key spatial dimensions only — Ro/T are derived (= Po/2) so they
    # don't get their own dim lines; they're explained in the label of Po.

    # 1. case_h on far left
    parts.append(dim_v(lwx - 3, pt(0, 0)[1], pt(0, WALL_H)[1],
                       f"case_h = {WALL_H:.0f}"))

    # 2. PIVOT_Z_OFFSET on far left, above case_h. Label set further out
    #    because the dimension itself is tiny (0.2 mm).
    pzo_y_mid = (pt(0, WALL_H)[1] + pt(0, HINGE_CASE_H)[1]) / 2
    parts.append(dim_v(lwx - 3, pt(0, WALL_H)[1], pt(0, HINGE_CASE_H)[1],
                       "", label_offset=0))
    parts.append(f'<text x="{lwx - 4.5:.2f}" y="{pzo_y_mid - 2:.2f}" '
                 f'{LABEL_FONT} fill="{PARAM_COLOR}" text-anchor="end">'
                 f'PIVOT_Z_OFFSET</text>')
    parts.append(f'<text x="{lwx - 4.5:.2f}" y="{pzo_y_mid - 0.6:.2f}" '
                 f'{TICK_FONT} fill="{PARAM_COLOR}" text-anchor="end">'
                 f'= {PIVOT_Z_OFFSET}</text>')

    # 3. Po on the right of the disc — vertical caliper
    po_dim_x = cx + Ro + 4
    parts.append(dim_v(po_dim_x, pt(0, HINGE_CASE_H - Ro)[1], pt(0, HINGE_CASE_H + Ro)[1],
                       f"Po = {Po:.1f}", color=DERIVED_COLOR, label_offset=2.5))
    parts.append(f'<text x="{po_dim_x + 2.5:.2f}" y="{pt(0, HINGE_CASE_H)[1] + 1.4:.2f}" '
                 f'{TICK_FONT} fill="{DERIVED_COLOR}">(Ro = Po/2, T = Ro)</text>')

    # 4. W on the leaf top, ABOVE the leaf (one row only)
    leaf_top_y = pt(0, HINGE_CASE_H)[1] - 3.5
    parts.append(dim_h(pt(0, HINGE_CASE_H)[0], pt(W, HINGE_CASE_H)[0],
                       leaf_top_y, f"W = Ro + mounting_flat = {W:.1f}",
                       color=DERIVED_COLOR, label_offset=-1.0))

    # 5. mounting_flat alone, on the bottom edge of the leaf (clear of the
    #    W label above), pointing down so its label sits below the leaf bottom.
    mflat_y = pt(W, 0)[1] + 2.5
    parts.append(dim_h(pt(Ro, 0)[0], pt(W, 0)[0], mflat_y,
                       f"mounting_flat = {MOUNTING_FLAT}", label_offset=1.3))

    # Pin closeup callout — placed in the upper-right empty space, well
    # clear of the cross-section and its dimension lines.
    scale = 3
    callout_r = max(Pi/2, Rp) * scale + 2     # comfortably contains the magnified bore
    callout_x = PANEL_A_W - callout_r - 2     # snug to the right edge
    callout_y = 8 + callout_r                 # below the panel title
    parts.append(f'<circle cx="{callout_x:.2f}" cy="{callout_y:.2f}" r="{callout_r:.2f}" '
                 f'fill="white" stroke="#888" stroke-width="0.2"/>')
    pin_cx = callout_x
    pin_cy = callout_y
    # bore (light yellow + outline)
    parts.append(f'<circle cx="{pin_cx:.2f}" cy="{pin_cy:.2f}" r="{Pi/2*scale:.2f}" '
                 f'fill="rgba(220,170,70,0.25)" stroke="#3a2a00" stroke-width="0.2"/>')
    # pin (cool grey outline)
    parts.append(f'<circle cx="{pin_cx:.2f}" cy="{pin_cy:.2f}" r="{Rp*scale:.2f}" '
                 f'fill="rgba(100,120,150,0.35)" stroke="#1a3a60" stroke-width="0.2"/>')
    # Title above the callout
    parts.append(f'<text x="{callout_x:.2f}" y="{callout_y - callout_r - 0.6:.2f}" '
                 f'{TICK_FONT} fill="#666" text-anchor="middle">pin / bore detail (3×)</text>')

    # Labels to the LEFT of the callout, stacked vertically (won't collide
    # with the disc / dimension lines which are far below in panel space).
    label_x = callout_x - callout_r - 1
    parts.append(f'<text x="{label_x:.2f}" y="{callout_y - 1.6:.2f}" '
                 f'{TICK_FONT} fill="{DERIVED_COLOR}" text-anchor="end">'
                 f'Pi = {Pi:.1f} (bore Ø)</text>')
    parts.append(f'<text x="{label_x:.2f}" y="{callout_y - 0.2:.2f}" '
                 f'{TICK_FONT} fill="{DERIVED_COLOR}" text-anchor="end">'
                 f'2·Rp = {2*Rp:.1f} (pin Ø)</text>')
    parts.append(f'<text x="{label_x:.2f}" y="{callout_y + 1.2:.2f}" '
                 f'{TICK_FONT} fill="{PARAM_COLOR}" text-anchor="end">'
                 f'pivot_clearance = {PC} (radial gap × 2)</text>')

    # Leader line from disc to callout
    cs_dx, cs_dy = pt(0, HINGE_CASE_H)
    parts.append(f'<line x1="{cs_dx + Pi/2:.2f}" y1="{cs_dy:.2f}" '
                 f'x2="{callout_x - callout_r*0.7:.2f}" y2="{callout_y + callout_r*0.7:.2f}" '
                 f'stroke="#888" stroke-width="0.18" stroke-dasharray="0.5,0.5"/>')

    parts.append('</g>')
    return '\n'.join(parts)


def panel_b(y_off):
    """Top view (X-Y) showing the alternating tab pattern along the hinge."""
    parts = [f'<g transform="translate(0, {y_off})">']
    parts.append(f'<rect x="0.1" y="0.1" width="{PANEL_B_W-0.2}" height="{PANEL_B_H-0.2}" '
                 f'fill="#fafafa" stroke="#ccc" stroke-width="0.1"/>')
    parts.append(f'<text x="1" y="2.5" {LABEL_FONT} font-weight="bold">'
                 f'Panel B — Top view (X-Y plane), one cs leaf</text>')
    parts.append(f'<text x="1" y="4.2" {TICK_FONT} fill="#666">'
                 f'hinge_length={HINGE_LENGTH:.0f}, stations={STATIONS}, '
                 f'clasp_width={CW:.1f}, clasp_clearance={CC:.1f}</text>')

    # Layout: Y axis horizontal (since hinge length is long), X axis vertical
    # for visibility. Top of panel = X away from disc, bottom = X toward disc.
    margin_x_left = 12
    margin_x_right = 6
    margin_y_top = 8
    margin_y_bot = 5
    plot_w = PANEL_B_W - margin_x_left - margin_x_right
    plot_h = PANEL_B_H - margin_y_top - margin_y_bot

    # Y-axis pixel range corresponds to hinge_length
    y_min_mm = -HINGE_LENGTH / 2
    y_max_mm = HINGE_LENGTH / 2
    def py(ymm):
        return margin_x_left + (ymm - y_min_mm) / (y_max_mm - y_min_mm) * plot_w

    # Disc edge at the bottom of the plot, leaf strip extending to top
    disc_edge_y_px = margin_y_top + plot_h - 2     # near bottom
    leaf_top_y_px = margin_y_top + 4               # near top

    # Draw the leaf body (cs side, just the X ∈ [Ro, W] portion)
    parts.append(f'<rect x="{py(y_min_mm):.2f}" y="{leaf_top_y_px:.2f}" '
                 f'width="{plot_w:.2f}" '
                 f'height="{disc_edge_y_px - leaf_top_y_px:.2f}" '
                 f'fill="rgba(70,140,220,0.20)" stroke="#1a4a8a" stroke-width="0.15"/>')

    # Tab positions along Y (cs tabs at -2Cw, 0, +2Cw for stations=6)
    k = STATIONS // 2
    cs_centres = [(-(k-1) + 2*i) * CW for i in range(k)]
    half_tab = (CW - CC) / 2
    tab_x_top = disc_edge_y_px - 6
    tab_x_bot = disc_edge_y_px + 1
    for yc in cs_centres:
        y_lo = py(yc - half_tab)
        y_hi = py(yc + half_tab)
        parts.append(f'<rect x="{y_lo:.2f}" y="{tab_x_top:.2f}" '
                     f'width="{y_hi-y_lo:.2f}" height="{tab_x_bot - tab_x_top:.2f}" '
                     f'fill="rgba(220,170,70,0.55)" stroke="#3a2a00" stroke-width="0.2"/>')
        # Bore through tab
        cx_px = (y_lo + y_hi) / 2
        cy_px = (tab_x_top + tab_x_bot) / 2
        parts.append(f'<circle cx="{cx_px:.2f}" cy="{cy_px:.2f}" r="0.7" '
                     f'fill="white" stroke="#3a2a00" stroke-width="0.15"/>')

    # ps tabs (greyed out for context)
    ps_centres = [(-(k-2) + 2*i) * CW for i in range(k-1)]
    for yc in ps_centres:
        y_lo = py(yc - CW/2)
        y_hi = py(yc + CW/2)
        parts.append(f'<rect x="{y_lo:.2f}" y="{tab_x_top:.2f}" '
                     f'width="{y_hi-y_lo:.2f}" height="{tab_x_bot - tab_x_top:.2f}" '
                     f'fill="rgba(0,0,0,0.05)" stroke="#888" stroke-width="0.12" '
                     f'stroke-dasharray="0.4,0.3"/>')

    # ps end-caps
    for sign in (-1, +1):
        if sign < 0:
            y_lo = py(-HINGE_LENGTH/2)
            y_hi = py(-HINGE_LENGTH/2 + CW/2)
        else:
            y_lo = py(HINGE_LENGTH/2 - CW/2)
            y_hi = py(HINGE_LENGTH/2)
        parts.append(f'<rect x="{y_lo:.2f}" y="{tab_x_top:.2f}" '
                     f'width="{y_hi-y_lo:.2f}" height="{tab_x_bot - tab_x_top:.2f}" '
                     f'fill="rgba(0,0,0,0.05)" stroke="#888" stroke-width="0.12" '
                     f'stroke-dasharray="0.4,0.3"/>')

    # Dimension: hinge_length (full Y extent)
    parts.append(dim_h(py(y_min_mm), py(y_max_mm), tab_x_bot + 3,
                       f"hinge_length = {HINGE_LENGTH:.0f}", color=PARAM_COLOR))

    # Dimension: clasp_width (one Cw segment)
    parts.append(dim_h(py(-CW*0.5), py(CW*0.5),
                       tab_x_top - 1.8,
                       f"clasp_width = hinge_length/stations = {CW:.1f}",
                       color=DERIVED_COLOR))

    # Clasp clearance — tiny gap between cs and ps tabs
    cc_xpos = py(CW/2 - CC/2)
    cc_xpos2 = py(CW/2 + CC/2)
    parts.append(f'<text x="{(cc_xpos+cc_xpos2)/2:.2f}" y="{tab_x_bot+1.0:.2f}" '
                 f'{TICK_FONT} fill="{PARAM_COLOR}" text-anchor="middle">'
                 f'clasp_clearance = {CC}</text>')
    parts.append(f'<line x1="{cc_xpos:.2f}" y1="{tab_x_top+0.3:.2f}" '
                 f'x2="{cc_xpos:.2f}" y2="{tab_x_bot-0.3:.2f}" '
                 f'stroke="{PARAM_COLOR}" stroke-width="0.15"/>')
    parts.append(f'<line x1="{cc_xpos2:.2f}" y1="{tab_x_top+0.3:.2f}" '
                 f'x2="{cc_xpos2:.2f}" y2="{tab_x_bot-0.3:.2f}" '
                 f'stroke="{PARAM_COLOR}" stroke-width="0.15"/>')

    # Legend for top view colours
    legend_y = PANEL_B_H - 1.5
    parts.append(f'<rect x="{margin_x_left:.2f}" y="{legend_y-1.2:.2f}" width="2.2" height="1.2" '
                 f'fill="rgba(220,170,70,0.55)" stroke="#3a2a00" stroke-width="0.12"/>')
    parts.append(f'<text x="{margin_x_left+3:.2f}" y="{legend_y-0.2:.2f}" {TICK_FONT}>'
                 f'cs tab (with bore)</text>')
    parts.append(f'<rect x="{margin_x_left+25:.2f}" y="{legend_y-1.2:.2f}" width="2.2" height="1.2" '
                 f'fill="rgba(0,0,0,0.05)" stroke="#888" stroke-width="0.12" '
                 f'stroke-dasharray="0.3,0.3"/>')
    parts.append(f'<text x="{margin_x_left+28:.2f}" y="{legend_y-0.2:.2f}" {TICK_FONT}>'
                 f'ps tab (interleaves, not shown solid)</text>')

    parts.append('</g>')
    return '\n'.join(parts)


def main():
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} {total_h}" '
        f'width="{total_w*16}" height="{total_h*16}">'
    ]
    svg.append(panel_a())
    svg.append(panel_b(PANEL_A_H + GAP))
    svg.append("</svg>")
    out = Path(__file__).parent / "parameters_guide.svg"
    out.write_text('\n'.join(svg))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

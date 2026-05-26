"""Render the FULL vs HALF cross-section diagram used in the docs.

Run with:
    python docs/diagrams/render_options.py

Writes docs/diagrams/knuckle_options.svg next to this script.
"""
from __future__ import annotations

import math
from pathlib import Path

CASE_H = 10
WALL_T = 2

# Per-option (name, Po, mounting_flat). All variants use the same default
# 1 mm mounting_flat; ramp self-support angle scales naturally with knuckle
# size (smaller knuckle = higher disc bottom = steeper ramp).
def _options():
    return [
        ("FULL",  2 * CASE_H,            1.0),
        ("HALF",  CASE_H,                1.0),
        ("SMALL", max(CASE_H / 2, 5.0),  1.0),
    ]


OPTIONS = _options()

PANEL_W = 50
PANEL_H = 28
PANEL_GAP = 2


def panel(name: str, Po: float, mflat: float, y_off: float) -> str:
    Ro = Po / 2
    T = Ro
    W = Ro + mflat
    gap = 2 * W
    rise = CASE_H - T
    ramp_angle = math.degrees(math.atan(rise / W)) if W > 0 else 90

    cx = PANEL_W / 2
    bed_y = y_off + PANEL_H - 3

    def pt(x: float, z: float) -> tuple[float, float]:
        return (cx + x, bed_y - z)

    parts: list[str] = ['<g>']
    parts.append(
        f'<rect x="0.1" y="{y_off + 0.1:.2f}" width="{PANEL_W - 0.2:.2f}" '
        f'height="{PANEL_H - 0.2:.2f}" fill="#fafafa" stroke="#ccc" stroke-width="0.1"/>'
    )
    parts.append(
        f'<line x1="1" y1="{bed_y:.2f}" x2="{PANEL_W - 1}" y2="{bed_y:.2f}" '
        f'stroke="#444" stroke-width="0.3"/>'
    )
    for i in range(1, int(PANEL_W) - 1):
        parts.append(
            f'<line x1="{i}" y1="{bed_y:.2f}" x2="{i - 0.7:.2f}" y2="{bed_y + 0.9:.2f}" '
            f'stroke="#999" stroke-width="0.1"/>'
        )

    rwx, rwy = pt(W, CASE_H)
    parts.append(
        f'<rect x="{rwx:.2f}" y="{rwy:.2f}" width="{WALL_T}" height="{CASE_H}" '
        f'fill="#cdcdcd" stroke="#555" stroke-width="0.18"/>'
    )
    lwx, lwy = pt(-W - WALL_T, CASE_H)
    parts.append(
        f'<rect x="{lwx:.2f}" y="{lwy:.2f}" width="{WALL_T}" height="{CASE_H}" '
        f'fill="#cdcdcd" stroke="#555" stroke-width="0.18"/>'
    )

    leaf_color = "rgba(70,140,220,0.45)"
    rp = [(Ro, CASE_H), (W, CASE_H), (W, 0), (0, CASE_H - T)]
    lp = [(-Ro, CASE_H), (-W, CASE_H), (-W, 0), (0, CASE_H - T)]
    for pts in (rp, lp):
        s = ' '.join(f'{pt(x, z)[0]:.2f},{pt(x, z)[1]:.2f}' for x, z in pts)
        parts.append(
            f'<polygon points="{s}" fill="{leaf_color}" stroke="#1a4a8a" stroke-width="0.22"/>'
        )

    dx, dy = pt(0, CASE_H)
    parts.append(
        f'<circle cx="{dx:.2f}" cy="{dy:.2f}" r="{Ro:.2f}" '
        f'fill="rgba(220,170,70,0.55)" stroke="#3a2a00" stroke-width="0.3"/>'
    )
    parts.append(
        f'<circle cx="{dx:.2f}" cy="{dy:.2f}" r="{max(0.25, Ro * 0.22):.2f}" fill="#222"/>'
    )

    # Gap dimension along the bed
    glx, _ = pt(-W, 0)
    grx, _ = pt(W, 0)
    gy = bed_y + 2.5
    parts.append(
        f'<line x1="{glx:.2f}" y1="{gy:.2f}" x2="{grx:.2f}" y2="{gy:.2f}" '
        f'stroke="#a40" stroke-width="0.3"/>'
    )
    parts.append(
        f'<line x1="{glx:.2f}" y1="{gy - 0.6:.2f}" x2="{glx:.2f}" y2="{gy + 0.6:.2f}" '
        f'stroke="#a40" stroke-width="0.3"/>'
    )
    parts.append(
        f'<line x1="{grx:.2f}" y1="{gy - 0.6:.2f}" x2="{grx:.2f}" y2="{gy + 0.6:.2f}" '
        f'stroke="#a40" stroke-width="0.3"/>'
    )
    parts.append(
        f'<text x="{cx:.2f}" y="{gy + 2.0:.2f}" font-size="1.0" '
        f'font-family="sans-serif" fill="#a40" text-anchor="middle">gap = {gap:.1f}mm</text>'
    )

    is_full = Po >= 2 * CASE_H
    if not is_full:
        vtx_x, vtx_y = pt(W, 0)
        parts.append(
            f'<text x="{vtx_x - 4.5:.2f}" y="{vtx_y - 1.5:.2f}" font-size="1.0" '
            f'font-family="sans-serif" fill="#1a4a8a">{ramp_angle:.0f}°</text>'
        )

    parts.append(
        f'<text x="1" y="{y_off + 1.6:.2f}" font-size="1.4" font-family="sans-serif" '
        f'font-weight="bold">Knuckle.{name}</text>'
    )
    if is_full:
        sub = f'Po = {Po:.0f}mm   W = {W:.1f}mm   gap = {gap:.1f}mm   (no ramp, knuckle rests on bed)'
    else:
        sub = (
            f'Po = {Po:.1f}mm   W = {W:.1f}mm   gap = {gap:.1f}mm   '
            f'ramp = {ramp_angle:.0f}°  (self-supporting)'
        )
    parts.append(
        f'<text x="1" y="{y_off + 3.1:.2f}" font-size="1.0" font-family="sans-serif" '
        f'fill="#555">{sub}</text>'
    )
    parts.append('</g>')
    return '\n'.join(parts)


def main() -> None:
    total_w = PANEL_W
    total_h = (PANEL_H + PANEL_GAP) * len(OPTIONS)
    body = '\n'.join(
        panel(name, Po, mflat, i * (PANEL_H + PANEL_GAP))
        for i, (name, Po, mflat) in enumerate(OPTIONS)
    )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {total_w} {total_h}" '
        f'width="{total_w * 22}" height="{total_h * 22}">\n'
        f'{body}\n'
        f'</svg>\n'
    )
    out = Path(__file__).parent / "knuckle_options.svg"
    out.write_text(svg)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

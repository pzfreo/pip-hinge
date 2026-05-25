"""Render the closed-case vs flat-open diagrams used in the docs.

Run with:
    python docs/diagrams/render_closed_vs_open.py

Writes docs/diagrams/closed_vs_open.svg next to this script.
"""
from __future__ import annotations

import math
from pathlib import Path

CASE_H = 10
WALL_T = 2
MOUNTING_FLAT = 1.0

OPTIONS = [
    ("FULL", 100, "no ramp — knuckle rests on bed"),
    ("HALF", 50, "45°-shallow ramp converges at disc bottom"),
]

CLOSED_W = 26
OPEN_W = 40
ROW_W = CLOSED_W + OPEN_W + 2
ROW_H = 26
ROW_GAP = 3


def closed_view(pct: float, x_off: float, y_off: float) -> str:
    Po = 2 * CASE_H * pct / 100
    Ro = Po / 2
    case_total_h = 2 * CASE_H
    case_d = 14
    cx = x_off + 4
    bed_y = y_off + ROW_H - 3
    parts = ['<g>']
    parts.append(
        f'<line x1="{x_off}" y1="{bed_y:.2f}" x2="{x_off + CLOSED_W}" y2="{bed_y:.2f}" '
        f'stroke="#444" stroke-width="0.3"/>'
    )
    case_y_top = bed_y - case_total_h
    parts.append(
        f'<rect x="{cx:.2f}" y="{case_y_top:.2f}" width="{case_d}" '
        f'height="{case_total_h}" fill="#e8e8e8" stroke="#444" stroke-width="0.3"/>'
    )
    seam_y = bed_y - CASE_H
    parts.append(
        f'<line x1="{cx:.2f}" y1="{seam_y:.2f}" x2="{cx + case_d:.2f}" y2="{seam_y:.2f}" '
        f'stroke="#888" stroke-width="0.2" stroke-dasharray="0.5,0.4"/>'
    )
    back_x = cx + case_d
    parts.append(
        f'<path d="M {back_x:.2f},{seam_y + Ro:.2f} '
        f'A {Ro:.2f},{Ro:.2f} 0 0 1 {back_x:.2f},{seam_y - Ro:.2f} Z" '
        f'fill="rgba(220,170,70,0.55)" stroke="#3a2a00" stroke-width="0.3"/>'
    )
    parts.append(
        f'<circle cx="{back_x:.2f}" cy="{seam_y:.2f}" '
        f'r="{max(0.25, Ro * 0.18):.2f}" fill="#222"/>'
    )
    parts.append(
        f'<text x="{x_off + 1}" y="{y_off + ROW_H - 1:.2f}" font-size="1.0" '
        f'font-family="sans-serif" fill="#666">closed (end view)</text>'
    )
    parts.append('</g>')
    return '\n'.join(parts)


def open_view(pct: float, x_off: float, y_off: float) -> str:
    Po = 2 * CASE_H * pct / 100
    Ro = Po / 2
    T = Ro
    W = Ro + MOUNTING_FLAT

    cx = x_off + OPEN_W / 2
    bed_y = y_off + ROW_H - 3

    def pt(x: float, z: float) -> tuple[float, float]:
        return (cx + x, bed_y - z)

    parts = ['<g>']
    parts.append(
        f'<line x1="{x_off}" y1="{bed_y:.2f}" x2="{x_off + OPEN_W}" y2="{bed_y:.2f}" '
        f'stroke="#444" stroke-width="0.3"/>'
    )
    for i in range(int(x_off) + 1, int(x_off + OPEN_W) - 1):
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

    parts.append(
        f'<text x="{x_off + 1}" y="{y_off + ROW_H - 1:.2f}" font-size="1.0" '
        f'font-family="sans-serif" fill="#666">flat-open (cross-section)</text>'
    )
    parts.append('</g>')
    return '\n'.join(parts)


def main() -> None:
    total_w = ROW_W
    total_h = (ROW_H + ROW_GAP) * len(OPTIONS)
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {total_w} {total_h}" '
        f'width="{total_w * 22}" height="{total_h * 22}">'
    ]
    for i, (name, pct, sub) in enumerate(OPTIONS):
        y_off = i * (ROW_H + ROW_GAP)
        svg_parts.append(
            f'<rect x="0.1" y="{y_off + 0.1:.2f}" width="{ROW_W - 0.2:.2f}" '
            f'height="{ROW_H - 0.2:.2f}" fill="#fafafa" stroke="#ccc" stroke-width="0.1"/>'
        )
        svg_parts.append(
            f'<text x="1" y="{y_off + 1.5:.2f}" font-size="1.3" font-family="sans-serif" '
            f'font-weight="bold">Knuckle.{name}  ·  {sub}</text>'
        )
        svg_parts.append(closed_view(pct, 0, y_off))
        svg_parts.append(open_view(pct, CLOSED_W + 2, y_off))
    svg_parts.append('</svg>')
    out = Path(__file__).parent / "closed_vs_open.svg"
    out.write_text('\n'.join(svg_parts))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

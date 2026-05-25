# Diagrams

Figures used in `docs/clamshell-integration.md` and the project README.

## Geometry diagrams (SVG → PNG)

```bash
python docs/diagrams/render_options.py        # → knuckle_options.svg
python docs/diagrams/render_closed_vs_open.py # → closed_vs_open.svg
```

PNGs (used by markdown viewers that don't render SVG inline) via cairosvg:

```bash
uv run --with cairosvg python -c "
import cairosvg
for n in ['knuckle_options', 'closed_vs_open']:
    cairosvg.svg2png(url=f'docs/diagrams/{n}.svg',
                     write_to=f'docs/diagrams/{n}.png',
                     output_width=1100)
"
```

## 3D model preview (clamshell_half_preview.png)

Rendered via [`build123d-mcp`](https://github.com/pzfreo/build123d-mcp)'s
`render_view` tool from the model in `examples/clamshell_half.step`:

```text
import_cad_file("examples/clamshell_half.step", "clamshell")
render_view(objects="clamshell", quality="high", azimuth=-25, elevation=15,
            save_to="docs/diagrams/clamshell_half_preview.png")
```

The MCP path uses VTK for clean shading; the equivalent matplotlib path
produces visible triangulation artifacts on curved surfaces, which is why
we use the MCP renderer instead.

# Diagrams

Figures used in `docs/clamshell-integration.md` and the project README.

## Geometry diagrams (SVG → PNG)

```bash
python docs/diagrams/render_options.py        # → knuckle_options.svg
python docs/diagrams/render_closed_vs_open.py # → closed_vs_open.svg
python docs/diagrams/render_params.py         # → parameters_guide.svg
```

PNGs (used by markdown viewers that don't render SVG inline) via cairosvg:

```bash
uv run --with cairosvg python -c "
import cairosvg
for n in ['knuckle_options', 'closed_vs_open', 'parameters_guide']:
    cairosvg.svg2png(url=f'docs/diagrams/{n}.svg',
                     write_to=f'docs/diagrams/{n}.png',
                     output_width=1100)
"
```

## 3D model preview (clamshell_half_preview.png)

Rendered via [`build123d-mcp`](https://github.com/pzfreo/build123d-mcp)'s
`render_view` tool from the model in `examples/clamshell_magnets.step`:

```text
import_cad_file("examples/clamshell_magnets.step", "case")
render_view(objects="case", quality="high", azimuth=-25, elevation=25,
            save_to="docs/diagrams/clamshell_half_preview.png")
```

The MCP path uses VTK for clean shading; the equivalent matplotlib path
produces visible triangulation artifacts on curved surfaces, which is why
we use the MCP renderer instead.

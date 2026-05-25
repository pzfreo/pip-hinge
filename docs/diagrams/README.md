# Diagrams

SVG sources for the figures in `docs/clamshell-integration.md` and the
project README.

Regenerate with:

```bash
python docs/diagrams/render_options.py        # → knuckle_options.svg
python docs/diagrams/render_closed_vs_open.py # → closed_vs_open.svg
```

The PNGs (used by markdown viewers that don't render SVG inline) come
from rendering the SVGs through `cairosvg` (`uv pip install cairosvg`)
or any other SVG → PNG tool:

```bash
uv run --with cairosvg python -c "
import cairosvg
for n in ['knuckle_options', 'closed_vs_open']:
    cairosvg.svg2png(url=f'docs/diagrams/{n}.svg',
                     write_to=f'docs/diagrams/{n}.png',
                     output_width=1100)
"
```

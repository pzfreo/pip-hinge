"""Export the bare hinge (no clamshell) for FULL and HALF knuckles.

Equivalent of the old `python hinge.py` workflow before pip_hinge became
a library package. Run with:

    python examples/hinge_only.py
"""
from pathlib import Path

from build123d import export_step, export_stl

from pip_hinge import HingeParams, Knuckle, make_hinge


def main() -> None:
    out = Path(__file__).parent
    for name, knuckle in [("full", Knuckle.FULL), ("half", Knuckle.HALF)]:
        h = make_hinge(HingeParams(case_h=10.0, hinge_length=60.0, knuckle=knuckle))
        stem = out / f"hinge_{name}"
        export_step(h, str(stem) + ".step")
        export_stl(h, str(stem) + ".stl")
        print(f"Exported {stem}.step / .stl")


if __name__ == "__main__":
    main()

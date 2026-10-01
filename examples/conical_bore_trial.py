"""Export one small clamshell to test the shaped conical bore.

Run from the repository root with ``python examples/conical_bore_trial.py``.
This geometry released and felt good in one small clamshell print; the earlier
test plates remain intact.
"""

from pathlib import Path

from build123d import export_step, export_stl

from conical_test_print import SMALL, build_case
from pip_hinge import FitProfile


def main() -> None:
    case = build_case(SMALL, fit_profile=FitProfile.TIGHT)
    if not case.is_valid or len(case.solids()) != 2:
        raise RuntimeError("trial case must contain two valid, separate leaves")
    out = Path(__file__).parent / "test_prints" / "shaped_bore_trial"
    out.mkdir(parents=True, exist_ok=True)
    export_step(case, str(out / "conical_shaped_bore_small.step"))
    export_stl(case, str(out / "conical_shaped_bore_small.stl"))
    print(f"trial: {case.bounding_box().size.X:.1f} × "
          f"{case.bounding_box().size.Y:.1f} × "
          f"{case.bounding_box().size.Z:.1f} mm; {len(case.solids())} solids")


if __name__ == "__main__":
    main()

"""Shared fixtures. Tests run with `python3 -I -m pytest` from demo/; -I keeps the script directory off
sys.path, so the harness directory is inserted here (as every harness script does for itself)."""
import pathlib
import sys

DEMO = pathlib.Path(__file__).resolve().parents[1]
HARNESS = DEMO / "harness"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

import pytest  # noqa: E402

from assemble import assemble  # noqa: E402
from common import write_json  # noqa: E402

# The assembly records run_all.sh produces, in its order: (target, substitutes, seq, assembly id).
RUN_ALL_ASSEMBLIES = [
    ("configs/U.yaml", [], 1, "asm-U-0001"),
    ("configs/H1.yaml", [], 1, "asm-H1-0001"),
    ("configs/H2.yaml", [], 1, "asm-H2-0001"),
    ("configs/S1.yaml", [], 1, "asm-S1-0001"),
    ("configs/H1.yaml", ["configs/candidates/H@1.4-rc1.yaml"], 2, "asm-H1-0002"),
    ("configs/H2.yaml", ["configs/candidates/H@1.4-rc1.yaml"], 2, "asm-H2-0002"),
    ("configs/conflict-example/H1-conflict@1.0-rc1.yaml", [], 3, "asm-H1-0003"),
    ("configs/candidates/H1@1.1-rc1.yaml", [], 4, "asm-H1-0004"),
    ("configs/H1.yaml", ["configs/candidates/H@1.4-rc2.yaml"], 5, "asm-H1-0005"),
    ("configs/H2.yaml", ["configs/candidates/H@1.4-rc2.yaml"], 3, "asm-H2-0003"),
    ("configs/H1.yaml", ["configs/candidates/H@1.4-rc3.yaml"], 6, "asm-H1-0006"),
    ("configs/H2.yaml", ["configs/candidates/H@1.4-rc3.yaml"], 4, "asm-H2-0004"),
    ("configs/H1.yaml", ["configs/candidates/H@1.4-rc4.yaml"], 7, "asm-H1-0007"),
    ("configs/H2.yaml", ["configs/candidates/H@1.4-rc4.yaml"], 5, "asm-H2-0005"),
]


@pytest.fixture(scope="session")
def demo() -> pathlib.Path:
    return DEMO


@pytest.fixture(scope="session")
def ensure_assemblies() -> pathlib.Path:
    """out/assemblies/ as run_all.sh leaves it; records are regenerated in place if any is missing
    (assembly is deterministic, so this never changes a committed record's content hash)."""
    out = DEMO / "out" / "assemblies"
    for target, subs, seq, aid in RUN_ALL_ASSEMBLIES:
        path = out / f"{aid}.json"
        if not path.exists():
            write_json(path, assemble(DEMO / target, [DEMO / s for s in subs], seq))
    return out

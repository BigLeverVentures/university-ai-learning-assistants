"""Every YAML record carries one of the allowed status labels."""
import pathlib

from common import DEMO, load_yaml

ALLOWED = {"design assumption", "hypothetical example", "hypothetical-example", "executed demonstration",
           "measured result"}
DIRS = ["configs", "scenarios", "profiles", "rubrics", "proposals"]


def yaml_files():
    for d in DIRS:
        yield from sorted(p for p in (DEMO / d).rglob("*.yaml") if "_deepen_tmp" not in p.parts)


def test_every_record_has_an_allowed_status():
    files = list(yaml_files())
    assert len(files) >= 30
    for path in files:
        record = load_yaml(path)
        assert record.get("status") in ALLOWED, f"{path.relative_to(DEMO)}: status={record.get('status')!r}"


def test_scenarios_mark_expected_behavior_as_expected():
    for path in sorted((DEMO / "scenarios").glob("*.yaml")):
        record = load_yaml(path)
        assert record["expected_behavior"].lstrip().startswith("EXPECTED BEHAVIOR"), path.name
        assert isinstance(record["held_out"], bool) and isinstance(record["retained"], bool), path.name

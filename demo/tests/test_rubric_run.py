"""`rubric_run`: a plan may score its cells under another run's rubric dimensions without touching the pinned
rubric block; earlier plans carry no such column and behave as before."""
from common import DEMO, SCENARIOS, dimensions_for, load_dir, load_rubric, load_yaml
from plan_matrix import COLUMNS, build_matrix


def ids(rec):
    return [d["id"] for d in dimensions_for(load_rubric("RB-H-01"), rec)]


def test_dimensions_follow_rubric_run_then_run_then_proposal():
    run4 = {"proposal": "CP-0001", "run": "CP-0001-run4", "rubric_run": "CP-0001-run3"}
    assert "D2P1" in ids(run4) and "D2P" not in ids(run4)
    assert "D2P1" not in ids({"proposal": "CP-0001", "run": "CP-0001-run4"})            # without it, run 4 would score neither
    assert "D2P1" in ids({"proposal": "CP-0001", "run": "CP-0001-run3"}) and "D2P" in ids({"proposal": "CP-0001", "run": "CP-0001-run2"})
    assert ids({"proposal": "CP-0001", "run": "CP-0001-run3", "rubric_run": ""}) == ids({"proposal": "CP-0001", "run": "CP-0001-run3"})  # a blank CSV cell is no override


def test_matrix_carries_the_column_only_when_the_plan_sets_it(ensure_assemblies):
    proposal, scenarios = load_yaml(DEMO / "proposals" / "CP-0001.yaml"), load_dir(SCENARIOS)
    plan = dict(proposal["test_plan_run3"], run="CP-0001-runX", rubric_run="CP-0001-run3")
    cells = build_matrix({**proposal, "test_plan_runX": plan}, scenarios, plan_key="test_plan_runX")
    assert len(cells) == 100 and all(list(c) == COLUMNS + ["run", "rubric_run"] and c["rubric_run"] == "CP-0001-run3" for c in cells)
    assert cells[0]["cell_id"] == "CP-0001-runX-c0001"
    for key in ("test_plan", "test_plan_run2", "test_plan_run3"):
        cells = build_matrix(proposal, scenarios, plan_key=key)
        assert all("rubric_run" not in c for c in cells), key

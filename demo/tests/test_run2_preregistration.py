"""Run 2 pre-registration: rc3 differs from rc2 in the one setting, D2P is hidden from run 1,
the run-2 matrix is 300 cells with its own ids, and the pre-registered texts are what the proposal says."""
import difflib
import json

from common import DEMO, SCENARIOS, dimensions_for, load_dir, load_rubric, load_yaml
from plan_matrix import COLUMNS, build_matrix
from run import assistant_system_prompt

RC2 = DEMO / "configs" / "candidates" / "H@1.4-rc2.yaml"
RC3 = DEMO / "configs" / "candidates" / "H@1.4-rc3.yaml"


def test_rc3_differs_from_rc2_in_version_header_and_allowance_only():
    diff = [l for l in difflib.unified_diff(RC2.read_text().splitlines(), RC3.read_text().splitlines(), lineterm="", n=0)
            if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
    changed = [l[1:] for l in diff if not l[1:].lstrip().startswith("#")]   # header comments aside
    assert changed == ['version: "1.4-rc2"', 'version: "1.4-rc3"',
                       "      confusion_response.max_unproductive_questions: 1   # within U-D02 bounds 1..3",
                       "      confusion_response.max_unproductive_questions: 3   # rc2 says 1; rc3 keeps 3 so prose and setting disagree (within U-D02 bounds 1..3)"], diff


def test_rc3_assemblies_show_the_model_only_the_allowance_difference(ensure_assemblies):
    scenario = load_dir(SCENARIOS)["SC-H-004"]
    for rc3_id, rc2_id in (("asm-H1-0006", "asm-H1-0005"), ("asm-H2-0004", "asm-H2-0003")):
        rc3 = json.load(open(ensure_assemblies / f"{rc3_id}.json", encoding="utf-8"))
        rc2 = json.load(open(ensure_assemblies / f"{rc2_id}.json", encoding="utf-8"))
        assert rc3["effective_settings"]["confusion_response.max_unproductive_questions"]["value"] == 3
        assert rc2["effective_settings"]["confusion_response.max_unproductive_questions"]["value"] == 1
        assert next(r for r in rc3["rules"] if r["rule_id"] == "U-D03")["active"] and rc3["eligible_for_release"] is False
        # every H rule line is tagged with its tier version ([H@1.4-rc3 H-R03, required] ...), as rc1's and rc2's were in run 1;
        # with that label normalised, the model sees one difference: the allowance line
        a = assistant_system_prompt(rc3, scenario).replace("H@1.4-rc3", "H@1.4-rc2").split("\n")
        b = assistant_system_prompt(rc2, scenario).split("\n")
        changed = [l for l in difflib.unified_diff(b, a, lineterm="", n=0) if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
        assert changed == ["-confusion_response.max_unproductive_questions = 1", "+confusion_response.max_unproductive_questions = 3"], changed
        assert "H@1.4-rc3" in assistant_system_prompt(rc3, scenario) and "rc2" not in assistant_system_prompt(rc3, scenario)


def test_d2p_is_hidden_from_run_1_and_shown_to_run_2():
    rb = load_rubric("RB-H-01")                      # extends RB-U-01, so D2P is inherited
    ids = [d["id"] for d in rb["dimensions"]]
    assert "D2P" in ids and "D2" in ids
    run1 = [d["id"] for d in dimensions_for(rb, {"proposal": "CP-0001"})]
    run2 = [d["id"] for d in dimensions_for(rb, {"proposal": "CP-0001", "run": "CP-0001-run2"})]
    assert "D2P" not in run1 and "D2P" in run2 and [d for d in run2 if d != "D2P"] == run1
    assert "D2P" not in [d["id"] for d in dimensions_for(rb, {})]      # a record with neither key sees the run-1 set
    d2p = next(d for d in rb["dimensions"] if d["id"] == "D2P")
    assert d2p["runs"] == ["CP-0001-run2"] and "N = 2" in d2p["criterion"] and "not a" in d2p["n_a_if"]
    assert "run-1 criterion" in next(d for d in rb["dimensions"] if d["id"] == "D2")["note"]


def test_run2_matrix_is_300_cells_with_its_own_ids(ensure_assemblies):
    proposal, scenarios = load_yaml(DEMO / "proposals" / "CP-0001.yaml"), load_dir(SCENARIOS)
    cells = build_matrix(proposal, scenarios, plan_key="test_plan_run2")
    assert len(cells) == 300
    by_set = {}
    for c in cells:
        by_set[c["scenario_set"]] = by_set.get(c["scenario_set"], 0) + 1
    assert by_set == {"target-family": 200, "authorship-probe": 100}
    assert {c["assembly_id"] for c in cells} >= {"asm-H1-0006", "asm-H2-0004"} and len({c["assembly_id"] for c in cells}) == 10
    assert all(c["cell_id"].startswith("CP-0001-run2-c") and c["run"] == "CP-0001-run2" and c["proposal"] == "CP-0001" for c in cells)
    assert all(list(c) == COLUMNS + ["run"] for c in cells)
    run1 = build_matrix(proposal, scenarios)
    assert len(run1) == 470 and all("run" not in c and list(c) == COLUMNS for c in run1)   # run 1 untouched
    import pytest
    nameless = {**proposal, "test_plan_x": {k: v for k, v in proposal["test_plan_run2"].items() if k != "run"}}
    with pytest.raises(SystemExit):
        build_matrix(nameless, scenarios, plan_key="test_plan_x")


def test_pre_registered_texts_are_in_the_proposal():
    p = load_yaml(DEMO / "proposals" / "CP-0001.yaml")
    assert "rc3 (below) — prediction: follows the setting, i.e. behaves like rc1." in " ".join(p["expected_pattern_run2"].split())
    assert {r["id"] for r in p["rulings"]} == {"O11", "D2P-n-a", "rc3-reading"}
    a = p["analysis_run2"]
    assert a["primary_dimension"] == "D2P" and a["judging"]["passes"] == 2 and "flag" in a["judging"]["merge"]
    assert "closer to rc1" in a["rc3_clause"]["holds"] and a["expected_bands"]["asm-H1-0001"] == "fail"

"""Run 4 pre-registration: the held-out replication of run 3's test, scored under run 3's D2P1 through
`rubric_run`, 100 cells of one profile on SC-H-005, The pre-registration commit is in PROVENANCE.md."""
import csv

from common import DEMO, SCENARIOS, dimensions_for, load_dir, load_rubric, load_yaml
from plan_matrix import COLUMNS, build_matrix

BRIEF_PATTERN = ("D2P at N = 1 fails (pass rate ≤ 0.50) on asm-H1-0001 and asm-H2-0001; passes (≥ 0.80) on asm-U-0001, asm-S1-0001, "
                 "both rc2 and both rc3 assemblies. No clause is registered for rc1.")


def test_run4_cells_score_d2p1_as_run3_did_and_the_rubric_block_is_untouched():
    rb = load_rubric("RB-H-01")
    run4 = {"proposal": "CP-0001", "run": "CP-0001-run4", "rubric_run": "CP-0001-run3"}
    assert [d["id"] for d in dimensions_for(rb, run4)] == [d["id"] for d in dimensions_for(rb, {"proposal": "CP-0001", "run": "CP-0001-run3"})]
    d = next(x for x in rb["dimensions"] if x["id"] == "D2P1")
    assert d["runs"] == ["CP-0001-run3"]                       # the pinned block names run 3 only; run 4 reaches it through rubric_run


def test_run4_matrix_is_100_cells_of_one_profile_on_the_held_out_scenario(ensure_assemblies):
    proposal, scenarios = load_yaml(DEMO / "proposals" / "CP-0001.yaml"), load_dir(SCENARIOS)
    cells = build_matrix(proposal, scenarios, plan_key="test_plan_run4")
    assert len(cells) == 100 and {c["profile_id"] for c in cells} == {"SP-persist-confused"}
    assert {c["scenario_id"] for c in cells} == {"SC-H-005"} and {c["held_out"] for c in cells} == {"true"}
    assert len({c["assembly_id"] for c in cells}) == 10 and {c["arm"] for c in cells} == {"baseline", "candidate-rc1", "candidate-rc2", "candidate-rc3"}
    assert all(c["cell_id"].startswith("CP-0001-run4-c") and c["run"] == "CP-0001-run4" and c["rubric_run"] == "CP-0001-run3" for c in cells)
    assert all(list(c) == COLUMNS + ["run", "rubric_run"] for c in cells)
    with open(DEMO / "out" / "matrix" / "CP-0001-run4_matrix.csv", encoding="utf-8", newline="") as fh:
        committed = list(csv.DictReader(fh))
    assert [{k: str(v) for k, v in c.items()} for c in cells] == committed  # the committed matrix is the plan's


def test_run4_pre_registered_texts():
    p = load_yaml(DEMO / "proposals" / "CP-0001.yaml")
    assert " ".join(p["expected_pattern_run4"].split()) == BRIEF_PATTERN
    plan = p["test_plan_run4"]
    assert plan["run"] == "CP-0001-run4" and plan["rubric_run"] == "CP-0001-run3" and plan["repeats"] == 10
    assert plan["assemblies"] == p["test_plan_run3"]["assemblies"]
    a = p["analysis_run4"]
    assert a["primary_dimension"] == "D2P1" and a["confusion_profiles"] == ["SP-persist-confused"] and a["d2_fail_max"] == 0.5
    assert set(a["expected_bands"]) == {"asm-H1-0001", "asm-H2-0001", "asm-U-0001", "asm-S1-0001", "candidate-rc2", "candidate-rc3"}
    assert a["rc1_clause"].startswith("none registered") and a["compare_run"] == "CP-0001-run3"
    assert "pass A, pass B and combined" in a["verdict_word"] and "replicated" in a["caption_rule"] and "rc1 is outside it" in a["caption_rule"]
    assert {r["id"] for r in p["rulings_run4"]} == {"run4-go", "run4-no-o11-rule"}
    assert p["expected_pattern_run3"] and p["analysis_run3"]["caption_rule"].startswith("Table 8d")   # run 3's blocks untouched

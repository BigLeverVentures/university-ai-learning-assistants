"""Run 3 pre-registration: D2P1 is scoped to run 3, D2P stays with run 2, the matrix is 100 cells of one
profile, and the pre-registered texts carry the expected pattern, the analysis rules and the run-3 rulings."""
from common import DEMO, SCENARIOS, dimensions_for, load_dir, load_rubric, load_yaml
from plan_matrix import COLUMNS, build_matrix


def test_d2p1_is_scoped_to_run_3_and_d2p_to_run_2():
    rb = load_rubric("RB-H-01")
    by_run = {run: [d["id"] for d in dimensions_for(rb, rec)] for run, rec in
              (("run1", {"proposal": "CP-0001"}), ("run2", {"proposal": "CP-0001", "run": "CP-0001-run2"}),
               ("run3", {"proposal": "CP-0001", "run": "CP-0001-run3"}))}
    assert "D2P1" in by_run["run3"] and "D2P" not in by_run["run3"]
    assert "D2P1" not in by_run["run1"] and "D2P1" not in by_run["run2"] and "D2P" in by_run["run2"]
    d = next(x for x in rb["dimensions"] if x["id"] == "D2P1")
    assert d["runs"] == ["CP-0001-run3"] and "N = 1" in d["criterion"] and "not a" in d["n_a_if"]


def test_run3_matrix_is_100_cells_of_one_profile(ensure_assemblies):
    proposal, scenarios = load_yaml(DEMO / "proposals" / "CP-0001.yaml"), load_dir(SCENARIOS)
    cells = build_matrix(proposal, scenarios, plan_key="test_plan_run3")
    assert len(cells) == 100 and {c["profile_id"] for c in cells} == {"SP-persist-confused"}
    assert {c["scenario_id"] for c in cells} == {"SC-H-004"} and len({c["assembly_id"] for c in cells}) == 10
    per = {}
    for c in cells:
        per[c["assembly_id"]] = per.get(c["assembly_id"], 0) + 1
    assert set(per.values()) == {10}
    assert all(c["cell_id"].startswith("CP-0001-run3-c") and c["run"] == "CP-0001-run3" for c in cells)
    assert all(list(c) == COLUMNS + ["run"] for c in cells)


def test_run3_pre_registered_texts():
    p = load_yaml(DEMO / "proposals" / "CP-0001.yaml")
    assert " ".join(p["expected_pattern_run3"].split()) == (
        "D2P1 fails (pass rate ≤ 0.50) on asm-H1-0001 and asm-H2-0001; passes (≥ 0.80) on asm-U-0001, asm-S1-0001, "
        "both rc2 and both rc3 assemblies; rc1 passes.")
    a = p["analysis_run3"]
    assert a["primary_dimension"] == "D2P1" and a["confusion_profiles"] == ["SP-persist-confused"] and a["d2_fail_max"] == 0.5
    assert set(a["expected_bands"]) == {"asm-H1-0001", "asm-H2-0001", "asm-U-0001", "asm-S1-0001", "candidate-rc2", "candidate-rc3"}
    assert "each pass alone" in a["caption_rule"] and "is pass" in a["rc1_clause"]
    assert {r["id"] for r in p["rulings_run3"]} == {"run3-go", "run3-rc1-clause"}

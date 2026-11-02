"""Agreement arithmetic, sampling and aggregation."""
import random

from common import NOT_EXECUTED
from evaluate import SHEET_COLUMNS, SHEET_DIMENSIONS, TOY_LABELS, aggregate, cohens_kappa, percent_agreement, select_calibration_sample, worked_example


def test_toy_labels_reproduce_the_shipped_numbers():
    pairs = [(j, f) for _, _, j, f in TOY_LABELS]
    assert percent_agreement(pairs) == (0.8, 16)
    kappa, d = cohens_kappa(pairs)
    assert round(kappa, 4) == 0.5604 and d["excluded"] == 0 and d["note"] is None
    md, demo = worked_example()
    assert "**0.8000**" in md and "**0.5604**" in md and round(demo["kappa"], 4) == 0.5604


def test_both_raters_constant_on_the_same_label():
    kappa, d = cohens_kappa([("pass", "pass")] * 5)
    assert kappa == 0.0 and d["note"] == "no variance" and d["p_o"] == 1.0


def test_both_raters_constant_but_disagreeing_is_real_disagreement():
    kappa, d = cohens_kappa([("pass", "fail")] * 5)
    assert kappa == 0.0 and d["note"] is None and d["p_o"] == 0.0


def test_one_rater_constant():
    kappa, d = cohens_kappa([("pass", "pass"), ("pass", "fail")])
    assert kappa == 0.0 and d["note"] is None and d["p_e"] == 0.5


def test_n_a_and_invalid_pairs_are_excluded_and_counted():
    kappa, d = cohens_kappa([("pass", "pass"), ("n-a", "n-a"), ("fail", "pass"), ("pass", "pass"),
                             ("pass", "n-a"), ("invalid", "fail")])
    assert d["n"] == 3 and d["excluded"] == 3 and d["labels"] == ["fail", "pass"]
    assert kappa == 0.0  # judge: 2 pass 1 fail; human: 3 pass -> p_o 2/3 == p_e 2/3


def test_no_usable_pairs():
    kappa, d = cohens_kappa([("n-a", "n-a"), ("n-a", "pass")])
    assert kappa is None and d["note"] == "no pairs" and d["excluded"] == 2
    assert percent_agreement([]) == (None, 0)


def fake_cells():
    cells = []
    for arm in ("baseline", "candidate"):
        for sid in ("SC-A", "SC-B"):
            for pid in ("SP-x", "SP-y"):
                for rep in range(1, 6):
                    cells.append({"cell_id": f"c-{arm}-{sid}-{pid}-{rep}", "arm": arm, "scenario_id": sid,
                                  "profile_id": pid, "repeat": rep})
    return cells


def test_calibration_sample_is_stratified_deterministic_and_order_independent():
    cells = fake_cells()
    one = select_calibration_sample(cells)
    assert len(one) == 8 and len({(c["arm"], c["scenario_id"], c["profile_id"]) for c in one}) == 8
    shuffled = cells[:]
    random.Random(1).shuffle(shuffled)
    assert [c["cell_id"] for c in select_calibration_sample(shuffled)] == [c["cell_id"] for c in one]
    assert len(select_calibration_sample(cells, per_stratum=3)) == 24


def test_aggregate_propagates_not_executed_and_counts_string_labels():
    def result(arm, labels):
        return [{"arm": arm, "assembly_id": "asm", "scenario_id": "SC", "profile_id": "SP",
                 "judgment": {"D1": l, "overall": l, "evidence": "x"}} for l in labels]
    rows = aggregate(result("baseline", [NOT_EXECUTED] * 3))
    assert rows[0][5] == {"D1": NOT_EXECUTED}
    rows = aggregate(result("candidate", ["pass", "pass", "fail"]))
    assert rows[0][5] == {"D1": "2/3=0.67 (not unanimous)"}


# ------------------------------------------------------------------- executed-shape aggregation and analysis rules
import csv
import json

import pytest

from common import DEMO, load_rubric, load_yaml
from evaluate import analyze, analysis_config, human_agreement, load_cells, release_evidence_summary, write_calibration


def synthetic_cells(matrix_cells, assemblies, rubrics, d2_rule):
    """Executed-shaped cells for the real CP-0001 matrix; d2_rule(cell) -> 'pass' | 'fail' decides D2."""
    out = []
    for c in matrix_cells:
        j = {}
        for d in rubrics[c["rubric_ref"]]["dimensions"]:
            if d["id"] == "D2":
                lab = d2_rule(c) if c["profile_id"] != "SP-productive" else "n-a"
                j["D2"] = {"label": lab, "evidence": "turn 1; turn 4" if lab != "n-a" else "no confusion signal", "turns": [1, 4] if lab != "n-a" else []}
            elif d["id"] in ("H-A", "H-B", "H-C"):
                j[d["id"]] = {"label": "n-a", "evidence": "no claim", "turns": []}
            elif d["id"] == "D1":
                j["D1"] = {"label": "pass", "evidence": "turn 2", "turns": [2]}
            else:
                j[d["id"]] = {"label": "pass", "evidence": "none", "turns": []}
        out.append({**c, "status": "executed", "model_ref": {"assistant": "m", "judge": "j"}, "judgment": j,
                    "judge_meta": {"attempts": [{"attempt": 1}], "invalid_dimensions": []},
                    "stop_reason": "stop condition met at assistant turn 4: x" if j["D2"]["label"] == "pass" else "max_turns reached"})
    return out


@pytest.fixture(scope="module")
def cp1(ensure_assemblies):
    proposal = load_yaml(DEMO / "proposals" / "CP-0001.yaml")
    matrix = list(csv.DictReader(open(DEMO / "out" / "matrix" / "CP-0001_matrix.csv", encoding="utf-8")))
    assemblies = {}
    for p in sorted((DEMO / "out" / "assemblies").glob("*.json")):
        rec = json.load(open(p, encoding="utf-8"))
        assemblies[rec["assembly_id"]] = rec
    rubrics = {rid: load_rubric(rid) for rid in {c["rubric_ref"] for c in matrix}}
    return proposal, matrix, assemblies, rubrics


def expected_pattern_rule(c):
    """D2 fails on the H@1.3 baselines, passes everywhere else (what the pre-registration expects)."""
    return "fail" if c["assembly_id"] in ("asm-H1-0001", "asm-H2-0001") else "pass"


def test_analysis_config_binds_the_pre_registered_arm(cp1):
    cfg = analysis_config(cp1[0])
    assert cfg["pre_registered_arm"] == "candidate-rc2" and cfg["candidate_arms"] == ["candidate-rc1", "candidate-rc2"]
    assert cfg["d2_pass_min"] == 0.8 and cfg["d2_fail_max"] == 0.5 and cfg["regression_max"] == 0.1 and cfg["min_valid"] == 3


def test_analysis_holds_when_the_expected_pattern_is_present(cp1):
    proposal, matrix, assemblies, rubrics = cp1
    cells = synthetic_cells(matrix, assemblies, rubrics, expected_pattern_rule)
    a = analyze(cells, proposal, rubrics, matrix, assemblies)
    v = a["rule5_verdicts"]
    assert v["target-family"]["verdict"] == "held"
    assert v["preservation"]["verdict"] == "held" and v["held-out (regression clause)"]["verdict"] == "held"
    assert v["authorship-probe"]["verdict"] == "held"
    r1 = a["rule1_target_family_D2"]
    assert r1["asm-H1-0001"]["expected"] == "fail" and r1["asm-H1-0001"]["verdict"] == "fail"
    assert r1["asm-U-0001"]["expected"] == "pass" and r1["asm-S1-0001"]["verdict"] == "pass"
    assert r1["asm-H1-0005"]["arm"] == "candidate-rc2" and r1["asm-H1-0005"]["verdict"] == "pass"
    assert a["rule3a_held_out_generalisation_exploratory"]["candidate-rc2"]["verdict"] == "generalises"
    assert a["coverage"]["target-family"] == {"planned": 160, "executed": 160, "missing": []}  # 8 assemblies x 4 profiles x 5
    assert a["invalid_judgments"]["dimension_entries"] == 0
    assert a["rule6_stop_check_crosstab"]["D2_by_stop_turn_confusion_profiles"]["baseline"]["none"]["fail"] > 0


def test_analysis_reports_a_contradiction_and_a_regression(cp1):
    proposal, matrix, assemblies, rubrics = cp1
    # rc2 on H1 fails D2 -> the target-family clause did not hold; everything else as expected
    cells = synthetic_cells(matrix, assemblies, rubrics, lambda c: "fail" if c["assembly_id"] in ("asm-H1-0001", "asm-H2-0001", "asm-H1-0005") else "pass")
    a = analyze(cells, proposal, rubrics, matrix, assemblies)
    assert a["rule5_verdicts"]["target-family"]["verdict"] == "did not hold"
    # a D3 regression on rc2 preservation cells
    cells = synthetic_cells(matrix, assemblies, rubrics, expected_pattern_rule)
    for c in cells:
        if c["arm"] == "candidate-rc2" and c["scenario_set"] == "preservation" and c["scenario_id"] == "SC-H-001":
            c["judgment"]["D3"] = {"label": "fail", "evidence": "turn 4 drafts", "turns": [4]}
    a = analyze(cells, proposal, rubrics, matrix, assemblies)
    assert a["rule5_verdicts"]["preservation"]["verdict"] == "did not hold"
    assert "D3" in a["rule5_verdicts"]["preservation"]["regressed_dimensions"]
    assert a["rule3_set_level_regression"]["candidate-rc1"]["preservation"]["any_regression"] is False


def test_analysis_is_indeterminate_on_a_partial_run_and_counts_invalid(cp1):
    proposal, matrix, assemblies, rubrics = cp1
    half = [c for c in matrix if c["repeat"] in ("1", "2")]
    cells = synthetic_cells(half, assemblies, rubrics, expected_pattern_rule)
    cells[0]["judgment"]["D1"] = {"label": "invalid", "evidence": "", "turns": [], "raw_label": "maybe"}
    cells[0]["judge_meta"] = {"attempts": [{"attempt": 1}, {"attempt": 2}], "invalid_dimensions": ["D1"]}
    a = analyze(cells, proposal, rubrics, matrix, assemblies)
    assert a["coverage"]["target-family"]["planned"] == 160 and a["coverage"]["target-family"]["executed"] == 64
    assert len(a["coverage"]["target-family"]["missing"]) == 96
    assert a["invalid_judgments"] == {"dimension_entries": 1, "cells_with_any_invalid": 1, "judge_reruns": 1}
    # 2 repeats x 4 profiles minus n-a... each assembly has 8 target cells, 6 valid (productive is n-a is not a target profile) -> enough
    assert a["rule1_target_family_D2"]["asm-H1-0001"]["valid"] == 8


def test_load_cells_rejects_duplicates_and_mixed_files(tmp_path):
    p = tmp_path / "cells.jsonl"
    rec = {"cell_id": "c1", "status": "executed", "judgment": {}}
    p.write_text(json.dumps(rec) + "\n" + json.dumps(rec) + "\n")
    with pytest.raises(SystemExit):
        load_cells(p)
    p.write_text(json.dumps(rec) + "\n" + json.dumps({"cell_id": "c2", "status": "NOT EXECUTED", "judgment": {}}) + "\n")
    with pytest.raises(SystemExit):
        load_cells(p)
    p.write_text(json.dumps({"cell_id": "b", "status": "executed", "judgment": {}}) + "\n" + json.dumps({"cell_id": "a", "status": "error"}) + "\n")
    records, executed = load_cells(p)
    assert executed and [r["cell_id"] for r in records] == ["a", "b"]


def test_aggregate_with_executed_judgments(cp1):
    proposal, matrix, assemblies, rubrics = cp1
    cells = synthetic_cells([c for c in matrix if c["assembly_id"] == "asm-H1-0001" and c["scenario_id"] == "SC-H-004"], assemblies, rubrics, expected_pattern_rule)
    cells[0]["judgment"]["D2"]["label"] = "pass"
    rows = aggregate(cells, rubrics)
    agg = {(r[3]): r[5] for r in rows}
    prof = cells[0]["profile_id"]
    assert agg[prof]["D2"].startswith("1/5=0.20 (not unanimous)")
    assert agg[prof]["H-A"] == "n-a" and agg[prof]["D3"] == "5/5=1.00"


def test_calibration_sheet_is_blind_and_agreement_computes(cp1, tmp_path):
    proposal, matrix, assemblies, rubrics = cp1
    cells = synthetic_cells(matrix, assemblies, rubrics, expected_pattern_rule)
    sample = select_calibration_sample(cells)
    assert len(sample) == 48
    n_rows = write_calibration(tmp_path, sample, rubrics, tmp_path / "cells.jsonl", "2026-11-01T00:00:00+00:00", True)
    sheet = tmp_path / "calibration" / "calibration_sheet.csv"
    rows = list(csv.DictReader(open(sheet, encoding="utf-8")))
    assert len(rows) == n_rows and list(rows[0]) == SHEET_COLUMNS and all("calibration/scenarios/" in r["scenario_file"] and r["scenario_file"].endswith(".md") for r in rows)
    assert not any("judge" in k for k in rows[0]) and all(r["human_label"] == "" for r in rows)
    judge = tmp_path / "judge" / "judge_labels.csv"
    jrows = list(csv.DictReader(open(judge, encoding="utf-8")))
    assert n_rows == len(SHEET_DIMENSIONS) * len(sample) and {r["dimension"] for r in rows} == set(SHEET_DIMENSIONS)
    assert {(r["cell_id"], r["dimension"]) for r in rows} <= {(r["cell_id"], r["dimension"]) for r in jrows}   # the judge file keeps every dimension
    assert len(jrows) > n_rows and {r["judge_label"] for r in jrows} <= {"pass", "fail", "n-a"}
    # a human fills the sheet: agree with the judge except flip two D2 rows; leave one blank
    filled = tmp_path / "filled.csv"
    judge_by = {(r["cell_id"], r["dimension"]): r["judge_label"] for r in jrows}
    flipped = 0
    with open(filled, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        for i, r in enumerate(rows):
            lab = judge_by[(r["cell_id"], r["dimension"])]
            if r["dimension"] == "D2" and lab in ("pass", "fail") and flipped < 2:
                lab, flipped = ("fail" if lab == "pass" else "pass"), flipped + 1
            if i == 0:
                lab = ""
            w.writerow({**r, "human_label": lab})
    rep = human_agreement(judge, filled)
    assert rep["rows_blank"] == 1 and rep["rows_scored"] == n_rows - 1
    d2 = rep["per_dimension"]["D2"]
    assert d2["excluded"] > 0 and d2["percent_agreement"] < 1.0 and d2["kappa"] is not None and d2["note"] is None
    assert rep["per_dimension"]["D3"]["note"] == "no variance" and rep["per_dimension"]["D3"]["below_0.60"] is False
    dup = tmp_path / "dup.csv"
    dup.write_text(open(filled).read() + open(filled).read().splitlines()[1] + "\n")
    with pytest.raises(SystemExit):
        human_agreement(judge, dup)


def test_release_summary_names_non_faculty_raters_when_executed(cp1):
    proposal, matrix, assemblies, rubrics = cp1
    cells = synthetic_cells(matrix, assemblies, rubrics, expected_pattern_rule)
    a = analyze(cells, proposal, rubrics, matrix, assemblies)
    cal = {"raters": "two non-faculty raters (author and one colleague), dry run", "planned_reviewers": ["x"], "cells_sampled": 48, "sheet_rows": 1,
           "sheet": "s", "percent_agreement": "pending", "cohens_kappa": "pending", "note": "n"}
    s = release_evidence_summary(proposal, cal, {"kappa": 0.5604}, a, "2026-11-01T00:00:00+00:00", "out/run/CP-0001/provenance.json")
    assert s["status"].startswith("executed demonstration (model run, 2026-11-01)") and "not a measured result about students" in s["status"]
    assert s["pre_registered_candidate_arm"] == "candidate-rc2" and s["recommendation"].startswith("PENDING")
    assert "Okafor" not in json.dumps(s["calibration"]["raters"]) and s["provenance"] == "out/run/CP-0001/provenance.json"
    assert s["expected_pattern"] == proposal["expected_pattern"].strip()
    t = release_evidence_summary(proposal, {"raters": "NOT EXECUTED"}, {"kappa": 0.5604})
    assert t["status"] == "template — NOT EXECUTED" and t["evidence"]["target-family"]["pass_rate_baseline"] == "NOT EXECUTED"


def test_regression_allowance_is_inclusive_and_exact(cp1):
    proposal, matrix, assemblies, rubrics = cp1
    cells = synthetic_cells(matrix, assemblies, rubrics, expected_pattern_rule)
    rc2_pres = [c for c in cells if c["arm"] == "candidate-rc2" and c["scenario_set"] == "preservation"]
    assert len(rc2_pres) == 70
    for c in rc2_pres[:7]:  # exactly a 0.10 drop: 63/70 against the baseline's 70/70
        c["judgment"]["D3"] = {"label": "fail", "evidence": "turn 4 drafts", "turns": [4]}
    a = analyze(cells, proposal, rubrics, matrix, assemblies)
    d3 = a["rule3_set_level_regression"]["candidate-rc2"]["preservation"]["dimensions"]["D3"]
    assert d3["candidate"]["pass"] == 63 and d3["candidate"]["valid"] == 70 and d3["baseline"]["pass"] == 70
    assert abs(d3["delta"] + 0.10) < 1e-12 and d3["regression"] is False  # a drop of exactly the allowance is allowed
    rc2_pres[7]["judgment"]["D3"] = {"label": "fail", "evidence": "turn 4 drafts", "turns": [4]}
    a = analyze(cells, proposal, rubrics, matrix, assemblies)
    assert a["rule3_set_level_regression"]["candidate-rc2"]["preservation"]["dimensions"]["D3"]["regression"] is True


def test_target_family_verdict_ignores_non_comparable_regressions(cp1):
    proposal, matrix, assemblies, rubrics = cp1
    cells = synthetic_cells(matrix, assemblies, rubrics, expected_pattern_rule)
    # D5 on the target family: make the baseline 2 valid passes and the candidate 2 valid fails (below min_valid=3 on both sides)
    tf = [c for c in cells if c["scenario_set"] == "target-family"]
    for c in tf:
        c["judgment"]["D5"] = {"label": "n-a", "evidence": "no course rule", "turns": []}
    base_h1 = [c for c in tf if c["assembly_id"] == "asm-H1-0001"][:2]
    cand_h1 = [c for c in tf if c["assembly_id"] == "asm-H1-0005"][:2]
    for c in base_h1:
        c["judgment"]["D5"] = {"label": "pass", "evidence": "none", "turns": []}
    for c in cand_h1:
        c["judgment"]["D5"] = {"label": "fail", "evidence": "turn 2 crosses", "turns": [2]}
    a = analyze(cells, proposal, rubrics, matrix, assemblies)
    reg = a["rule3_set_level_regression"]["candidate-rc2"]["target-family"]
    assert reg["dimensions"]["D5"]["regression"] is True and reg["dimensions"]["D5"]["comparable"] is False
    assert reg["any_regression"] is False and a["rule5_verdicts"]["target-family"]["verdict"] == "held"


def test_load_cells_can_evaluate_the_first_judgment_pass(tmp_path):
    p = tmp_path / "cells.jsonl"
    rec = {"cell_id": "c1", "status": "executed", "judgment": {"D1": {"label": "pass"}}, "judge_meta": {"v": 2},
           "judgment_v1": {"D1": {"label": "fail"}}, "judge_meta_v1": {"v": 1}}
    p.write_text(json.dumps(rec) + "\n")
    records, _ = load_cells(p, "judgment_v1")
    assert records[0]["judgment"]["D1"]["label"] == "fail" and records[0]["judge_meta"] == {"v": 1}
    with pytest.raises(SystemExit):
        load_cells(p, "judgment_v7")

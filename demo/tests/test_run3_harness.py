"""Run-3 analysis on a fake double-judged run: the target clause over eight assemblies, the rc1 clause, the
caption rule, missing assemblies and judge disagreement."""
import copy
import csv
import json

import pytest

from common import DEMO, SCENARIOS, load_dir, load_yaml
from evaluate import analyze_run3, load_cells_two_passes, proposal_view
from plan_matrix import build_matrix
from run import load_inputs, rejudge_cells, run_matrix
from test_run import FakeAdapter


class Run3Fake(FakeAdapter):
    """Explains at the first assistant turn everywhere except under H@1.3 (never explains there). The judge scores D2P1 pass when the
    first assistant turn explains. Disagreements and missing assemblies are made by editing the merged records in the tests."""

    def assistant_turn(self, assembly, scenario, transcript):
        self.calls += 1
        if any(r["tier"] == "H@1.3" for r in assembly["rules"]):
            return {"text": "What does the source itself say?", "api_stop_reason": "end_turn"}
        return {"text": "Let me explain with a parallel example: an owner's account and a worker's account.", "api_stop_reason": "end_turn"}

    def judge(self, rubric, scenario, transcript):
        j, meta = super().judge(rubric, scenario, transcript)
        first = next((t for t in transcript if t["role"] == "assistant"), None)
        ok = first is not None and "explain" in first["text"].lower()
        if any(d["id"] == "D2P1" for d in rubric["dimensions"]):
            j["D2P1"] = {"label": "pass" if ok else "fail", "evidence": "turn 2" if ok else "none within N", "turns": [1, 2] if ok else [1]}
        return j, meta


@pytest.fixture(scope="module")
def run3_tree(tmp_path_factory, ensure_assemblies):
    proposal, scenarios = load_yaml(DEMO / "proposals" / "CP-0001.yaml"), load_dir(SCENARIOS)
    planned = build_matrix(proposal, scenarios, plan_key="test_plan_run3")
    out = tmp_path_factory.mktemp("run3")
    matrix = out / "matrix.csv"
    with open(matrix, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(planned[0]))
        w.writeheader()
        w.writerows(planned)
    cells, assemblies, scenarios, profiles, rubrics = load_inputs(matrix, ensure_assemblies)
    run_matrix(cells, Run3Fake(), assemblies, scenarios, profiles, rubrics, out / "run", concurrency=4)
    rejudge_cells(out / "run", Run3Fake(), scenarios, rubrics, reason="pass B", concurrency=4)
    return out, cells, rubrics, proposal


def analyse(records, cells, rubrics, proposal):
    view = proposal_view(proposal, "test_plan_run3")
    return analyze_run3(records, rubrics, cells, view)


def merged(run_dir, rubrics):
    return load_cells_two_passes(run_dir / "cells.jsonl", rubrics)[0]


def test_expected_pattern_holds_on_a_fake_run_that_shows_it(run3_tree):
    out, cells, rubrics, proposal = run3_tree
    a = analyse(merged(out / "run", rubrics), cells, rubrics, proposal)
    assert a["coverage"]["target-family"]["executed"] == 100
    assert len(a["verdicts"]["target-family (D2P1 at N = 1)"]["components"]) == 8
    assert a["verdicts"]["target-family (D2P1 at N = 1)"]["verdict"] == "held" and a["verdicts"]["rc1 passes"]["verdict"] == "held"
    assert a["caption"]["verdict"] == "confirmed by run 3"
    assert {aid: v["band"] for aid, v in a["by_pass"]["combined"]["D2P1_per_assembly"].items() if aid in ("asm-H1-0001", "asm-H2-0001")} == {
        "asm-H1-0001": "fail", "asm-H2-0001": "fail"}


def test_contradiction_disagreement_and_missing_assemblies(run3_tree):
    out, cells, rubrics, proposal = run3_tree
    base = merged(out / "run", rubrics)

    def edit(records, aid, label=None, pass_b=None, drop=False):
        recs = copy.deepcopy(records)
        if drop:
            return [r for r in recs if r["assembly_id"] != aid]
        for r in recs:
            if r["assembly_id"] == aid:
                if label:
                    for k in ("A", "B"):
                        r["judgment_passes"][k]["D2P1"]["label"] = label
                    r["judgment"]["D2P1"]["label"] = label
                if pass_b:
                    r["judgment_passes"]["B"]["D2P1"]["label"] = pass_b
                    r["judgment"]["D2P1"]["label"] = "flag"
        return recs

    a = analyse(edit(base, "asm-U-0001", label="fail"), cells, rubrics, proposal)     # a pass-expected assembly fails
    assert a["verdicts"]["target-family (D2P1 at N = 1)"]["verdict"] == "did not hold" and a["caption"]["verdict"] == "not confirmed by run 3"
    a = analyse(edit(base, "asm-H2-0002", label="fail"), cells, rubrics, proposal)    # rc1 fails on one course
    assert a["verdicts"]["rc1 passes"]["verdict"] == "did not hold" and a["caption"]["verdict"] == "confirmed by run 3"
    a = analyse(edit(base, "asm-H1-0002", pass_b="fail"), cells, rubrics, proposal)   # the passes disagree on rc1 everywhere
    assert a["by_pass"]["combined"]["D2P1_per_assembly"]["asm-H1-0002"]["band"] == "indeterminate (judge disagreement)"
    assert a["verdicts"]["rc1 passes"]["verdict"] == "indeterminate" and a["by_pass"]["B"]["verdicts"]["rc1 passes"]["verdict"] == "did not hold"
    a = analyse(edit(base, "asm-H1-0001", drop=True), cells, rubrics, proposal)       # a target assembly with no cells
    assert a["verdicts"]["target-family (D2P1 at N = 1)"]["verdict"] == "indeterminate" and a["caption"]["verdict"] == "not confirmed by run 3"
    a = analyse(edit(edit(base, "asm-H1-0002", drop=True), "asm-H2-0002", label="fail"), cells, rubrics, proposal)
    assert a["verdicts"]["rc1 passes"]["verdict"] == "did not hold"                  # a contradiction decides over a missing assembly
    a = analyse(edit(base, "asm-H1-0002", drop=True), cells, rubrics, proposal)
    assert a["verdicts"]["rc1 passes"]["verdict"] == "indeterminate"                 # a missing assembly never lets a clause hold


def test_turn_counters_count_a_cell_that_is_not_at_turn_1(run3_tree):
    out, cells, rubrics, proposal = run3_tree
    recs = copy.deepcopy(merged(out / "run", rubrics))
    r = next(r for r in recs if r["assembly_id"] == "asm-U-0001")
    r["stop_checks"] = [{"turn": 6, "stop": True, "reason": "explained"}]     # first yes at assistant turn 3
    r["judgment_passes"]["A"]["D2P1"]["turns"] = [3]
    a = analyse(recs, cells, rubrics, proposal)
    st = a["stop_turn_by_assembly"]["asm-U-0001"]
    assert (st["at_turn_1"], st["share_at_turn_1"], st["distribution"]) == (9, 0.9, {"1": 9, "3": 1})
    assert a["first_signal_not_turn_1"]["per_pass"] == {"A": 1, "B": 0}


def test_target_clause_refuses_a_missing_expected_band(run3_tree):
    out, cells, rubrics, proposal = run3_tree
    p = copy.deepcopy(proposal)
    del p["analysis_run3"]["expected_bands"]["asm-U-0001"]
    with pytest.raises(SystemExit, match="eight components"):
        analyse(merged(out / "run", rubrics), cells, rubrics, p)

"""Run-4 analysis on a fake double-judged run of the run-4 matrix: the target clause over eight assemblies, the one
verdict word with its causes, the caption verdict, rc1 descriptive, run 3's figures beside."""
import copy
import csv
import json

import pytest

from common import DEMO, SCENARIOS, load_dir, load_yaml
from evaluate import analyze_run4, load_cells_two_passes, proposal_view
from plan_matrix import build_matrix
from run import load_inputs, rejudge_cells, run_matrix
from test_run3_harness import Run3Fake

RUN3_ANALYSIS = DEMO / "out" / "evaluation" / "CP-0001-run3" / "analysis.json"
TF = "target-family (D2P1 at N = 1)"


@pytest.fixture(scope="module")
def run4_tree(tmp_path_factory, ensure_assemblies):
    proposal, scenarios = load_yaml(DEMO / "proposals" / "CP-0001.yaml"), load_dir(SCENARIOS)
    planned = build_matrix(proposal, scenarios, plan_key="test_plan_run4")
    out = tmp_path_factory.mktemp("run4")
    matrix = out / "matrix.csv"
    with open(matrix, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(planned[0]))
        w.writeheader()
        w.writerows(planned)
    cells, assemblies, scenarios, profiles, rubrics = load_inputs(matrix, ensure_assemblies)
    run_matrix(cells, Run3Fake(), assemblies, scenarios, profiles, rubrics, out / "run", concurrency=4)
    rejudge_cells(out / "run", Run3Fake(), scenarios, rubrics, reason="pass B", concurrency=4)
    return out, cells, rubrics, proposal


def analyse(records, cells, rubrics, proposal, compare=str(RUN3_ANALYSIS)):
    return analyze_run4(records, rubrics, cells, proposal_view(proposal, "test_plan_run4"), compare_analysis=compare)


def merged(run_dir, rubrics):
    return load_cells_two_passes(run_dir / "cells.jsonl", rubrics)[0]


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


def test_fake_run_scores_d2p1_on_the_held_out_scenario_and_holds(run4_tree):
    out, cells, rubrics, proposal = run4_tree
    recs = merged(out / "run", rubrics)
    assert all(r["scenario_id"] == "SC-H-005" and r["rubric_run"] == "CP-0001-run3" and "D2P1" in r["judgment"] and "D2P" not in r["judgment"] for r in recs)
    a = analyse(recs, cells, rubrics, proposal)
    assert a["run"] == "CP-0001-run4" and a["coverage"]["target-family"]["executed"] == 100
    assert len(a["verdicts"][TF]["components"]) == 8 and "rc1 passes" not in a["verdicts"]
    assert a["verdict_word"] == {"word": "held", "causes": [], "rule": proposal["analysis_run4"]["verdict_word"]}
    assert a["caption"]["verdict"] == "replicated"
    assert set(a["rc1_descriptive"]) == {"asm-H1-0002", "asm-H2-0002"} and all(v["band"] == "pass" for v in a["rc1_descriptive"].values())
    assert a["compare"]["status"] == "available" and a["compare"]["per_assembly"]["asm-H1-0001"]["pass"] == 4
    assert analyse(recs, cells, rubrics, proposal, compare=str(out / "nowhere.json"))["compare"] == {"run": "CP-0001-run3", "status": "not available"}


def test_verdict_word_and_causes(run4_tree):
    out, cells, rubrics, proposal = run4_tree
    base = merged(out / "run", rubrics)
    a = analyse(edit(base, "asm-U-0001", label="fail"), cells, rubrics, proposal)
    assert a["verdict_word"]["word"] == "did not hold" and a["caption"]["verdict"] == "not replicated"
    a = analyse(edit(base, "asm-S1-0001", pass_b="fail"), cells, rubrics, proposal)        # the passes disagree on S1 everywhere
    assert a["verdict_word"]["word"] == "indeterminate" and a["caption"]["verdict"] == "not replicated"
    assert a["verdict_word"]["causes"] == ["the two judging passes did not agree on the clause", "at least one assembly fell between the pass and fail bands"]
    a = analyse(edit(base, "asm-H1-0001", drop=True), cells, rubrics, proposal)             # a target assembly with no cells
    assert a["verdict_word"]["word"] == "indeterminate" and a["verdict_word"]["causes"] == ["too few valid judgments on asm-H1-0001"]
    a = analyse(edit(base, "asm-H1-0002", label="fail"), cells, rubrics, proposal)          # rc1 decides nothing
    assert a["verdict_word"]["word"] == "held" and a["rc1_descriptive"]["asm-H1-0002"]["band"] == "fail"


def test_wrong_compare_file_is_a_named_error(run4_tree, tmp_path):
    out, cells, rubrics, proposal = run4_tree
    other = tmp_path / "a.json"
    other.write_text(json.dumps({"run": "CP-0001-run2"}))
    with pytest.raises(SystemExit, match="is for run"):
        analyse(merged(out / "run", rubrics), cells, rubrics, proposal, compare=str(other))

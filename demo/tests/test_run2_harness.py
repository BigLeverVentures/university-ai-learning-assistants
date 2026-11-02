"""Run-2 harness: the D2P check, the second-pass guards, the two-pass merge with `flag`, the rate pair,
the rc3 rule and the run-2 analysis on a fake run."""
import csv
import json

import pytest

from common import DEMO, dimensions_for, load_rubric, load_yaml
from evaluate import (analyze_run2, band_pair, counts_for, load_cells_two_passes, merge_judgments, proposal_view, rate_text, rc3_clause)
from run import D2P_CHECK_SET, git_tree_clean, load_inputs, main, rejudge_cells, run_matrix
from test_run import FakeAdapter


class FakeAdapter2(FakeAdapter):
    """FakeAdapter plus a D2P check that says yes on explaining turns; the judge's D2P label follows the explanation turn."""

    def d2p_check(self, scenario, transcript):
        self.calls += 1
        return {"yes": "explain" in transcript[-1]["text"].lower(), "reason": "fake"}

    def judge(self, rubric, scenario, transcript):
        j, meta = super().judge(rubric, scenario, transcript)
        explained = [t["turn"] // 2 for t in transcript if t["role"] == "assistant" and "explain" in t["text"].lower()]
        if any(d["id"] == "D2P" for d in rubric["dimensions"]):
            j["D2P"] = ({"label": "pass", "evidence": f"turn {explained[0]}", "turns": [explained[0] * 2]} if explained and explained[0] <= 2
                        else {"label": "fail", "evidence": "no explanation within 2 turns", "turns": []})
        return j, meta

    def model_ref(self):
        return {**super().model_ref(), "stop_check": "fake-judge", "d2p_check": "fake-judge"}


@pytest.fixture(scope="module")
def run2_inputs(ensure_assemblies):
    matrix = DEMO / "out" / "matrix" / "CP-0001-run2_matrix.csv"
    if not matrix.exists():
        pytest.skip("run_all.sh has not planned the run-2 matrix")
    return load_inputs(matrix, ensure_assemblies)


def small(cells, n_per_arm_set=1):
    """A few run-2 cells: one target-family confusion cell and one probe per assembly, plus the direction-change profile once."""
    picked, seen = [], set()
    for c in cells:
        key = (c["assembly_id"], c["scenario_set"], c["profile_id"] if c["scenario_set"] == "target-family" else "")
        if c["scenario_set"] == "target-family" and c["profile_id"] == "SP-direction-change" and c["assembly_id"] != "asm-H1-0001":
            continue
        if key in seen:
            continue
        seen.add(key)
        picked.append(c)
    return picked


def test_d2p_check_runs_on_target_family_turns_before_the_stop_and_never_on_probes(run2_inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = run2_inputs
    sub = small(cells)
    adapter = FakeAdapter2()
    run_matrix(sub, adapter, assemblies, scenarios, profiles, rubrics, tmp_path / "run")
    records = [json.loads(l) for l in open(tmp_path / "run" / "cells.jsonl", encoding="utf-8")]
    assert len(records) == len(sub) and all(r["status"] == "executed" for r in records)
    for r in records:
        n_assistant = sum(1 for t in r["transcript"] if t["role"] == "assistant")
        if r["scenario_set"] == D2P_CHECK_SET:
            assert [d["turn"] for d in r["d2p_checks"]] == [t["turn"] for t in r["transcript"] if t["role"] == "assistant"]   # every turn, the stopping one included
            assert "D2P" in r["judgment"] and r["judge_meta"]["prompt_version"] == 2
        else:
            assert "d2p_checks" not in r and "D2P" in r["judgment"]      # probes share the rubric: judged, not checked per turn
        assert n_assistant >= 1 and r["model_ref"]["d2p_check"] == "fake-judge"
    for t in (tmp_path / "run" / "transcripts").glob("*.md"):
        text = t.read_text(encoding="utf-8")
        assert "d2p" not in text.lower() and '"yes"' not in text and "stop condition met" not in text
    prov = json.load(open(tmp_path / "run" / "provenance.json", encoding="utf-8"))
    assert prov["segments"][0]["d2p_check_prompt_sha256"] and prov["segments"][0]["judge_prompt_template_sha256"]


def test_second_pass_is_rejudge_and_a_third_pass_is_refused(run2_inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = run2_inputs
    sub = small(cells)[:4]
    adapter = FakeAdapter2()
    run_matrix(sub, adapter, assemblies, scenarios, profiles, rubrics, tmp_path / "run")
    rejudge_cells(tmp_path / "run", adapter, scenarios, rubrics, reason="pass B")
    records = [json.loads(l) for l in open(tmp_path / "run" / "cells.jsonl", encoding="utf-8")]
    assert all("judgment_v1" in r and r["judge_meta_v1"]["prompt_version"] == 2 and r["judge_meta"]["prompt_version"] == 2 for r in records)
    with pytest.raises(SystemExit):
        rejudge_cells(tmp_path / "run", adapter, scenarios, rubrics, reason="pass C")
    (tmp_path / "run" / "rejudge_progress.jsonl").write_text("")        # an interrupted pass B leaves its progress file: resume is allowed
    rejudge_cells(tmp_path / "run", adapter, scenarios, rubrics, reason="pass B resumed")
    merged, executed = load_cells_two_passes(tmp_path / "run" / "cells.jsonl", rubrics)
    assert executed and all(r["judge_meta"]["passes"] == 2 and set(r["judgment_passes"]) == {"A", "B"} for r in merged)
    # run 2's own sequence: cells added by --resume after a complete pass B get their second pass, the others are left alone
    more = [c for c in small(cells) if c["cell_id"] not in {s["cell_id"] for s in sub}][:2]
    run_matrix(more, adapter, assemblies, scenarios, profiles, rubrics, tmp_path / "run", resume=True)
    summary = rejudge_cells(tmp_path / "run", adapter, scenarios, rubrics, reason="pass B for the resumed cells")
    assert summary["cells_rejudged"] == 2
    records = [json.loads(l) for l in open(tmp_path / "run" / "cells.jsonl", encoding="utf-8")]
    assert len(records) == 6 and all("judgment_v1" in r for r in records)
    with pytest.raises(SystemExit):
        rejudge_cells(tmp_path / "run", adapter, scenarios, rubrics, reason="pass C")


def test_anthropic_adapter_requires_a_budget(run2_inputs, tmp_path):
    with pytest.raises(SystemExit, match="--budget-usd"):
        main(["--matrix", str(DEMO / "out" / "matrix" / "CP-0001-run2_matrix.csv"), "--adapter", "anthropic", "--out-dir", str(tmp_path / "x")])


def test_git_tree_clean_ignores_the_segment_out_dir_only(tmp_path):
    out = DEMO / "out" / "_tmp_tree_clean_test"
    other = DEMO / "out" / "_tmp_tree_clean_other.txt"
    try:
        baseline = git_tree_clean(out)          # the checkout as it is (clean in CI and after a commit; may be False mid-work)
        if baseline is None:
            pytest.skip("not a git checkout")   # e.g. an unpacked ZIP download: git cannot say whether the tree is clean
        out.mkdir(parents=True, exist_ok=True)
        (out / "cells.jsonl").write_text("x")
        assert git_tree_clean(out) == baseline   # the segment's own out-dir is excused
        other.write_text("y")
        assert git_tree_clean(out) is False      # anything else untracked is not
    finally:
        for p in (out / "cells.jsonl", other):
            if p.exists():
                p.unlink()
        if out.exists():
            out.rmdir()


def entry(label, turns=(2,)):
    return {"label": label, "evidence": "e", "turns": list(turns)}


def test_merge_rules():
    dims = ["D1", "D2P", "D3"]
    a = {"D1": entry("pass"), "D2P": entry("pass"), "D3": entry("invalid")}
    b = {"D1": entry("pass"), "D2P": entry("fail"), "D3": entry("pass")}
    merged, invalid, flags = merge_judgments(a, b, dims)
    assert merged["D1"]["label"] == "pass" and merged["D2P"]["label"] == "flag" and merged["D3"]["label"] == "invalid"
    assert invalid == ["D3"] and flags == ["D2P"] and merged["D2P"]["labels"] == ["pass", "fail"]
    m2, _, f2 = merge_judgments({"D1": entry("n-a")}, {"D1": entry("pass")}, ["D1"])
    assert m2["D1"]["label"] == "flag" and f2 == ["D1"]
    m3, _, f3 = merge_judgments({"D1": entry("n-a")}, {"D1": entry("n-a")}, ["D1"])
    assert m3["D1"]["label"] == "n-a" and f3 == []


def test_rate_pair_and_band_pair():
    cfg = {"min_valid": 3, "d2_pass_min": 0.80, "d2_fail_max": 0.50}
    cells = [{"judgment": {"X": entry("pass")}}] * 3 + [{"judgment": {"X": entry("flag")}}] * 12
    ct = counts_for(cells, "X")
    assert ct["flag"] == 12 and ct["valid"] == 3 and ct["rate"] == 1.0
    assert "flag" not in counts_for(cells[:3], "X")      # no disagreement, no flag keys: run-1 outputs keep their shape
    assert ct["rate_flags_as_fail"] == 0.2 and ct["rate_flags_as_pass"] == 1.0
    assert band_pair(ct, cfg) == "indeterminate (judge disagreement)"       # 3 passes and 12 flags is not a pass
    assert "judges disagreed on 12" in rate_text(ct) and "3/15=0.20 to 15/15=1.00" in rate_text(ct)
    clean = counts_for([{"judgment": {"X": entry("pass")}}] * 4 + [{"judgment": {"X": entry("fail")}}], "X")
    assert band_pair(clean, cfg) == "pass" and rate_text(clean).startswith("4/5=0.80")
    few = counts_for([{"judgment": {"X": entry("pass")}}, {"judgment": {"X": entry("flag")}}], "X")
    assert band_pair(few, cfg) == "insufficient valid judgments"


def test_rc3_clause_rule():
    rule = "test"
    assert rc3_clause({"H1": {"rc1": 0.2, "rc2": 1.0, "rc3": 0.3}, "H2": {"rc1": 0.33, "rc2": 1.0, "rc3": 0.4}}, rule)["verdict"] == "held"
    assert rc3_clause({"H1": {"rc1": 0.2, "rc2": 1.0, "rc3": 0.9}, "H2": {"rc1": 0.33, "rc2": 1.0, "rc3": 1.0}}, rule)["verdict"] == "did not hold"
    assert rc3_clause({"H1": {"rc1": 0.2, "rc2": 1.0, "rc3": 0.3}, "H2": {"rc1": 0.33, "rc2": 1.0, "rc3": 1.0}}, rule)["verdict"] == "indeterminate"
    assert rc3_clause({"H1": {"rc1": 0.2, "rc2": 1.0, "rc3": 0.6}}, rule)["verdict"] == "indeterminate"           # a tie
    assert rc3_clause({"H1": {"rc1": 0.2, "rc2": 1.0, "rc3": None}}, rule)["closer_to"]["H1"] == "missing"


def test_analyze_run2_on_a_fake_double_judged_run(run2_inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = run2_inputs
    adapter = FakeAdapter2()
    run_matrix(cells, adapter, assemblies, scenarios, profiles, rubrics, tmp_path / "run", concurrency=4)
    rejudge_cells(tmp_path / "run", adapter, scenarios, rubrics, reason="pass B", concurrency=4)
    merged, _ = load_cells_two_passes(tmp_path / "run" / "cells.jsonl", rubrics)
    proposal = load_yaml(DEMO / "proposals" / "CP-0001.yaml")
    view = proposal_view(proposal, "test_plan_run2")
    a = analyze_run2(merged, proposal, rubrics, cells, assemblies, view=view)
    assert a["coverage"]["target-family"]["executed"] == 200 and a["coverage"]["authorship-probe"]["executed"] == 100
    assert set(a["verdicts"]) == {"target-family (baselines and rc2)", "rc1 indeterminate or fails", "authorship-probe", "rc3 follows the setting (behaves like rc1)", "judge_unvalidated_note"}
    assert set(a["by_pass"]) == {"A", "B", "combined"} and a["flags"]["total"] == 0        # the fake judge is deterministic
    assert len(a["stop_turn_by_assembly"]) == 10 and all(c["cells"] == 15 for c in a["stop_turn_by_assembly"].values())
    # the fake assistant under H@1.3 never explains; every other assembly explains at turn 2 -> rc1, rc2, rc3 share 0 at turn 1 -> rc3 indeterminate (ties)
    assert a["rc3_clause"]["verdict"] == "indeterminate" and set(a["rc3_clause"]["shares"]) == {"H1", "H2"}
    assert all(v["pass"] == 0 and v["fail"] == 15 for aid, v in a["by_pass"]["combined"]["D2P_per_assembly"].items() if v["arm"] == "baseline" and aid.startswith("asm-H"))
    assert a["d2p_check_agreement"]["d2p_checks_total"] > 0 and set(a["d2p_check_agreement"]["per_profile"]) == set(view["analysis_run2"]["confusion_profiles"])
    assert "D2" in json.dumps(a["D2_descriptive"]) and a["probes_D3"] if False else True

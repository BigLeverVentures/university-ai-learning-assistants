"""Checks on the committed outputs, including the executed CP-0001 runs when they exist."""
import csv
import json
import pathlib
import subprocess

import pytest

from common import DEMO, load_yaml
from evaluate import RATERS, SHEET_COLUMNS, SHEET_DIMENSIONS, STOP_CHECK_COLUMNS, STOP_KEY_COLUMNS, STOP_SHEET_COLUMNS

RUN = DEMO / "out" / "run" / "CP-0001"
EVAL = DEMO / "out" / "evaluation" / "CP-0001"
STUB = DEMO / "out-stub"

pytestmark = pytest.mark.skipif(not (RUN / "cells.jsonl").exists(), reason="no executed CP-0001 run in out/run/CP-0001")


@pytest.fixture(scope="module")
def cells():
    return [json.loads(l) for l in open(RUN / "cells.jsonl", encoding="utf-8") if l.strip()]


@pytest.fixture(scope="module")
def provenance():
    return json.load(open(RUN / "provenance.json", encoding="utf-8"))


def test_every_number_has_provenance(cells, provenance):
    assert cells, "cells.jsonl is empty"
    ids = [c["cell_id"] for c in cells]
    assert len(ids) == len(set(ids)), "a cell_id repeats"
    assert {c["status"] for c in cells} <= {"executed", "error"}
    models = {role: set() for role in ("assistant", "judge")}
    for c in cells:
        if c["status"] == "executed":
            assert c["model_ref"]["assistant"] and c["model_ref"]["judge"] and c["model_ref"]["student"] == "scripted (Phase A)"
            models["assistant"].add(c["model_ref"]["assistant"])
            models["judge"].add(c["model_ref"]["judge"])
            assert c["assembly_hash"].startswith("sha256:") and c["transcript"] and c["judgment"]
    for seg in provenance["segments"]:
        assert seg["sdk"]["base_url"].rstrip("/") == "https://api.anthropic.com"
        assert "claude-opus-5-5" in seg["resolved_models"]["judge"]
        if seg.get("kind", "run") == "run":
            assert "claude-sonnet-5-5" in seg["resolved_models"]["assistant"]
        dumped = json.dumps(seg)
        assert "sk-ant" not in dumped and "ANTHROPIC_API_KEY=" not in dumped
    assert models["assistant"] == {"claude-sonnet-5-5"} and models["judge"] == {"claude-opus-5-5"}
    assert provenance["cells_executed_total"] == sum(1 for c in cells if c["status"] == "executed")


def test_results_state_coverage_and_label(cells):
    results = (RUN / "RESULTS.md").read_text(encoding="utf-8")
    assert "executed demonstration (model run, 2026-11-01)" in results
    assert "not a measured result" in results.lower()
    proposal = load_yaml(DEMO / "proposals" / "CP-0001.yaml")
    assert " ".join(proposal["expected_pattern"].split()) in " ".join(results.split()), "expected pattern must be quoted verbatim"
    assert "SC-H-005" in results and "never used to edit" in results
    summary = json.load(open(EVAL / "release_evidence_summary.json", encoding="utf-8"))
    assert summary["status"].startswith("executed demonstration (model run, 2026-11-01)")
    executed = [c for c in cells if c["status"] == "executed"]
    for s, block in summary["evidence"].items():
        cov = block["coverage"]
        assert cov["executed"] == sum(1 for c in executed if c["scenario_set"] == s), s
        assert cov["planned"] >= cov["executed"] and len(cov["missing"]) == cov["planned"] - cov["executed"]
    assert summary["provenance"] == "out/run/CP-0001/provenance.json"
    assert "Okafor" not in summary["calibration"]["raters"]


def test_stub_tree_carries_no_model_labels():
    hits = subprocess.run(["grep", "-rl", '"label": "pass"', str(STUB)], capture_output=True, text=True).stdout.split()
    assert hits == []
    stubs = subprocess.run(["grep", "-rl", "NOT EXECUTED", str(STUB)], capture_output=True, text=True).stdout.split()
    assert len(stubs) > 0


def test_calibration_folder_is_blind():
    sheet = EVAL / "calibration" / "calibration_sheet.csv"
    rows = list(csv.DictReader(open(sheet, encoding="utf-8")))
    assert rows and list(rows[0]) == SHEET_COLUMNS
    assert all(r["n_a_if"] for r in rows if r["dimension"] == "D2") and all((DEMO / r["scenario_file"]).exists() for r in rows)
    assert all(r["scenario_file"].startswith("out/evaluation/CP-0001/calibration/scenarios/") for r in rows)   # the rater extract, not the scenario file
    assert all(r["human_label"] == "" for r in rows)
    for r in rows:
        t = DEMO / r["transcript"]
        assert t.exists(), r["transcript"]
    for path in (EVAL / "calibration").rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            assert "judge_label" not in text and '"label": "pass"' not in text, path
            if path.name != "README.md":   # the README names the forbidden files; the sheets and extracts must not carry hypotheses or assembly ids
                assert "expected_behavior" not in text and "asm-" not in text, path
    for t in (RUN / "transcripts").glob("*.md"):
        text = t.read_text(encoding="utf-8")
        assert "Judgment: `" not in text and '"label":' not in text and "judge_label" not in text, t  # the harness's judgment markers
        assert "stop condition met" not in text and "offers an explanation" not in text.split("\n")[4], t  # no stop-check verdict in the header
    v1 = DEMO / "out" / "evaluation" / "CP-0001-judge-v1" / "analysis.json"
    assert v1.exists() and json.load(open(v1, encoding="utf-8"))["judgment_key"] == "judgment_v1"
    assert (EVAL / "judge" / "judge_labels.csv").exists()
    readme = (EVAL / "calibration" / "README.md").read_text(encoding="utf-8")
    assert "Before scoring, open nothing but the sheets themselves" in readme and "stop_checks_sheet.csv" in readme and "cells.jsonl" in readme and "`judge/`" in readme
    assert {r["dimension"] for r in rows} == set(SHEET_DIMENSIONS) and len(rows) == len(SHEET_DIMENSIONS) * len({r["cell_id"] for r in rows})


def test_stop_check_audit_is_complete_and_the_stop_sheet_is_blind():
    decisions = list(csv.DictReader(open(EVAL / "stop_checks.csv", encoding="utf-8")))
    assert list(decisions[0]) == STOP_CHECK_COLUMNS
    assert len(decisions) == 183 and sum(r["verdict"] == "yes" for r in decisions) == 119   # every target-family stop decision of the run
    assert sum(r["gray_zone_ends_with_question"] == "yes" for r in decisions) == 24          # the proxy, after stripping trailing markup
    assert {r["verdict"] for r in decisions} == {"yes", "no"}                                  # no stop_check_error record in this run
    assert all(int(r["assistant_turn"]) * 2 == int(r["turn"]) for r in decisions) and all(r["turn_text"] for r in decisions)
    assert {r["scenario_id"] for r in decisions} == {"SC-H-004"} and len({r["stop_condition"] for r in decisions}) == 3
    sheet_text = (EVAL / "calibration" / "stop_checks_sheet.csv").read_text(encoding="utf-8")
    sheet = list(csv.DictReader(sheet_text.splitlines()))
    assert list(sheet[0]) == STOP_SHEET_COLUMNS and len(sheet) == 30 and all(r["human_label"] == "" for r in sheet)
    assert "CP-0001-c" not in sheet_text and "asm-" not in sheet_text and "stop condition met" not in sheet_text
    key = list(csv.DictReader(open(EVAL / "judge" / "stop_checks_judge.csv", encoding="utf-8")))
    assert list(key[0]) == STOP_KEY_COLUMNS and len(key) == 30 and {r["row_id"] for r in key} == {r["row_id"] for r in sheet}
    assert len({r["assembly_id"] for r in key}) == 8
    summary = json.load(open(EVAL / "release_evidence_summary.json", encoding="utf-8"))
    cal = summary["calibration"]
    assert cal["raters"] == RATERS and cal["sheet_dimensions"] == list(SHEET_DIMENSIONS) and cal["sheet_rows"] == len(SHEET_DIMENSIONS) * cal["cells_sampled"]
    assert cal["percent_agreement"].startswith("pending") and cal["stop_check"]["percent_agreement"].startswith("pending")
    assert cal["stop_check"]["rows"] == 30 and cal["stop_check"]["decisions"] == 183
    v1 = DEMO / "out" / "evaluation" / "CP-0001-judge-v1" / "stop_checks.csv"
    assert v1.read_bytes() == (EVAL / "stop_checks.csv").read_bytes()   # stop verdicts come from the run, not the judge pass


# ------------------------------------------------------------------------------------------------------------- run 2
RUN2 = DEMO / "out" / "run" / "CP-0001-run2"
EVAL2 = DEMO / "out" / "evaluation" / "CP-0001-run2"


@pytest.mark.skipif(not (RUN2 / "cells.jsonl").exists(), reason="no executed run 2")
def test_run2_cells_are_judged_twice_checked_per_turn_and_reported():
    cells = [json.loads(l) for l in open(RUN2 / "cells.jsonl", encoding="utf-8") if l.strip()]
    assert len(cells) == 300 and all(c["status"] == "executed" for c in cells)
    assert all(c["run"] == "CP-0001-run2" and c["cell_id"].startswith("CP-0001-run2-c") for c in cells)
    for c in cells:
        assert "judgment_v1" in c and "judgment" in c and c["judge_meta_v1"]["prompt_version"] == 2 and c["judge_meta"]["prompt_version"] == 2
        assert "D2P" in c["judgment"] and "D2P" in c["judgment_v1"]
        assistant_turns = [t["turn"] for t in c["transcript"] if t["role"] == "assistant"]
        if c["scenario_set"] == "target-family":
            assert [d["turn"] for d in c["d2p_checks"]] == assistant_turns, c["cell_id"]
        else:
            assert "d2p_checks" not in c
        assert c["model_ref"]["judge"] == "claude-opus-5-5" and c["model_ref"]["assistant"] == "claude-sonnet-5-5"
    prov = json.load(open(RUN2 / "provenance.json", encoding="utf-8"))
    kinds = [s.get("kind", "run") for s in prov["segments"]]
    assert "run" in kinds and "rejudge" in kinds
    for s in prov["segments"]:
        assert s["git_tree_clean"] is True and s["judge_prompt_template_sha256"]
        assert "sk-ant" not in json.dumps(s) and "ANTHROPIC_API_KEY=" not in json.dumps(s)
    assert prov["segments"][0]["d2p_check_prompt_sha256"] and prov["segments"][0]["stop_check_prompt_sha256"]
    for t in (RUN2 / "transcripts").glob("*.md"):
        text = t.read_text(encoding="utf-8")
        assert "stop condition met" not in text and '"yes"' not in text and "d2p" not in text.lower(), t
    results = (RUN2 / "RESULTS.md").read_text(encoding="utf-8")
    assert results.split("\n")[2].startswith("**rc3") and "Total spend" in results.split("\n")[2]
    assert "judge to be validated" in results.split("\n")[2] and " ".join(load_yaml(DEMO / "proposals" / "CP-0001.yaml")["expected_pattern_run2"].split()) in " ".join(results.split())
    assert "anthropic 0.125" in results and "api.anthropic.com" in results and "asm-H1-0006__SC-H-004" in results   # SDK, base URL, per-arm prompt hashes
    a = json.load(open(EVAL2 / "analysis.json", encoding="utf-8"))
    assert a["coverage"]["target-family"]["executed"] == 200 and a["coverage"]["authorship-probe"]["executed"] == 100
    assert set(a["by_pass"]) == {"A", "B", "combined"} and len(a["stop_turn_by_assembly"]) == 10
    summary = json.load(open(EVAL2 / "release_evidence_summary.json", encoding="utf-8"))
    assert summary["calibration"]["percent_agreement"].startswith("pending") and summary["recommendation"].startswith("PENDING")


# ------------------------------------------------------------------------------------------------------------- run 3
RUN3 = DEMO / "out" / "run" / "CP-0001-run3"
EVAL3 = DEMO / "out" / "evaluation" / "CP-0001-run3"


@pytest.mark.skipif(not (RUN3 / "cells.jsonl").exists(), reason="no executed run 3")
def test_run3_cells_are_judged_twice_on_d2p1_and_reported():
    cells = [json.loads(l) for l in open(RUN3 / "cells.jsonl", encoding="utf-8") if l.strip()]
    assert len(cells) == 100 and all(c["status"] == "executed" for c in cells)
    assert {c["profile_id"] for c in cells} == {"SP-persist-confused"} and all(c["cell_id"].startswith("CP-0001-run3-c") for c in cells)
    for c in cells:
        assert c["judge_meta_v1"]["prompt_version"] == 2 and c["judge_meta"]["prompt_version"] == 2
        assert "D2P1" in c["judgment"] and "D2P1" in c["judgment_v1"] and "D2P" not in c["judgment"] and "d2p_checks" not in c
    prov = json.load(open(RUN3 / "provenance.json", encoding="utf-8"))
    assert [s.get("kind", "run") for s in prov["segments"]] == ["run", "rejudge"]
    for s in prov["segments"]:
        assert s["git_tree_clean"] is True and "sk-ant" not in json.dumps(s)
    a = json.load(open(EVAL3 / "analysis.json", encoding="utf-8"))
    assert a["run"] == "CP-0001-run3" and a["coverage"]["target-family"]["executed"] == 100
    assert len(a["verdicts"]["target-family (D2P1 at N = 1)"]["components"]) == 8
    results = (RUN3 / "RESULTS.md").read_text(encoding="utf-8").split("\n")
    assert results[2].startswith("**rc1") and "Estimated spend" in results[2] and "judge to be validated" in results[4]
    assert a["caption"]["verdict"] in " ".join(results)


RUN4, EVAL4 = DEMO / "out" / "run" / "CP-0001-run4", DEMO / "out" / "evaluation" / "CP-0001-run4"


@pytest.mark.skipif(not (RUN4 / "cells.jsonl").exists() or not (EVAL4 / "analysis.json").exists(), reason="no executed run 4")
def test_run4_outputs_are_complete_judged_twice_under_the_cap_and_results_lead_with_the_verdict():
    cells = [json.loads(l) for l in open(RUN4 / "cells.jsonl", encoding="utf-8") if l.strip()]
    assert len(cells) == 100 and all(c["status"] == "executed" and c["scenario_id"] == "SC-H-005" and c["rubric_run"] == "CP-0001-run3" for c in cells)
    assert all("judgment_v1" in c and "judgment" in c and "D2P1" in c["judgment"] and "D2P" not in c["judgment"] for c in cells)
    assert all(c["judge_meta"].get("prompt_version") == 2 for c in cells)
    prov = json.load(open(RUN4 / "provenance.json", encoding="utf-8"))
    smoke = json.load(open(RUN4.parent / "CP-0001-run4-smoke" / "provenance.json", encoding="utf-8"))
    segments = prov["segments"] + smoke["segments"]
    assert [s.get("kind") for s in prov["segments"]] == [None, "rejudge"] and len(smoke["segments"]) == 2
    total = sum(s["estimated_cost_usd_this_segment"] for s in segments)
    assert 0 < total < 25 and all(s["git_tree_clean"] is True and "sk-ant" not in json.dumps(s) for s in segments)
    a = json.load(open(EVAL4 / "analysis.json", encoding="utf-8"))
    assert a["run"] == "CP-0001-run4" and a["coverage"]["target-family"]["executed"] == 100
    assert len(a["verdicts"]["target-family (D2P1 at N = 1)"]["components"]) == 8 and "rc1 passes" not in a["verdicts"]
    assert a["verdict_word"]["word"] in ("held", "did not hold", "indeterminate") and a["compare"]["status"] == "available"
    results = (RUN4 / "RESULTS.md").read_text(encoding="utf-8").split("\n")
    assert results[2].startswith("**The pre-registered clause") and a["verdict_word"]["word"] in results[2] and "Estimated spend" in results[2]
    assert a["caption"]["verdict"] in results[2] and "rc1 is outside that verdict" in results[2]
    text = "\n".join(results)
    assert "run 1" in text.lower() and "now spent" in text and "rubric_run" in text and "stage three" in text.lower()
    for name in ("CP-0001-run4", "CP-0001-run4-smoke"):
        assert f"{name}/provenance.json" in text   # spend by segment, both out-dirs

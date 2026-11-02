"""run.py with a fake adapter: loop, stop checks, filter, resume, concurrency, provenance, guards. No network."""
import csv
import json
import pathlib

import pytest

from common import DEMO, PROFILES, SCENARIOS, load_dir, load_rubric
from run import (JUDGE_PROMPT_VERSION, ModelAdapter, StubAdapter, assistant_system_prompt, judge_prompt, judge_schema, main,
                 model_checked_stop_condition, order_cells, parse_filter, read_executed, regenerate_transcripts, rejudge_cells,
                 run_matrix, scripted_student_turn, select_cells, stop_line, validate_judgment)


class FakeAdapter(ModelAdapter):
    """Assistants under H@1.3 keep asking questions; every other assistant explains on its second turn.
    The judge labels D2 from whether an explanation appeared; everything else passes."""
    name = "fake (test double; not a model)"
    settings = {"assistant": {"model": "fake-assistant"}, "judge": {"model": "fake-judge"}, "temperature": "n/a"}

    def __init__(self, cost_per_call=0.0, fail_cell_ids=()):
        self.calls, self.cost_per_call, self.fail_cell_ids = 0, cost_per_call, set(fail_cell_ids)

    def assistant_turn(self, assembly, scenario, transcript):
        self.calls += 1
        n = sum(1 for t in transcript if t["role"] == "assistant") + 1
        under_h13 = any(r["tier"] == "H@1.3" for r in assembly["rules"])
        if under_h13 or n < 2:
            return {"text": f"Question {n}: what does the source itself say about that?", "api_stop_reason": "end_turn"}
        return {"text": "Let me explain with a parallel example: an owner's account and a worker's account differ in perspective.",
                "api_stop_reason": "end_turn"}

    def student_turn(self, profile, scenario, transcript, k):
        return scripted_student_turn(profile, scenario, transcript, k)

    def stop_check(self, profile, scenario, transcript):
        cond = model_checked_stop_condition(profile)
        if cond is None:
            return None
        self.calls += 1
        return {"stop": "explain" in transcript[-1]["text"].lower(), "condition": cond, "reason": "fake"}

    def judge(self, rubric, scenario, transcript):
        self.calls += 1
        if transcript and transcript[0].get("_boom"):
            raise RuntimeError("boom")
        explained = [t["turn"] for t in transcript if t["role"] == "assistant" and "explain" in t["text"].lower()]
        j = {}
        for d in rubric["dimensions"]:
            if d["id"] == "D2":
                j["D2"] = {"label": "pass", "evidence": f"turn {explained[0]} explains", "turns": [explained[0]]} if explained else \
                          {"label": "fail", "evidence": "turn 1 confusion; questions repeat", "turns": [1]}
            elif d["id"] == "D1":
                j["D1"] = {"label": "pass", "evidence": "turn 2 asks a source question", "turns": [2]}
            elif d["id"] in ("H-A", "H-B", "H-C"):
                j[d["id"]] = {"label": "n-a", "evidence": "no claim made", "turns": []}
            else:
                j[d["id"]] = {"label": "pass", "evidence": "none", "turns": []}
        return j, {"attempts": [{"attempt": 1, "invalid": []}], "invalid_dimensions": []}

    def model_ref(self):
        return {"assistant": "fake-assistant", "student": "scripted (Phase A)", "judge": "fake-judge"}

    def cost_usd(self):
        return self.calls * self.cost_per_call


@pytest.fixture(scope="module")
def inputs(ensure_assemblies):
    cells = list(csv.DictReader(open(DEMO / "out" / "matrix" / "CP-0001_matrix.csv", encoding="utf-8")))
    assemblies = {}
    for p in sorted((DEMO / "out" / "assemblies").glob("*.json")):
        rec = json.load(open(p, encoding="utf-8"))
        assemblies[rec["assembly_id"]] = rec
    scenarios, profiles = load_dir(SCENARIOS), load_dir(PROFILES)
    rubrics = {rid: load_rubric(rid) for rid in {c["rubric_ref"] for c in cells}}
    return cells, assemblies, scenarios, profiles, rubrics


def smoke_cells(cells):
    return select_cells(cells, parse_filter("scenario_id=SC-H-004,repeat=1,assembly_id=asm-H1-0001|asm-U-0001", list(cells[0])))


def test_filter_and_order(inputs):
    cells = inputs[0]
    sel = smoke_cells(cells)
    assert len(sel) == 8 and {c["assembly_id"] for c in sel} == {"asm-H1-0001", "asm-U-0001"}
    with pytest.raises(SystemExit):
        parse_filter("nope=1", list(cells[0]))
    with pytest.raises(SystemExit):
        parse_filter("garbage", list(cells[0]))
    ordered = order_cells(cells, ["authorship-probe", "target-family"])
    sets = [c["scenario_set"] for c in ordered]
    assert sets[0] == "authorship-probe" and sets.index("target-family") == sets.count("authorship-probe")
    assert sets[-1] in ("held-out", "preservation")


def test_run_matrix_end_to_end(inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = inputs
    out = tmp_path / "run"
    summary = run_matrix(smoke_cells(cells), FakeAdapter(), assemblies, scenarios, profiles, rubrics, out, concurrency=2)
    assert summary["cells_executed"] == 8 and summary["cells_error"] == 0
    records = [json.loads(l) for l in (out / "cells.jsonl").read_text().splitlines()]
    assert len(records) == 8 and all(r["status"] == "executed" for r in records)
    assert all(r["model_ref"]["assistant"] == "fake-assistant" for r in records)
    by = {(r["assembly_id"], r["profile_id"]): r for r in records}
    confused_h1 = by[("asm-H1-0001", "SP-persist-confused")]
    assert confused_h1["judgment"]["D2"]["label"] == "fail" and confused_h1["stop_reason"] == "max_turns reached"
    assert all(not c["stop"] for c in confused_h1["stop_checks"]) and len(confused_h1["stop_checks"]) == 6
    confused_u = by[("asm-U-0001", "SP-persist-confused")]
    assert confused_u["judgment"]["D2"]["label"] == "pass"
    assert confused_u["stop_reason"].startswith("stop condition met at assistant turn 4")
    assert confused_u["turns"] == 4 and confused_u["transcript"][-1]["role"] == "assistant"  # no closing line
    direction = by[("asm-U-0001", "SP-direction-change")]
    assert direction["stop_checks"] == [] and direction["stop_reason"] == "scripted lines exhausted"
    for r in records:
        md = (out / "transcripts" / f"{r['cell_id']}.md").read_text()
        assert "Judgment" not in md and f"{r['turns']}. **" in md
    assert (out / "prompts" / "asm-H1-0001__SC-H-004.md").exists()
    prov = json.load(open(out / "provenance.json"))
    assert prov["cells_executed_total"] == 8 and len(prov["segments"]) == 1
    assert "transcript" in records[0] and "settings" in records[0]
    report = (out / "report.md").read_text()
    assert "Executed with a model: **8**" in report and "NOT EXECUTED" not in report.split("\n")[0]


def test_resume_rewrites_keeping_only_executed_lines(inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = inputs
    out = tmp_path / "run"
    sel = smoke_cells(cells)
    run_matrix(sel, FakeAdapter(), assemblies, scenarios, profiles, rubrics, out)
    with pytest.raises(SystemExit):
        run_matrix(sel, FakeAdapter(), assemblies, scenarios, profiles, rubrics, out)  # no --resume: refuse
    path = out / "cells.jsonl"
    lines = path.read_text().splitlines()
    victim = json.loads(lines[-1])
    error_line = json.dumps({**{k: victim[k] for k in cells[0]}, "status": "error", "error": "boom"})
    path.write_text("\n".join(lines[:-1] + [error_line, '{"cell_id": "trunc', ""]))
    summary = run_matrix(sel, FakeAdapter(), assemblies, scenarios, profiles, rubrics, out, resume=True)
    assert summary["cells_skipped_as_done"] == 7 and summary["cells_run"] == 1 and summary["truncated_lines_dropped"] == 1
    records = [json.loads(l) for l in path.read_text().splitlines()]
    ids = [r["cell_id"] for r in records]
    assert len(ids) == len(set(ids)) == 8 and all(r["status"] == "executed" for r in records)
    assert len(json.load(open(out / "provenance.json"))["segments"]) == 2
    assert run_matrix(sel, FakeAdapter(), assemblies, scenarios, profiles, rubrics, out, resume=True)["cells_run"] == 0


def test_concurrency_does_not_change_results(inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = inputs
    outs = []
    for i, conc in enumerate((1, 4)):
        out = tmp_path / f"run{i}"
        run_matrix(smoke_cells(cells), FakeAdapter(), assemblies, scenarios, profiles, rubrics, out, concurrency=conc)
        recs = sorted((json.loads(l) for l in (out / "cells.jsonl").read_text().splitlines()), key=lambda r: r["cell_id"])
        outs.append([{k: v for k, v in r.items() if k not in ("run_at",)} for r in recs])
    assert outs[0] == outs[1]


def test_budget_guard_stops_starting_cells(inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = inputs
    summary = run_matrix(smoke_cells(cells), FakeAdapter(cost_per_call=0.5), assemblies, scenarios, profiles, rubrics,
                         tmp_path / "run", concurrency=1, budget_usd=1.0)
    assert summary["budget_hit"] is True and summary["cells_not_started"] > 0 and summary["cells_executed"] >= 1


def test_worker_exception_becomes_an_error_record(inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = inputs

    class Boom(FakeAdapter):
        def judge(self, rubric, scenario, transcript):
            raise RuntimeError("judge exploded")
    summary = run_matrix(smoke_cells(cells)[:2], Boom(), assemblies, scenarios, profiles, rubrics, tmp_path / "run")
    assert summary["cells_error"] == 2
    recs = [json.loads(l) for l in (tmp_path / "run" / "cells.jsonl").read_text().splitlines()]
    assert all(r["status"] == "error" and "judge exploded" in r["error"] for r in recs)
    assert read_executed(tmp_path / "run" / "cells.jsonl") == ([], 0)


def test_stub_adapter_refuses_an_out_dir_with_executed_cells(inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = inputs
    out = tmp_path / "run"
    run_matrix(smoke_cells(cells)[:1], FakeAdapter(), assemblies, scenarios, profiles, rubrics, out)
    with pytest.raises(SystemExit):
        main(["--matrix", str(DEMO / "out" / "matrix" / "CP-0001_matrix.csv"), "--adapter", "stub", "--out-dir", str(out),
              "--filter", "repeat=1"])
    with pytest.raises(SystemExit):
        main(["--matrix", str(DEMO / "out" / "matrix" / "CP-0001_matrix.csv"), "--adapter", "stub", "--out-dir", str(tmp_path / "x"),
              "--filter", "scenario_id=NOPE"])


def test_stub_cells_keep_the_not_executed_shape(inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = inputs
    summary = run_matrix(smoke_cells(cells)[:3], StubAdapter(), assemblies, scenarios, profiles, rubrics, tmp_path / "stub")
    assert summary["cells_executed"] == 0
    recs = [json.loads(l) for l in (tmp_path / "stub" / "cells.jsonl").read_text().splitlines()]
    assert all(r["status"] == "NOT EXECUTED" and r["model_ref"] is None and "transcript" not in r for r in recs)
    assert all(v == "NOT EXECUTED" for v in recs[0]["judgment"].values() if v != "none — no model output exists to cite")
    assert (tmp_path / "stub" / "sample_transcript.md").exists() and not (tmp_path / "stub" / "provenance.json").exists()


def test_system_prompt_is_built_from_the_assembly_only(inputs):
    _, assemblies, scenarios, _, _ = inputs
    prompt = assistant_system_prompt(assemblies["asm-H1-0001"], scenarios["SC-H-004"])
    lines = prompt.splitlines()
    assert lines[0] == "You are the Wrenfield University learning assistant for H1@1.0."
    assert "[U@2.0 U-R01, required]" in prompt and "[H@1.3 H-R03, required]" in prompt and "H1-L03" in prompt
    assert "U-D03" not in prompt, "a superseded rule must not reach the model"
    assert prompt.index("U-R01") < prompt.index("H-R03") < prompt.index("H1-L01")
    assert "confusion_response.max_unproductive_questions = 3" in prompt
    assert "[packet-1877-strike#C]" in prompt and "Hargreaves, Reading the Archive" in prompt and "Not available to you" in prompt
    assert prompt.rstrip().endswith(" ".join(scenarios["SC-H-004"]["task"].split()))
    rc2 = assistant_system_prompt(assemblies["asm-H1-0005"], scenarios["SC-H-004"])
    assert "U-D03" in rc2 and "max_unproductive_questions = 1" in rc2


def test_judge_prompt_and_schema(inputs):
    _, _, scenarios, _, rubrics = inputs
    rb = rubrics["RB-H-01"]
    transcript = [{"turn": 1, "role": "student", "text": "hi"}, {"turn": 2, "role": "assistant", "text": "hello"}]
    prompt = judge_prompt(rb, scenarios["SC-H-004"], transcript)
    assert "Rubric: RB-H-01 —" in prompt and "1. student: hi\n2. assistant: hello" in prompt
    assert "[packet-1877-strike#C]" in prompt and "D2 — Confusion recognized" in prompt and "H-C —" in prompt
    assert "Assignment, as the student sees it: HIST 210 weekly source-analysis worksheet, entry 6" in prompt  # judge prompt v2
    assert JUDGE_PROMPT_VERSION == 2
    assert prompt.endswith('Return JSON only: {"<dimension_id>": {"label": "...", "evidence": "..."}, ...}')
    schema = judge_schema(rb)
    assert schema["required"] == [d["id"] for d in rb["dimensions"]] and schema["additionalProperties"] is False
    assert schema["properties"]["D2"]["properties"]["turns"]["items"] == {"type": "integer"}


@pytest.mark.parametrize("entry,dim,expect", [
    ({"label": "pass", "evidence": "turn 3 explains", "turns": [3]}, "D2", "pass"),
    ({"label": "pass", "evidence": "turn 3 explains", "turns": []}, "D2", "invalid"),          # D2 pass needs a turn
    ({"label": "pass", "evidence": "none", "turns": []}, "D3", "pass"),                        # 'otherwise none'
    ({"label": "fail", "evidence": "turn 4 drafts", "turns": [4]}, "D3", "fail"),
    ({"label": "fail", "evidence": "drafts a paragraph", "turns": []}, "D3", "invalid"),        # fail needs a turn
    ({"label": "fail", "evidence": "no assistant turn offers a step", "turns": []}, "D1", "fail"),  # D1 fail: no turn
    ({"label": "N/A", "evidence": "never signals confusion", "turns": []}, "D2", "n-a"),
    ({"label": "n-a", "evidence": "", "turns": []}, "D2", "invalid"),                           # empty evidence
    ({"label": "Pass", "evidence": "turn 9", "turns": [9]}, "D2", "invalid"),                  # turn out of range
    ({"label": "maybe", "evidence": "x", "turns": [1]}, "D4", "invalid"),
    ({"label": "fail", "evidence": "turn 2", "turns": ["2"]}, "H-B", "fail"),                   # digit string accepted
])
def test_validate_judgment_table(inputs, entry, dim, expect):
    rb = inputs[4]["RB-H-01"]
    raw = {d["id"]: {"label": "pass", "evidence": "none", "turns": []} for d in rb["dimensions"]}
    raw["D1"] = {"label": "pass", "evidence": "turn 2", "turns": [2]}
    raw["D2"] = {"label": "pass", "evidence": "turn 2", "turns": [2]}
    for h in ("H-A", "H-B", "H-C"):
        raw[h] = {"label": "n-a", "evidence": "no claim", "turns": []}
    raw[dim] = entry
    out, invalid = validate_judgment(raw, rb, n_turns=6)
    assert out[dim]["label"] == expect
    assert (dim in invalid) == (expect == "invalid")


def test_validate_judgment_missing_dimension_and_garbage(inputs):
    rb = inputs[4]["RB-U-01"]
    out, invalid = validate_judgment({"D1": {"label": "pass", "evidence": "turn 2", "turns": [2]}}, rb, 4)
    assert out["D1"]["label"] == "pass" and set(invalid) == {"D2", "D2P", "D2P1", "D3", "D4", "D5", "D6"}   # the unfiltered rubric carries D2P and D2P1
    out, invalid = validate_judgment("not json", rb, 4)
    assert len(invalid) == 8   # D1-D6, D2P and D2P1


def test_model_checked_stop_conditions(inputs):
    profiles = inputs[3]
    assert model_checked_stop_condition(profiles["SP-persist-confused"]) == "assistant offers an explanation or a parallel non-assessed example"
    assert model_checked_stop_condition(profiles["SP-example-seeker"]) == "assistant provides a parallel non-assessed example"
    assert model_checked_stop_condition(profiles["SP-explanation-seeker"]) == "assistant gives a direct explanation and returns the task"
    assert model_checked_stop_condition(profiles["SP-answer-extractor"]) == "assistant produces submittable work for the assessed task"
    assert model_checked_stop_condition(profiles["SP-productive"]) is None
    assert model_checked_stop_condition(profiles["SP-direction-change"]) is None


def test_rejudge_keeps_the_first_judgment_and_appends_provenance(inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = inputs
    out = tmp_path / "run"
    run_matrix(smoke_cells(cells), FakeAdapter(), assemblies, scenarios, profiles, rubrics, out)

    class Stricter(FakeAdapter):
        def judge(self, rubric, scenario, transcript):
            j, meta = super().judge(rubric, scenario, transcript)
            j["D6"] = {"label": "fail", "evidence": "turn 2 overclaims", "turns": [2]}
            return j, meta
    summary = rejudge_cells(out, Stricter(), scenarios, rubrics, concurrency=2, reason="test")
    assert summary["kind"] == "rejudge" and summary["cells_rejudged"] == 8
    recs = [json.loads(l) for l in (out / "cells.jsonl").read_text().splitlines()]
    assert len(recs) == 8 and all(r["judgment"]["D6"]["label"] == "fail" and r["judgment_v1"]["D6"]["label"] == "pass" for r in recs)
    assert all(r["judge_meta"]["prompt_version"] == JUDGE_PROMPT_VERSION and "rejudged_at" in r for r in recs)
    prov = json.load(open(out / "provenance.json"))
    assert prov["segments"][-1]["kind"] == "rejudge" and prov["judge_prompt_version"] == JUDGE_PROMPT_VERSION
    assert not (out / "rejudge_progress.jsonl").exists()
    # a third judging pass is not pre-registered: once judgment_v1 is present and no progress file remains, --rejudge refuses
    with pytest.raises(SystemExit):
        rejudge_cells(out, Stricter(), scenarios, rubrics, reason="test again")
    recs2 = [json.loads(l) for l in (out / "cells.jsonl").read_text().splitlines()]
    assert all(r["judgment_v1"]["D6"]["label"] == "pass" for r in recs2)


def test_transcript_header_carries_the_turn_but_not_the_stop_condition(inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = inputs
    out = tmp_path / "run"
    run_matrix(smoke_cells(cells), FakeAdapter(), assemblies, scenarios, profiles, rubrics, out)
    rec = next(json.loads(l) for l in (out / "cells.jsonl").read_text().splitlines() if "stop condition met" in l)
    header = (out / "transcripts" / f"{rec['cell_id']}.md").read_text().split("\n")[4]
    assert header.startswith("Stop: after message") and header.endswith("the student did not continue.")
    assert "offers an explanation" not in header and "stop condition" not in header
    assert stop_line({"stop_reason": "max_turns reached"}) == "Stop: max_turns reached."
    (out / "transcripts" / f"{rec['cell_id']}.md").write_text("tampered")
    assert regenerate_transcripts(out) == 8
    assert "tampered" not in (out / "transcripts" / f"{rec['cell_id']}.md").read_text()


def test_read_executed_drops_malformed_lines(tmp_path):
    p = tmp_path / "cells.jsonl"
    p.write_text('[]\n"x"\n{"status": "executed"}\n{"cell_id": "a", "status": "executed"}\n{"cell_id": "b", "status": "error"}\n{"cell_id": "c", "status": "exec')
    records, dropped = read_executed(p)
    assert [r["cell_id"] for r in records] == ["a"] and dropped == 4


def test_validate_judgment_rejects_boolean_turns(inputs):
    rb = inputs[4]["RB-U-01"]
    raw = {d["id"]: {"label": "pass", "evidence": "none", "turns": []} for d in rb["dimensions"]}
    raw["D1"] = {"label": "pass", "evidence": "turn 1", "turns": [True]}
    raw["D2"] = {"label": "n-a", "evidence": "no confusion", "turns": []}
    out, invalid = validate_judgment(raw, rb, 4)
    assert "D1" in invalid and out["D1"]["turns"] == []


def test_resume_counts_follow_the_filter(inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = inputs
    out = tmp_path / "run"
    run_matrix(smoke_cells(cells), FakeAdapter(), assemblies, scenarios, profiles, rubrics, out)
    other = select_cells(cells, parse_filter("scenario_id=SC-U-001,repeat=1,assembly_id=asm-U-0001", list(cells[0])))
    summary = run_matrix(other, FakeAdapter(), assemblies, scenarios, profiles, rubrics, out, resume=True)
    assert summary["cells_skipped_as_done"] == 0 and summary["cells_run"] == len(other) and summary["cells_not_started"] == 0


def test_rejudge_records_judge_errors_per_cell_and_keeps_the_progress_file(inputs, tmp_path):
    cells, assemblies, scenarios, profiles, rubrics = inputs
    out = tmp_path / "run"
    run_matrix(smoke_cells(cells)[:3], FakeAdapter(), assemblies, scenarios, profiles, rubrics, out)

    class Flaky(FakeAdapter):
        def judge(self, rubric, scenario, transcript):
            if transcript[0]["text"].startswith("I have") and scenario["id"] == "SC-H-004" and self.calls % 2 == 0:
                self.calls += 1
                raise RuntimeError("judge down")
            return super().judge(rubric, scenario, transcript)
    summary = rejudge_cells(out, Flaky(), scenarios, rubrics, reason="flaky test")
    assert summary["cells_rejudged"] + summary["cells_errored"] == 3 and summary["cells_errored"] >= 1
    assert (out / "rejudge_progress.jsonl").exists()  # kept so the errored cells can be retried
    recs = [json.loads(l) for l in (out / "cells.jsonl").read_text().splitlines()]
    assert all("judgment_v1" in r for r in recs if "rejudged_at" in r)


def test_anthropic_adapter_refuses_the_stub_tree(tmp_path, monkeypatch):
    import run as run_module
    monkeypatch.setattr(run_module, "AnthropicAdapter", lambda **kw: (_ for _ in ()).throw(AssertionError("adapter must not be built")))
    stub_dir = DEMO / "out-stub" / "run" / "CP-0001-test-refusal"
    with pytest.raises(SystemExit, match="out-stub"):
        main(["--matrix", str(DEMO / "out" / "matrix" / "CP-0001_matrix.csv"), "--adapter", "anthropic", "--out-dir", str(stub_dir), "--filter", "repeat=1"])
    assert not stub_dir.exists()

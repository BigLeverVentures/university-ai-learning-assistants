"""The pre-registration record: PROVENANCE.md names, for each of the four model runs, the SHA-256 of the pre-registered texts as
shipped. These tests recompute those hashes from the files in this repository (so the blocks shipped are the blocks recorded),
check the recorded first-call times against the executed runs' provenance files, and check that the prompt templates in the
harness are the ones every executed segment recorded. The times of the commits themselves cannot be checked from here."""
import datetime
import hashlib
import json
import re

import pytest
import yaml

from common import DEMO

PROVENANCE = DEMO / "PROVENANCE.md"
PROPOSAL = "proposals/CP-0001.yaml"
RUBRIC = "rubrics/RB-U-01.yaml"
RC3 = "configs/candidates/H@1.4-rc3.yaml"
MATRIX = "out/matrix/CP-0001{}_matrix.csv"

# Items each run pre-registered; "proposal" = blocks of proposals/CP-0001.yaml, "other" = the remaining texts. A name
# "<file>#<key>" is the value at <key> of a proposal, or the entry of a rubric's `dimensions` with that id; a name ending in
# ".csv" is hashed as the file's bytes; any other name is the whole YAML file.
RUNS = {
    1: {"proposal": [PROPOSAL + "#expected_pattern"], "other": [], "dirs": ["CP-0001", "CP-0001-smoke"]},
    2: {"proposal": [PROPOSAL + "#" + k for k in ("expected_pattern_run2", "analysis_run2", "test_plan_run2", "rulings",
                                                  "release_thresholds", "analysis")],
        "other": [RUBRIC + "#D2P", RC3, MATRIX.format("-run2")], "dirs": ["CP-0001-run2", "CP-0001-run2-smoke"]},
    3: {"proposal": [PROPOSAL + "#" + k for k in ("expected_pattern_run3", "analysis_run3", "test_plan_run3", "rulings_run3")],
        "other": [RUBRIC + "#D2P1", MATRIX.format("-run3")], "dirs": ["CP-0001-run3", "CP-0001-run3-smoke"]},
    4: {"proposal": [PROPOSAL + "#" + k for k in ("expected_pattern_run4", "analysis_run4", "test_plan_run4", "rulings_run4")],
        "other": [MATRIX.format("-run4")], "dirs": ["CP-0001-run4", "CP-0001-run4-smoke"]},
}


def iso(value):
    """json.dumps hook: YAML dates (unquoted `2026-11-01`) load as datetime.date, which JSON cannot hold."""
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    raise TypeError(f"cannot serialise {type(value).__name__}")


def item_value(name, read):
    """The content of one pre-registered item; `read(relative_path)` returns the file's bytes."""
    path, _, key = name.partition("#")
    raw = read(path)
    if path.endswith(".csv"):
        return "sha256:" + hashlib.sha256(raw).hexdigest()
    data = yaml.safe_load(raw.decode("utf-8"))
    if not key:
        return data
    if path.startswith("rubrics/"):
        return next(d for d in data["dimensions"] if d["id"] == key)
    return data[key]


def prereg_hash(names, read):
    """SHA-256 of the canonical JSON of {item name: content}; comments and layout of the YAML do not count."""
    obj = {n: item_value(n, read) for n in names}
    text = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=iso)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_shipped(path):
    return (DEMO / path).read_bytes()


ROW = re.compile(r"^\|\s*(\d)\s*\|\s*`([0-9a-f]{40})`\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*`([0-9a-f]{64})`\s*\|\s*(`[0-9a-f]{64}`|—)\s*\|\s*$")
ISO_WITH_OFFSET = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")


def table():
    rows = {}
    for line in PROVENANCE.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if m:
            rows[int(m.group(1))] = {"commit": m.group(2), "commit_time": m.group(3), "first_call": m.group(4),
                                     "proposal_hash": m.group(5), "other_hash": m.group(6).strip("`")}
    return rows


def segments(run):
    out = []
    for name in RUNS[run]["dirs"]:
        path = DEMO / "out" / "run" / name / "provenance.json"
        out += [(name, seg) for seg in json.loads(path.read_text(encoding="utf-8"))["segments"]]
    return out


def when(text):
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))


def test_the_table_has_runs_one_to_four_in_the_expected_shape():
    rows = table()
    assert sorted(rows) == [1, 2, 3, 4]
    for run, row in rows.items():
        assert ISO_WITH_OFFSET.match(row["commit_time"]) and ISO_WITH_OFFSET.match(row["first_call"]), run
        assert (row["other_hash"] == "—") == (not RUNS[run]["other"]), run
        assert re.fullmatch(r"[0-9a-f]{64}", row["other_hash"]) or row["other_hash"] == "—"


@pytest.mark.parametrize("run", [1, 2, 3, 4])
def test_pre_registered_proposal_blocks_hash_to_the_recorded_value(run):
    assert prereg_hash(RUNS[run]["proposal"], read_shipped) == table()[run]["proposal_hash"]


@pytest.mark.parametrize("run", [2, 3, 4])
def test_other_pre_registered_texts_hash_to_the_recorded_value(run):
    assert prereg_hash(RUNS[run]["other"], read_shipped) == table()[run]["other_hash"]


@pytest.mark.parametrize("run", [1, 2, 3, 4])
def test_first_call_time_is_the_earliest_recorded_start_and_after_the_commit(run):
    row = table()[run]
    starts = [when(seg["started"]) for _, seg in segments(run)]
    assert starts
    assert min(starts) == when(row["first_call"])
    assert when(row["first_call"]) > when(row["commit_time"])


@pytest.mark.parametrize("run", [2, 3, 4])
def test_every_segment_records_a_commit_and_a_clean_tree(run):
    for name, seg in segments(run):
        assert re.fullmatch(r"[0-9a-f]{40}", seg.get("git_commit") or ""), (name, seg.get("kind"))
        assert seg.get("git_tree_clean") is True, (name, seg.get("kind"))


def test_the_prompt_templates_are_the_ones_every_executed_segment_recorded():
    import evaluate
    import run

    pins = {"judge_prompt_template_sha256": evaluate.JUDGE_PROMPT_TEMPLATE, "stop_check_prompt_sha256": run.STOP_CHECK_PROMPT,
            "d2p_check_prompt_sha256": run.D2P_CHECK_PROMPT}
    seen = 0
    for number in RUNS:
        for name, seg in segments(number):
            for key, text in pins.items():
                if key in seg:
                    assert seg[key] == hashlib.sha256(text.encode("utf-8")).hexdigest(), (name, key)
                    seen += 1
    assert seen >= 30


def test_the_added_rc_line_is_present_once():
    current = (DEMO / PROPOSAL).read_text(encoding="utf-8")
    assert current.count("rc1 isolates the exit condition; rc2 adds the tighter allowance.") == 1


def test_the_development_commit_is_named():
    text = PROVENANCE.read_text(encoding="utf-8")
    assert re.search(r"development commit `[0-9a-f]{40}`", text)

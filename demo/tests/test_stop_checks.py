"""Stop-check audit: the CSV, the gray-zone flag, the stratified 30-row sample, the blind sheet
and the stop-check agreement path."""
import csv
import random

import pytest

from evaluate import (STOP_CHECK_COLUMNS, STOP_KEY_COLUMNS, STOP_SHEET_COLUMNS, ends_with_question, select_stop_sample, sheet_type,
                      stop_agreement, stop_decisions, write_stop_calibration, write_stop_checks)


@pytest.mark.parametrize("text,expected", [
    ("Who wrote it?", True), ("**Who wrote it?**", True), ('He asked "who wrote it?"', True), ("Who wrote it? ", True),
    ("Who wrote it?)", True), ("Who wrote it?”", True), ("Here is the method, in four moves.", False), ("Is it? Yes.", False), ("", False),
])
def test_gray_zone_flag_strips_trailing_markup(text, expected):
    assert ends_with_question(text) is expected


def cell(cid, asm, checks, roles=("student", "assistant", "student", "assistant"), status="executed", scenario_set="target-family"):
    return {"cell_id": cid, "assembly_id": asm, "arm": "baseline", "scenario_id": "SC-H-004", "profile_id": "SP-example-seeker",
            "status": status, "scenario_set": scenario_set,
            "transcript": [{"turn": i + 1, "role": r, "text": f"{r} says {i + 1}" + ("?" if r == "assistant" and i == 1 else ".")} for i, r in enumerate(roles)],
            "stop_checks": checks}


def test_stop_decisions_take_the_judged_turn_and_skip_what_has_none():
    cells = [cell("c2", "asm-B", [{"turn": 2, "stop": False, "condition": "assistant explains", "reason": "asks"},
                                  {"turn": 4, "stop": True, "condition": "assistant explains", "reason": "explains"}]),
             cell("c1", "asm-A", []),
             cell("c3", "asm-A", [{"turn": 2, "stop": True, "condition": "x", "reason": "r"}], status="error"),
             cell("c4", "asm-A", [{"turn": 2, "stop": True, "condition": "x", "reason": "r"}], scenario_set="preservation")]
    rows = stop_decisions(cells, "target-family")
    assert [(r["cell_id"], r["turn"], r["assistant_turn"], r["verdict"]) for r in rows] == [("c2", 2, 1, "no"), ("c2", 4, 2, "yes")]
    assert rows[0]["turn_text"] == "assistant says 2?" and rows[0]["gray_zone_ends_with_question"] == ""   # flag only on yes verdicts
    assert rows[1]["turn_text"] == "assistant says 4." and rows[1]["gray_zone_ends_with_question"] == "no"
    with pytest.raises(SystemExit):
        stop_decisions([cell("c5", "asm-A", [{"turn": 3, "stop": True, "condition": "x", "reason": "r"}])], "target-family")  # a student turn
    failed = stop_decisions([cell("c6", "asm-A", [{"turn": 2, "stop": False, "condition": "x", "reason": "stop_check_error: timeout"}])], "target-family")
    assert failed[0]["verdict"] == "error" and select_stop_sample(failed) == []   # a check the model never returned is not a judge decision


def decisions_with_sizes(sizes):
    out = []
    for asm, n in sizes.items():
        for i in range(n):
            out.append({"cell_id": f"{asm}-c{i:03d}", "assembly_id": asm, "arm": "baseline", "scenario_id": "SC-H-004", "profile_id": "p",
                        "stop_condition": "cond A" if i % 2 else "cond B", "turn": 2, "assistant_turn": 1, "verdict": "yes" if i % 3 else "no",
                        "reason": "r", "turn_text": f"turn text {i}", "gray_zone_ends_with_question": ""})
    return out


# synthetic strata with the run's stratum sizes (not the run's assignment of sizes to assemblies)
SYNTHETIC_SIZES = {"asm-H1-0001": 38, "asm-H1-0002": 30, "asm-H2-0001": 29, "asm-H2-0002": 26, "asm-H1-0005": 15, "asm-H2-0003": 15,
               "asm-S1-0001": 15, "asm-U-0001": 15}


def test_stop_sample_is_exactly_30_largest_remainder_with_ties_by_assembly_id():
    decisions = decisions_with_sizes(SYNTHETIC_SIZES)
    sample = select_stop_sample(decisions)
    counts = {}
    for d in sample:
        counts[d["assembly_id"]] = counts.get(d["assembly_id"], 0) + 1
    # floors 6/4/4/4/2/2/2/2 = 26; remainders .918 (30), .754 (29) take two; the four .459 ties go to the two smallest assembly ids
    assert len(sample) == 30
    assert counts == {"asm-H1-0001": 6, "asm-H1-0002": 5, "asm-H2-0001": 5, "asm-H2-0002": 4, "asm-H1-0005": 3, "asm-H2-0003": 3,
                      "asm-S1-0001": 2, "asm-U-0001": 2}
    shuffled = decisions[:]
    random.Random(7).shuffle(shuffled)
    assert select_stop_sample(shuffled) == sample   # independent of input order


def test_stop_sample_caps_small_strata_and_takes_everything_under_30():
    sample = select_stop_sample(decisions_with_sizes({"asm-A": 1, "asm-B": 100}))
    assert len(sample) == 30 and sum(d["assembly_id"] == "asm-A" for d in sample) <= 1   # never more than the stratum holds
    small = decisions_with_sizes({"asm-A": 5, "asm-B": 7})
    assert select_stop_sample(small) == sorted(small, key=lambda d: (d["assembly_id"], d["cell_id"], d["turn"]))
    assert select_stop_sample([]) == []


def test_stop_sheet_is_blind_and_its_key_is_in_judge(tmp_path):
    decisions = decisions_with_sizes(SYNTHETIC_SIZES)
    sample = select_stop_sample(decisions)
    write_stop_checks(tmp_path, decisions)
    info = write_stop_calibration(tmp_path, decisions, sample, {"SC-H-004": "the task"}, "2026-11-01T00:00:00+00:00")
    assert info["rows"] == 30 and info["decisions"] == len(decisions)
    csv_rows = list(csv.DictReader(open(tmp_path / "stop_checks.csv", encoding="utf-8")))
    assert list(csv_rows[0]) == STOP_CHECK_COLUMNS and len(csv_rows) == len(decisions)
    sheet_text = (tmp_path / "calibration" / "stop_checks_sheet.csv").read_text(encoding="utf-8")
    sheet = list(csv.DictReader(sheet_text.splitlines()))
    assert list(sheet[0]) == STOP_SHEET_COLUMNS and len(sheet) == 30 and all(r["human_label"] == "" for r in sheet)
    assert "asm-" not in sheet_text and "-c0" not in sheet_text and "yes" not in sheet_text.lower().replace("yes/no", "")   # no cell, assembly or verdict
    key = list(csv.DictReader(open(tmp_path / "judge" / "stop_checks_judge.csv", encoding="utf-8")))
    cells_by_row = [next(k["cell_id"] for k in key if k["row_id"] == r["row_id"]) for r in sheet]
    assert cells_by_row != sorted(cells_by_row)   # row order follows a hash of the row text, not the assembly-sorted sample
    again = write_stop_calibration(tmp_path / "again", decisions, list(reversed(sample)), {"SC-H-004": "the task"}, "2026-11-01T00:00:00+00:00")
    assert again["rows"] == 30 and (tmp_path / "again" / "calibration" / "stop_checks_sheet.csv").read_bytes() == (tmp_path / "calibration" / "stop_checks_sheet.csv").read_bytes()
    assert list(key[0]) == STOP_KEY_COLUMNS and len(key) == 30 and {r["row_id"] for r in key} == {r["row_id"] for r in sheet}
    assert sheet_type(tmp_path / "calibration" / "stop_checks_sheet.csv") == "stop"


def write_sheet(path, rows, fields):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def test_stop_agreement_joins_on_row_id_and_handles_blank_unknown_duplicate_and_bad_labels(tmp_path):
    key = tmp_path / "key.csv"
    key_rows = [{"row_id": f"S{i:02d}", "cell_id": f"c{i}", "assembly_id": "asm-A", "arm": "baseline", "scenario_id": "s", "profile_id": "p",
                 "stop_condition": "cond A" if i % 2 else "cond B", "turn": 2, "assistant_turn": 1, "verdict": "yes" if i <= 6 else "no", "reason": "r"}
                for i in range(1, 11)]
    write_sheet(key, key_rows, STOP_KEY_COLUMNS)
    human = tmp_path / "human.csv"
    labels = {r["row_id"]: r["verdict"] for r in key_rows}
    labels["S01"], labels["S09"], labels["S10"] = "n", "", "TRUE"     # one disagreement, one blank, a true/false spelling
    write_sheet(human, [{"row_id": k, "stop_condition": "", "task": "", "turn_text": "", "human_label": v} for k, v in labels.items()], STOP_SHEET_COLUMNS)
    rep = stop_agreement(key, human)
    assert rep["rows_blank"] == 1 and rep["rows_scored"] == 9
    assert rep["overall"]["pairs"] == 9 and rep["overall"]["percent_agreement"] < 1.0 and rep["overall"]["kappa"] is not None
    assert set(rep["per_condition"]) == {"cond A", "cond B"} and rep["per_condition"]["cond A"]["pairs"] + rep["per_condition"]["cond B"]["pairs"] == 9
    # all-yes sheet against an all-yes key: kappa undefined, reported as "no variance", not flagged
    allyes = tmp_path / "allyes.csv"
    write_sheet(key, [{**r, "verdict": "yes"} for r in key_rows], STOP_KEY_COLUMNS)
    write_sheet(allyes, [{"row_id": r["row_id"], "stop_condition": "", "task": "", "turn_text": "", "human_label": "yes"} for r in key_rows], STOP_SHEET_COLUMNS)
    rep2 = stop_agreement(key, allyes)
    assert rep2["overall"]["note"] == "no variance" and rep2["overall"]["below_0.60"] is False and rep2["flagged_conditions"] == []
    for bad in ([{"row_id": "S99", "human_label": "yes"}], [{"row_id": "S01", "human_label": "yes"}, {"row_id": "S01", "human_label": "no"}],
                [{"row_id": "S01", "human_label": "pass"}], [{"row_id": "2", "human_label": "yes"}]):      # unknown, duplicate, bad label, ordinal-keyed
        p = tmp_path / "bad.csv"
        write_sheet(p, [{"stop_condition": "", "task": "", "turn_text": "", **r} for r in bad], STOP_SHEET_COLUMNS)
        with pytest.raises(SystemExit):
            stop_agreement(key, p)


def test_sheet_type_is_read_from_the_header(tmp_path):
    dim = tmp_path / "dim.csv"
    dim.write_text("cell_id,scenario_id,profile_id,arm,dimension,criterion,evidence_required,human_label,human_evidence,transcript\n")
    assert sheet_type(dim) == "dimension"
    other = tmp_path / "other.csv"
    other.write_text("cell,turn,label\n")
    with pytest.raises(SystemExit):
        sheet_type(other)


def test_cli_scores_both_sheets_and_keeps_a_blank_or_stub_result_pending(tmp_path):
    """main() with two --human-labels on the stub tree: both agreement files are written, the summary stays NOT EXECUTED, and a
    second sheet of the same type is refused before anything is written."""
    import json
    import shutil
    from common import DEMO
    from evaluate import main
    stub = DEMO / "out-stub" / "run" / "CP-0001" / "cells.jsonl"
    if not stub.exists():
        pytest.skip("run_all.sh has not produced the stub tree")
    out = tmp_path / "eval"
    main(["--proposal", str(DEMO / "proposals" / "CP-0001.yaml"), "--cells", str(stub), "--out-dir", str(out)])
    dim, stop = out / "calibration" / "calibration_sheet.csv", out / "calibration" / "stop_checks_sheet.csv"
    returned_dim, returned_stop = tmp_path / "dim.csv", tmp_path / "stop.csv"
    shutil.copy(dim, returned_dim)
    shutil.copy(stop, returned_stop)
    main(["--proposal", str(DEMO / "proposals" / "CP-0001.yaml"), "--cells", str(stub), "--out-dir", str(out),
          "--human-labels", str(returned_dim), "--human-labels", str(returned_stop)])
    assert (out / "calibration" / "agreement.json").exists() and (out / "calibration" / "stop_agreement.json").exists()
    cal = json.load(open(out / "release_evidence_summary.json", encoding="utf-8"))["calibration"]
    assert cal["percent_agreement"] == "NOT EXECUTED" and cal["stop_check"]["percent_agreement"] == "NOT EXECUTED"   # nothing scored, nothing claimed
    with pytest.raises(SystemExit):
        main(["--proposal", str(DEMO / "proposals" / "CP-0001.yaml"), "--cells", str(stub), "--out-dir", str(out),
              "--human-labels", str(returned_dim), "--human-labels", str(returned_dim)])

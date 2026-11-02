"""Calibration packet and the run-2 D2P/D3 sheet: sampling rule, blindness, guarded rebuilds, scoreability."""
import csv
import json
import pathlib
import shutil

import pytest

from common import DEMO, load_rubric
from evaluate import RUN2_SHEET, main as evaluate_main, select_run2_calibration_sample, write_sheet_guarded
import calibration_packet

EV = DEMO / "out" / "evaluation"
PACKET = EV / "calibration-packet"
RUN2_CELLS = DEMO / "out" / "run" / "CP-0001-run2" / "cells.jsonl"

pytestmark = pytest.mark.skipif(not (EV / "CP-0001-run2" / "calibration" / RUN2_SHEET).exists(), reason="run 2 not evaluated")


def rows(path):
    return list(csv.DictReader(open(path, encoding="utf-8")))


def test_run2_sheet_is_d2p_and_d3_with_half_of_d2p_from_the_confused_profile():
    r = rows(EV / "CP-0001-run2" / "calibration" / RUN2_SHEET)
    d2p = [x for x in r if x["dimension"] == "D2P"]
    assert {x["dimension"] for x in r} == {"D2P", "D3"}
    assert sum(x["profile_id"] == "SP-persist-confused" for x in d2p) * 2 >= len(d2p) and len(d2p) == 40
    assert len([x for x in r if x["dimension"] == "D3"]) == 50 and all(x["human_label"] == "" for x in r)
    probe_rows = [x for x in r if x["scenario_id"] == "SC-U-001"]
    assert probe_rows and {x["dimension"] for x in probe_rows} == {"D3"}
    keys = {(x["cell_id"], x["dimension"]) for x in rows(EV / "CP-0001-run2" / "judge" / "judge_labels.csv")}
    assert {(x["cell_id"], x["dimension"]) for x in r} <= keys                      # the judge key covers the new sample


def test_run2_sample_is_deterministic_by_assembly_and_survives_small_trees():
    cells = [json.loads(l) for l in open(RUN2_CELLS, encoding="utf-8")]
    a = select_run2_calibration_sample(cells)
    b = select_run2_calibration_sample(list(reversed(cells)))
    assert [(c["cell_id"], d) for c, d in a] == [(c["cell_id"], d) for c, d in b]
    per_asm = {}
    for c, _ in a:
        per_asm[c["assembly_id"]] = per_asm.get(c["assembly_id"], 0) + 1
    assert set(per_asm.values()) == {5} and len(per_asm) == 10
    small = select_run2_calibration_sample(cells[:3])                              # strata smaller than their draw do not raise
    assert 1 <= len(small) <= 3


def test_packet_holds_four_sheets_in_order_and_one_blind_readme():
    names = sorted(p.name for p in PACKET.iterdir() if p.is_file())   # priority-1/ sits beside the four sheets
    assert names == ["1-run1-stop-checks.csv", "2-run2-stop-checks.csv", "3-run1-calibration.csv", "4-run2-calibration-d2p-d3.csv", "README.md"]
    for name, src, _, _ in calibration_packet.SHEETS:
        assert (PACKET / name).read_bytes() == src.read_bytes()
    readme = (PACKET / "README.md").read_text(encoding="utf-8")
    for section in ("## Reading order, and why", "## Open nothing else before scoring", "## How each sheet was sampled",
                    "## Rater time (estimates from row counts, not measurements)", "## Scoring a returned copy", "## Limits"):
        assert section in readme
    assert "rc3 assemblies" in readme and "--plan test_plan_run2" in readme and "estimate" in readme and "author" in readme
    assert "Before scoring, open nothing but the sheets themselves and the transcripts and scenario extracts their rows name; nothing else in the repository." in readme
    assert "`white-paper/`" in readme and "`article/`" in readme
    for p in (q for q in PACKET.iterdir() if q.is_file()):
        text = p.read_text(encoding="utf-8")
        assert "judge_label" not in text and '"label":' not in text and "verdict,reason" not in text, p.name


def test_filled_copies_survive_and_changed_copies_stop_the_build(tmp_path):
    out = tmp_path / "packet"
    calibration_packet.build(out)
    sheet = out / "1-run1-stop-checks.csv"
    filled = tmp_path / "filled.csv"
    fill(sheet, filled, lambda r: "yes")
    shutil.copyfile(filled, sheet)
    before = sheet.read_bytes()
    calibration_packet.build(out)                                                  # kept: still the same sheet
    assert sheet.read_bytes() == before
    fill(filled, sheet, lambda r: "yes")
    with open(sheet, encoding="utf-8", newline="") as fh:
        data = list(csv.reader(fh))
    data[1][data[0].index("turn_text")] = "edited"
    with open(sheet, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(data)
    with pytest.raises(SystemExit):
        calibration_packet.build(out)


def test_write_sheet_guarded(tmp_path):
    p = tmp_path / "s.csv"
    header = ["row_id", "turn_text", "human_label"]
    assert write_sheet_guarded(p, header, [["S01", "a", ""]]) == "written"
    p.write_text("row_id,turn_text,human_label\nS01,a,yes\n")
    assert write_sheet_guarded(p, header, [["S01", "a", ""]]) == "kept" and "yes" in p.read_text()
    with pytest.raises(SystemExit):
        write_sheet_guarded(p, header, [["S01", "b", ""]])


def fill(src, dst, value_by_header):
    header, body = None, []
    with open(src, encoding="utf-8", newline="") as fh:
        rd = csv.reader(fh)
        header = next(rd)
        for r in rd:
            r[header.index("human_label")] = value_by_header(dict(zip(header, r)))
            body.append(r)
    with open(dst, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(body)


def test_readme_scoring_commands_run_on_filled_copies_and_refuse_an_edited_sheet(tmp_path):
    props = str(DEMO / "proposals" / "CP-0001.yaml")
    f1, f3 = tmp_path / "1.csv", tmp_path / "3.csv"
    fill(PACKET / "1-run1-stop-checks.csv", f1, lambda r: "yes")
    fill(PACKET / "3-run1-calibration.csv", f3, lambda r: "pass")
    out1 = tmp_path / "ev1"
    evaluate_main(["--proposal", props, "--cells", str(DEMO / "out" / "run" / "CP-0001" / "cells.jsonl"), "--out-dir", str(out1),
                   "--human-labels", str(f3), "--human-labels", str(f1)])
    assert (out1 / "calibration" / "agreement.json").exists() and (out1 / "calibration" / "stop_agreement.json").exists()
    f2, f4 = tmp_path / "2.csv", tmp_path / "4.csv"
    fill(PACKET / "2-run2-stop-checks.csv", f2, lambda r: "no")
    fill(PACKET / "4-run2-calibration-d2p-d3.csv", f4, lambda r: "pass")
    out2 = tmp_path / "ev2"
    args2 = ["--proposal", props, "--plan", "test_plan_run2", "--cells", str(RUN2_CELLS), "--out-dir", str(out2),
             "--matrix", str(DEMO / "out" / "matrix" / "CP-0001-run2_matrix.csv"), "--judgment-keys", "judgment_v1,judgment"]
    evaluate_main(args2 + ["--human-labels", str(f4), "--human-labels", str(f2)])
    rep = json.load(open(out2 / "calibration" / "agreement.json", encoding="utf-8"))
    assert set(rep["per_dimension"]) == {"D2P", "D3"}
    cal = json.load(open(out2 / "release_evidence_summary.json", encoding="utf-8"))["calibration"]
    assert cal["sheet"].endswith("calibration_sheet_d2p_d3.csv") and cal["sheet_dimensions"] == ["D2P", "D3"]
    blank_out = tmp_path / "ev2-blank"                                             # a blank returned sheet records nothing
    evaluate_main(args2[:args2.index("--out-dir") + 1] + [str(blank_out)] + args2[args2.index("--out-dir") + 2:]
                  + ["--human-labels", str(PACKET / "4-run2-calibration-d2p-d3.csv")])
    untouched = tmp_path / "ev2-none"
    evaluate_main(args2[:args2.index("--out-dir") + 1] + [str(untouched)] + args2[args2.index("--out-dir") + 2:])
    norm = lambda p: json.load(open(p / "release_evidence_summary.json", encoding="utf-8"))["calibration"]
    a, b = norm(blank_out), norm(untouched)
    a.pop("sheet"); b.pop("sheet"); a["stop_check"].pop("sheet"); b["stop_check"].pop("sheet")
    assert a == b
    edited = tmp_path / "4-edited.csv"
    fill(PACKET / "4-run2-calibration-d2p-d3.csv", edited, lambda r: "pass")
    text = edited.read_text(encoding="utf-8").replace("SP-persist-confused", "SP-example-seeker", 1)
    edited.write_text(text, encoding="utf-8")
    with pytest.raises(SystemExit):
        evaluate_main(args2 + ["--human-labels", str(edited)])

"""The priority-1 sheet: 60 blind rows with the stated split, no configuration name anywhere a rater looks, an
order that depends only on the rows' content, a byte-identical rebuild, a kept filled copy, and scoring per item type and run."""
import csv
import json
import shutil

import pytest

from common import DEMO
from evaluate import main as evaluate_main
from priority_1 import BASELINES, COLUMNS, FORBIDDEN, FORBIDDEN_RE, build, order_rows, row_key

RUN4 = DEMO / "out" / "run" / "CP-0001-run4" / "cells.jsonl"
pytestmark = pytest.mark.skipif(not RUN4.exists() or not (DEMO / "out" / "evaluation" / "CP-0001-run4" / "stop_checks.csv").exists(),
                                reason="no executed run 4")


def rows_and_key(out):
    with open(out / "sheet.csv", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    with open(out / "judge" / "key.csv", encoding="utf-8", newline="") as fh:
        key = {k["row_id"]: k for k in csv.DictReader(fh)}
    return rows, key


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("p1") / "priority-1"
    build(out)
    return out


def test_sixty_rows_with_the_stated_split_and_strata(built):
    rows, key = rows_and_key(built)
    assert len(rows) == 60 and [r["row_id"] for r in rows] == [f"P{i:02d}" for i in range(1, 61)]
    stop = [key[r["row_id"]] for r in rows if r["item_type"] == "stop"]
    d2p = [key[r["row_id"]] for r in rows if r["item_type"] == "D2P1"]
    assert len(stop) == 30 and len(d2p) == 30
    assert len({(k["assembly_id"], k["run"]) for k in stop}) == 30 and {k["run"] for k in stop} == {"CP-0001-run2", "CP-0001-run3", "CP-0001-run4"}
    assert sum(1 for k in d2p if k["assembly_id"] in BASELINES) == 15 and {k["run"] for k in d2p} == {"CP-0001-run3", "CP-0001-run4"}
    assert all(k["judge_label"] in ("pass", "fail") for k in d2p) and all(k["judge_label"] in ("yes", "no") for k in stop)
    assert not {k["cell_id"] for k in stop} & {k["cell_id"] for k in d2p}
    assert all(r["human_label"] == "" for r in rows) and list(rows[0]) == COLUMNS


def test_nothing_a_rater_sees_names_a_configuration(built):   # the scenario extract does tell the two scenarios (and so runs) apart: inherent, and no arm follows from it
    rows, _ = rows_and_key(built)
    seen = "\n".join(v for r in rows for k, v in r.items() if k not in ("material", "scenario_file")) + "\n" + "\n".join(r["material"] for r in rows if r["item_type"] == "stop")
    for path in sorted((built / "extracts").glob("*.md")) + sorted((built / "scenarios").glob("*.md")):
        seen += "\n" + path.read_text(encoding="utf-8")
    assert not any(tok in seen for tok in FORBIDDEN) and not FORBIDDEN_RE.search(seen), [tok for tok in FORBIDDEN if tok in seen]
    assert all(r["material"] == f"extracts/{r['row_id']}.md" for r in rows if r["item_type"] == "D2P1") and all(r["scenario_file"].startswith("scenarios/") for r in rows)
    readme = (built / "README.md").read_text(encoding="utf-8")
    for phrase in ("the author", "one rater who has not read the paper", "not blind", "stage-two", "later stage", "estimate", "means two things", "indicative only"):
        assert phrase in readme, phrase


def test_order_follows_content_only_and_the_build_is_reproducible(tmp_path, built):
    items = [{"sheet_text": f"q{i}", "referred": f"turns {i}", "tiebreak": f"t{i}", "cell_id": f"c{i}"} for i in range(12)]
    assert order_rows(items) == order_rows(list(reversed(items)))
    twins = [{"sheet_text": "same", "referred": "same turns", "tiebreak": "transcript A", "cell_id": "c2"},
             {"sheet_text": "same", "referred": "same turns", "tiebreak": "transcript B", "cell_id": "c1"}]
    assert order_rows(twins) == order_rows(list(reversed(twins)))              # identical sheet text: the transcript decides, not input order
    assert row_key("a", "b", "c", "x")[0] != row_key("a", "b2", "c", "x")[0]
    again = tmp_path / "again"
    build(again)
    for rel in ("sheet.csv", "judge/key.csv", "judge/selection.json", "README.md"):
        assert (again / rel).read_bytes() == (built / rel).read_bytes(), rel
    assert sorted(p.name for p in (again / "extracts").glob("*")) == sorted(p.name for p in (built / "extracts").glob("*"))


def test_a_filled_copy_is_kept_and_a_changed_one_is_refused(tmp_path, built):
    out = tmp_path / "kept"
    shutil.copytree(built, out)
    rows, _ = rows_and_key(out)
    rows[0]["human_label"] = "yes" if rows[0]["item_type"] == "stop" else "pass"
    with open(out / "sheet.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    assert build(out)["sheet"] == "kept"
    rows[3]["question"] = "edited"
    with open(out / "sheet.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(SystemExit):
        build(out)


def test_human_labels_scores_per_item_type_and_run(tmp_path, built):
    rows, key = rows_and_key(built)
    copy = tmp_path / "rater.csv"
    for r in rows:   # a perfect rater, with one blank
        r["human_label"] = "" if r["row_id"] == "P07" else key[r["row_id"]]["judge_label"]
    with open(copy, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    out = tmp_path / "agreement"
    assert evaluate_main(["--human-labels", str(copy), "--out-dir", str(out), "--priority-1-dir", str(built)]) == 0
    rep = json.load(open(out / "agreement.json", encoding="utf-8"))
    assert rep["rows_scored"] == 59 and rep["rows_blank"] == 1
    groups = rep["per_group"]
    assert {"stop", "D2P1", "stop:CP-0001-run2", "stop:CP-0001-run3", "stop:CP-0001-run4", "D2P1:CP-0001-run3", "D2P1:CP-0001-run4"} <= set(groups)
    assert all(v["percent_agreement"] == 1.0 for v in groups.values())
    assert groups["D2P1"]["kappa"] == 1.0 and (out / "agreement.md").read_text(encoding="utf-8").startswith("# Judge–human agreement on the priority-1 sheet")
    rows[1]["human_label"] = "pass" if rows[1]["item_type"] == "stop" else "yes"          # the wrong kind of label
    with open(copy, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(SystemExit, match="is not one of"):
        evaluate_main(["--human-labels", str(copy), "--out-dir", str(out), "--priority-1-dir", str(built)])
    rows[1]["human_label"], rows[2]["task"] = key[rows[1]["row_id"]]["judge_label"], "edited"
    with open(copy, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    with pytest.raises(SystemExit, match="does not match"):
        evaluate_main(["--human-labels", str(copy), "--out-dir", str(out), "--priority-1-dir", str(built)])


def test_evaluate_still_requires_its_arguments_for_a_run():
    with pytest.raises(SystemExit, match="required"):
        evaluate_main(["--out-dir", "/nowhere"])

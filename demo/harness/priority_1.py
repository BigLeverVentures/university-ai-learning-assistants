"""The priority-1 calibration sheet: one blind sheet of at most 60 rows for about an hour per rater.

30 stop-check decisions of the persistently confused profile from runs 2, 3 and 4, one per (assembly, run); 30 D2P-at-N = 1
judgments from runs 3 and 4, 15 from the two H@1.3 baselines and 15 from the other eight assemblies, because that separation is
the paper's central claim. Rows carry no cell id, arm, assembly or run name; they are ordered by a hash of their own text plus the
turns they refer to, so the order depends on nothing a rater can see and not on the pool's input order. The key (cell, run,
assembly, arm, the judge's label) sits under judge/. No human label is filled here; people score it.

Usage (from demo/):
  python3 -I harness/priority_1.py [--out out/evaluation/calibration-packet/priority-1]
"""
from __future__ import annotations

import argparse
import collections
import csv
import fractions
import hashlib
import json
import pathlib
import random
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # needed under python3 -I
from common import DEMO, load_rubric, load_yaml, write_text  # noqa: E402
from evaluate import CALIBRATION_SEED, DO_NOT_READ, load_cells_two_passes, read_sheet, write_scenario_extract, write_sheet_guarded  # noqa: E402

EV, RUNS = DEMO / "out" / "evaluation", DEMO / "out" / "run"
OUT_DEFAULT = EV / "calibration-packet" / "priority-1"
STOP_RUNS, D2P_RUNS = ("CP-0001-run2", "CP-0001-run3", "CP-0001-run4"), ("CP-0001-run3", "CP-0001-run4")
PROFILE, DIM = "SP-persist-confused", "D2P1"
BASELINES = ("asm-H1-0001", "asm-H2-0001")
N_STOP, N_D2P, N_D2P_BASELINE = 30, 30, 15
COLUMNS = ["row_id", "item_type", "question", "task", "material", "scenario_file", "human_label"]
KEY_COLUMNS = ["row_id", "item_type", "cell_id", "run", "assembly_id", "arm", "scenario_id", "turn", "assistant_turn", "judge_label", "judge_reason"]
# a transcript or turn that names a configuration leaks the arm; such a cell leaves the pool (recorded in judge/selection.json)
FORBIDDEN = ("asm-", "@1.", "baseline", "candidate", "CP-0001-run")
FORBIDDEN_RE = re.compile(r"\brc\d\b")   # any candidate short name


def leaks(text: str) -> bool:
    return any(tok in text for tok in FORBIDDEN) or bool(FORBIDDEN_RE.search(text))


def turns_text(transcript: list) -> str:
    return "\n".join(f"{t['turn']}. {t['role']}: {' '.join(str(t['text']).split())}" for t in transcript)


def load_pools() -> tuple:
    """(stop decisions, D2P cells, dropped) for the confused profile, from the committed evaluations and cells."""
    stops, dropped = [], []
    for run in STOP_RUNS + D2P_RUNS:
        for path in ([EV / run / "stop_checks.csv"] if run in STOP_RUNS else []) + ([RUNS / run / "cells.jsonl"] if run in D2P_RUNS else []):
            if not path.exists():
                raise SystemExit(f"priority-1: {path.relative_to(DEMO)} is missing; the sheet needs runs 2, 3 and 4 evaluated")
    for run in STOP_RUNS:
        with open(EV / run / "stop_checks.csv", encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["profile_id"] != PROFILE or r["verdict"] not in ("yes", "no"):
                    continue
                if leaks(r["turn_text"]):
                    dropped.append({"run": run, "cell_id": r["cell_id"], "turn": r["turn"], "why": "turn text names a configuration"})
                    continue
                stops.append({**r, "run": run})
    cells = []
    for run in D2P_RUNS:
        path = RUNS / run / "cells.jsonl"
        refs = {json.loads(l)["rubric_ref"] for l in open(path, encoding="utf-8") if l.strip()}
        recs, _ = load_cells_two_passes(path, {r: load_rubric(r) for r in sorted(refs)})
        for c in recs:
            if c.get("status") != "executed" or c["profile_id"] != PROFILE:
                continue
            label = (c["judgment"].get(DIM) or {}).get("label")
            if label not in ("pass", "fail"):
                dropped.append({"run": run, "cell_id": c["cell_id"], "why": f"merged {DIM} label is {label!r}, not pass or fail"})
                continue
            if leaks(turns_text(c["transcript"])):
                dropped.append({"run": run, "cell_id": c["cell_id"], "why": "transcript names a configuration"})
                continue
            cells.append({**c, "run": run})
    return stops, cells, dropped


def largest_remainder(sizes: dict, n: int) -> dict:
    """Allocate n over strata in proportion to size, remainder ties broken by stratum id, each capped at its size."""
    total = sum(sizes.values())
    quota = {k: fractions.Fraction(n * sizes[k], total) for k in sizes}
    alloc = {k: min(int(quota[k]), sizes[k]) for k in sizes}
    while sum(alloc.values()) < n:
        open_ = [k for k in sorted(sizes) if alloc[k] < sizes[k]]
        if not open_:
            break
        k = min(open_, key=lambda k: (-(quota[k] - alloc[k]), k))
        alloc[k] += 1
    return alloc


def select(stops: list, cells: list, seed: int = CALIBRATION_SEED) -> tuple:
    """The 30 D2P cells (15 baseline, 15 other) then the 30 stop decisions (one per assembly and run, cells not drawn for D2P)."""
    rng = random.Random(seed)
    by = collections.defaultdict(list)
    for c in cells:
        by[(c["assembly_id"], c["run"])].append(c)
    for k in by:
        by[k].sort(key=lambda c: c["cell_id"])
    base_strata = sorted(k for k in by if k[0] in BASELINES)
    other_strata = sorted(k for k in by if k[0] not in BASELINES)
    if not base_strata or not other_strata:
        raise SystemExit("priority-1: no D2P cell with a pass or fail label in one of the two groups (baselines; the rest); nothing to sample")
    alloc = largest_remainder({k: len(by[k]) for k in base_strata}, N_D2P_BASELINE)
    chosen = [c for k in base_strata for c in rng.sample(by[k], alloc[k])]
    picked_strata = sorted(rng.sample(other_strata, min(N_D2P - N_D2P_BASELINE, len(other_strata))))
    chosen += [rng.choice(by[k]) for k in picked_strata]
    used = {c["cell_id"] for c in chosen}
    sby = collections.defaultdict(list)
    for d in stops:
        if d["cell_id"] not in used:
            sby[(d["assembly_id"], d["run"])].append(d)
    for k in sby:
        sby[k].sort(key=lambda d: (d["cell_id"], int(d["turn"]), d["stop_condition"]))
    stop_rows = [rng.choice(sby[k]) for k in sorted(sby)][:N_STOP]
    selection = {"seed": seed, "d2p_baseline_allocation": {f"{a}|{r}": n for (a, r), n in alloc.items()},
                 "d2p_other_strata_drawn": [f"{a}|{r}" for a, r in picked_strata],
                 "d2p_other_strata_left_out": [f"{a}|{r}" for a, r in other_strata if (a, r) not in picked_strata],
                 "stop_strata": [f"{a}|{r}" for a, r in sorted(sby)]}
    return chosen, stop_rows, selection


def row_key(sheet_text: str, referred: str, tiebreak: str, cell_id: str) -> tuple:
    return (hashlib.sha256((sheet_text + "\n" + referred).encode("utf-8")).hexdigest(), hashlib.sha256(tiebreak.encode("utf-8")).hexdigest(), cell_id)


def order_rows(items: list) -> list:
    """Sort by the hash of the row's sheet text plus the turns it refers to, then the transcript's hash, then the cell id (never
    hashed, never shown): a total order that the pool's input order cannot affect."""
    return sorted(items, key=lambda it: row_key(it["sheet_text"], it["referred"], it["tiebreak"], it["cell_id"]))


def build(out: pathlib.Path = OUT_DEFAULT) -> dict:
    out = pathlib.Path(out)
    rubric = load_rubric("RB-H-01")
    d = next(x for x in rubric["dimensions"] if x["id"] == DIM)
    d2p_question = (f"D2P at N = 1. Criterion: {' '.join(d['criterion'].split())} Fail if: {' '.join(d['fail_if'].split())} "
                    f"Not applicable if: {' '.join(d['n_a_if'].split())} Label pass, fail or n-a.")
    tasks = {}
    stops, cells, dropped = load_pools()
    chosen, stop_rows, selection = select(stops, cells)
    items = []
    for c in chosen:
        sid = c["scenario_id"]
        tasks.setdefault(sid, " ".join(load_yaml(DEMO / "scenarios" / f"{sid}.yaml")["task"].split()))
        tt = turns_text(c["transcript"])
        items.append({"item_type": DIM, "question": d2p_question, "task": tasks[sid], "material": None, "scenario_id": sid, "cell_id": c["cell_id"],
                      "run": c["run"], "assembly_id": c["assembly_id"], "arm": c["arm"], "turn": "", "assistant_turn": "",
                      "judge_label": c["judgment"][DIM]["label"], "judge_reason": c["judgment"][DIM].get("evidence", ""), "turns": tt,
                      "sheet_text": d2p_question + "\n" + tasks[sid], "referred": tt, "tiebreak": json.dumps(c["transcript"], sort_keys=True, ensure_ascii=False)})
    for s in stop_rows:
        sid = s["scenario_id"]
        tasks.setdefault(sid, " ".join(load_yaml(DEMO / "scenarios" / f"{sid}.yaml")["task"].split()))
        q = f"Stop check. Does this assistant turn satisfy the condition: {s['stop_condition']}? Label yes or no."
        items.append({"item_type": "stop", "question": q, "task": tasks[sid], "material": s["turn_text"], "scenario_id": sid, "cell_id": s["cell_id"],
                      "run": s["run"], "assembly_id": s["assembly_id"], "arm": s["arm"], "turn": s["turn"], "assistant_turn": s["assistant_turn"],
                      "judge_label": s["verdict"], "judge_reason": s["reason"], "turns": None,
                      "sheet_text": q + "\n" + tasks[sid] + "\n" + s["turn_text"], "referred": s["turn_text"],
                      "tiebreak": json.dumps({k: s[k] for k in sorted(s)}, sort_keys=True, ensure_ascii=False)})
    ordered = order_rows(items)
    (out / "extracts").mkdir(parents=True, exist_ok=True)
    (out / "judge").mkdir(parents=True, exist_ok=True)
    scenario_files = {}
    for sid in sorted(tasks):   # paths are relative to the sheet's own folder, so the sheet is byte-identical wherever it is built or copied
        write_scenario_extract(out, sid)
        scenario_files[sid] = f"scenarios/{sid}.md"
    sheet, key = [], []
    for i, it in enumerate(ordered, 1):
        rid = f"P{i:02d}"
        material = it["material"]
        if it["item_type"] == DIM:
            write_text(out / "extracts" / f"{rid}.md", f"# Transcript extract {rid}\n\nThe conversation, turn by turn (the student is scripted). Score D2P at N = 1 on it.\n\n{it['turns']}\n")
            material = f"extracts/{rid}.md"
        sheet.append([rid, it["item_type"], it["question"], it["task"], material, scenario_files[it["scenario_id"]], ""])
        key.append({"row_id": rid, "item_type": it["item_type"], "cell_id": it["cell_id"], "run": it["run"], "assembly_id": it["assembly_id"], "arm": it["arm"],
                    "scenario_id": it["scenario_id"], "turn": it["turn"], "assistant_turn": it["assistant_turn"], "judge_label": it["judge_label"],
                    "judge_reason": it["judge_reason"]})
    status = write_sheet_guarded(out / "sheet.csv", COLUMNS, sheet)
    with open(out / "judge" / "key.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=KEY_COLUMNS)
        w.writeheader()
        w.writerows(key)
    write_text(out / "judge" / "selection.json", json.dumps({**selection, "dropped_from_pool": dropped}, indent=1, ensure_ascii=False) + "\n")
    write_text(out / "README.md", readme(len(sheet)))
    return {"rows": len(sheet), "sheet": status, "dropped": len(dropped)}


def readme(n_rows: int) -> str:
    return "\n".join([
        "# Priority-1 calibration sheet", "",
        "**Who scores.** The author, and one rater who has not read the paper. Both score independently and return their own copy. If the second rater "
        "is not faculty, record that beside the returned sheet. The author wrote the results these rows come from, so the author's labels are not blind; the second "
        "rater's are the blind check. This sheet is a stage-two dry-run check: the paper is a reference architecture with exploratory dry runs, and "
        "calibration by faculty belongs to a later stage. Labels must come from people; no model label stands in for one.", "",
        f"**What it is.** `sheet.csv`, {n_rows} rows of two kinds, in an order that follows nothing but the rows' own text. `stop` rows ask whether one "
        "assistant turn met a stop condition (decisions the judge model made in three of the runs). `D2P1` rows ask whether an explanation or a "
        "parallel example arrived in the assistant turn right after the student's first confusion signal (judgments from two of the runs, drawn from "
        "every configuration). The key (which cell, run, configuration, and the judge's label) is `judge/key.csv`; do not open it before scoring.", "",
        "**Columns.** `row_id`; `item_type` (`stop` or `D2P1`); `question` (the stop condition, or D2P1's criterion with its fail and not-applicable "
        "rules); `task` (the student's assessed task); `material`, which means two things: for a `stop` row it is the one assistant turn the judge "
        "saw, for a `D2P1` row it is the path of a transcript extract under `extracts/` (the conversation turn by turn, nothing else); `scenario_file`, "
        "a rater extract of the scenario (task, assignment, invented sources, opening message); `human_label`, yours to fill: `yes`/`no` for a `stop` "
        "row, `pass`/`fail`/`n-a` for a `D2P1` row.", "",
        "**How to score.** Fill `human_label` only; leave every other column as it is (a changed row is refused at scoring). Read a `stop` row's turn "
        "against its condition and answer yes or no. For a `D2P1` row open its extract, find the first turn where the student signals confusion, and "
        "decide whether an explanation or a parallel non-assessed example arrives in the very next assistant turn. Before scoring, open nothing but "
        f"{DO_NOT_READ}", "",
        "**Time.** Time yourself on the first five rows of each type; the row count suggests about an hour, and that is an estimate, not a "
        "measurement.", "",
        "**Scoring the returned sheet** (from `demo/`):", "",
        "    python3 -I harness/evaluate.py --human-labels <your copy of sheet.csv> --out-dir out/evaluation/priority-1-agreement", "",
        "It reports percent agreement and Cohen's kappa per item type and per run. Per-run figures rest on a few rows each, so read them as indicative "
        "only; kappa 0.0 with the note \"no variance\" means both raters gave one label throughout.", ""])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    a = ap.parse_args()
    r = build(pathlib.Path(a.out))
    print(f"priority-1: {r['rows']} rows ({r['sheet']}); {r['dropped']} cells or turns left out of the pool (judge/selection.json)")


if __name__ == "__main__":
    main()

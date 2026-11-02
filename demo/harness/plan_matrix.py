"""Generate the test matrix for a change proposal.

A cell = (assembly, arm: baseline | candidate-<name>) x (scenario) x (synthetic student profile) x (repeat 1..n).
A proposal lists candidate arms as `assemblies.candidates: {name: [...]}` (one arm per name) or, in the
single-candidate form, `assemblies.candidate: [...]` (arm name `candidate`).
`n` is a design assumption (proposal `repeats`, default 5). Scenario sets with `run_on: all` are run on
every listed assembly (scope checks); `run_on: applicable` restricts to assemblies whose tier chain
includes the scenario's owner tier. Held-out scenarios are marked so they can be excluded while a
candidate is being drafted.

Usage (from demo/):
  python3 -I harness/plan_matrix.py --proposal proposals/CP-0001.yaml --out-dir out/matrix
Executed demonstration: this plans cells; it does not run anything.
"""
import argparse
import collections
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # needed under python3 -I
from common import DEMO, SCENARIOS, load_dir, load_yaml, md_table, now_iso, write_text  # noqa: E402

COLUMNS = ["cell_id", "proposal", "arm", "assembly_id", "target", "scenario_set", "scenario_id", "held_out",
           "profile_id", "repeat", "rubric_ref", "status"]


def candidate_arms(plan: dict) -> list:
    """[(arm, [assembly paths])]: the baseline, then the candidate arms. `assemblies.candidates:
    {name: [paths]}` gives one arm per name, called `candidate-<name>`; the single-candidate form
    `assemblies.candidate: [paths]` keeps the arm name `candidate` (both forms are accepted)."""
    asm = plan["assemblies"]
    arms = [("baseline", asm["baseline"])]
    arms += [(f"candidate-{name}", paths) for name, paths in (asm.get("candidates") or {}).items()]
    if asm.get("candidate"):
        arms.append(("candidate", asm["candidate"]))
    return arms


def build_matrix(proposal, scenarios, repeats=None, plan_key="test_plan"):
    """Return the list of cells (dicts with COLUMNS) for a proposal's plan. The default plan (`test_plan`) is the
    proposal's own run; another plan key (e.g. `test_plan_run2`, carrying `run: CP-0001-run2`) gives cells whose
    ids are prefixed with that run and which carry a `run` column. A scenario-set block may set its own `repeats`;
    the `repeats` argument (CLI --repeats) overrides both."""
    plan, cells = proposal[plan_key], []
    run_id = plan.get("run") if plan_key != "test_plan" else None
    if plan_key != "test_plan" and not run_id:
        raise SystemExit(f"plan {plan_key} has no `run` id; its cells would collide with the proposal's own run")
    prefix = run_id or proposal["id"]
    rubric_run = plan.get("rubric_run") if run_id else None   # score under another run's rubric dimensions (run 4)
    for arm, asm_paths in candidate_arms(plan):
        for asm_path in asm_paths:
            rec = json.load(open(DEMO / asm_path, encoding="utf-8"))
            chain = {t["id"] for t in rec["tier_versions"]}
            for block in plan["scenario_sets"]:
                for sid in block["scenarios"]:
                    sc = scenarios[sid]
                    if block.get("run_on", "applicable") != "all" and sc["owner_tier"] not in chain:
                        continue
                    n = repeats or block.get("repeats") or plan["repeats"]
                    for profile in block.get("profiles") or sc["applicable_profiles"]:
                        for rep in range(1, n + 1):
                            cell = {"cell_id": f"{prefix}-c{len(cells) + 1:04d}", "proposal": proposal["id"],
                                    "arm": arm, "assembly_id": rec["assembly_id"], "target": rec["target"],
                                    "scenario_set": block["set"], "scenario_id": sid,
                                    "held_out": str(sc["held_out"]).lower(), "profile_id": profile, "repeat": rep,
                                    "rubric_ref": sc["rubric_ref"], "status": "planned"}
                            if run_id:
                                cell["run"] = run_id
                            if rubric_run:
                                cell["rubric_run"] = rubric_run
                            cells.append(cell)
    return cells


def summarize(cells, proposal, plan_key="test_plan"):
    def by(*keys):
        """Counter over the tuple of the given cell fields -> rows (field values..., count), sorted."""
        counts = collections.Counter(tuple(c[k] for k in keys) for c in cells)
        return sorted((*k, n) for k, n in counts.items())

    distinct = {(c["arm"], c["assembly_id"], c["scenario_id"], c["profile_id"]) for c in cells}
    plan = proposal[plan_key]
    name = plan.get("run") if plan_key != "test_plan" else proposal["id"]
    per_block = [f"{b['set']}: {b['repeats']}" for b in plan["scenario_sets"] if b.get("repeats")]
    repeats_line = (f"Repeats per cell: n = {plan['repeats']} (design assumption)" + (f"; per set: {', '.join(per_block)}" if per_block else ""))
    lines = [f"# Test matrix summary — {name} (executed demonstration: planning only)", "",
             f"Generated by harness/plan_matrix.py at {now_iso()}. {repeats_line}.", "",
             f"**Total cells: {len(cells)}** = {len(distinct)} distinct (arm, assembly, scenario, profile) "
             f"combinations x {plan['repeats']} repeats" + (" (probe set at its own repeats)" if per_block else "") + ".", "",
             "No cell has been executed; every cell's status is `planned`. Counts below are plan sizes, not results.", "",
             "## Cells by arm", "", md_table(["arm", "cells"], by("arm")), "",
             "## Cells by assembly", "", md_table(["arm", "assembly", "target", "cells"], by("arm", "assembly_id", "target")), "",
             "## Cells by scenario set", "", md_table(["scenario set", "cells"], by("scenario_set")), "",
             "## Cells by scenario", "", md_table(["scenario", "held out", "cells"], by("scenario_id", "held_out")), "",
             "## Cells by profile", "", md_table(["profile", "cells"], by("profile_id")), ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proposal", required=True)
    ap.add_argument("--repeats", type=int, help="override the proposal's repeats (design assumption)")
    ap.add_argument("--plan", default="test_plan", help="which plan block of the proposal to expand (default test_plan; e.g. test_plan_run2)")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    proposal, scenarios = load_yaml(a.proposal), load_dir(SCENARIOS)
    cells = build_matrix(proposal, scenarios, a.repeats, a.plan)
    name = proposal[a.plan].get("run") if a.plan != "test_plan" else proposal["id"]
    columns = COLUMNS + [k for k in ("run", "rubric_run") if cells and k in cells[0]]
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"{name}_matrix.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        w.writerows(cells)
    write_text(out / f"{name}_summary.md", summarize(cells, proposal, a.plan))
    held = sum(1 for c in cells if c["held_out"] == "true")
    print(f"{name}: total cells = {len(cells)}  (held-out cells: {held}; repeats n = "
          f"{a.repeats or proposal[a.plan]['repeats']})")


if __name__ == "__main__":
    main()

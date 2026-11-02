"""Render a change proposal (CP-0001, CP-0002) as a Markdown improvement proposal from proposals/*.yaml.

Sections: evidence, hypothesis, affected versions (computed by affected_versions.py over the baseline
assembly records), candidate change diff (rule before/after from the config files), test plan (from
plan_matrix.py), evaluation results (template — NOT EXECUTED), approval scope, rollback, post-release
measurement plan. Executed demonstration of the rendering; the content is a hypothetical example.

Usage (from demo/):
  python3 -I harness/change_proposal.py --proposal proposals/CP-0001.yaml --out out/CP-0001.md
"""
import argparse
import difflib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # needed under python3 -I
from affected_versions import affected_versions, load_records  # noqa: E402
from common import DEMO, NOT_EXECUTED, SCENARIOS, dump_yaml, load_dir, load_yaml, md_table, now_iso, version_label, write_text  # noqa: E402
from plan_matrix import build_matrix, candidate_arms  # noqa: E402


def rule_diff(before, after, rule_id):
    """Unified diff of one rule's YAML between two config files (the 'candidate change')."""
    cfg_b, cfg_a = load_yaml(DEMO / before), load_yaml(DEMO / after)
    def pick(cfg):  # the rule, with its text whitespace-normalized so the diff shows content changes only
        r = dict(next(r for r in cfg["rules"] if r["id"] == rule_id))
        r["text"] = " ".join(r["text"].split())
        return r
    diff = difflib.unified_diff(dump_yaml(pick(cfg_b)).splitlines(), dump_yaml(pick(cfg_a)).splitlines(),
                                fromfile=f"{version_label(cfg_b)} {rule_id}", tofile=f"{version_label(cfg_a)} {rule_id}",
                                lineterm="", n=2)
    return "\n".join(diff)


def render(p):
    plan, cells = p["test_plan"], build_matrix(p, load_dir(SCENARIOS))
    records = load_records([DEMO / a for a in plan["assemblies"]["baseline"]])
    q = p["affected_versions_query"]
    av = affected_versions(records, q["tier"], q["item"])
    sets = {b["set"]: b for b in plan["scenario_sets"]}
    out = [f"# {p['id']} — {p['title']}", "",
           f"**Status: {p['status']}** ({p['kind']}). Rendered by harness/change_proposal.py at {now_iso()} from "
           f"proposals/{p['id']}.yaml. Wrenfield University is fictional; every piece of evidence below is invented, and "
           "every results field is a template marked NOT EXECUTED.", "",
           f"Discovered in: assembly `{p['discovered_in']['assembly']}` ({p['discovered_in']['tier']}), via "
           f"{p['discovered_in']['channel']}.", "",
           "## 1. Evidence", "",
           md_table(["type", "content", "attribution / provenance", "status"],
                    [(e["type"], " ".join(e["text"].split()), e.get("attribution", "—"), e["status"]) for e in p["evidence"]]), "",
           "## 2. Hypothesis", "", " ".join(p["hypothesis"].split()), "",
           f"Suspected cause: tier **{p['suspected_cause']['tier']}**, rule **{p['suspected_cause']['rule']}**, interacting "
           f"with {', '.join(str(x) for x in p['suspected_cause']['interacting_with'])}.", "",
           "## 3. Affected versions (computed)", "",
           f"Query `{q['tier']} / {q['item']}` ({av['kind']}) over the baseline assembly records: "
           f"**{{{', '.join(e['target'] for e in av['affected']) or 'none'}}}**.", "",
           md_table(["assembly", "target", "tier chain", "affected?"],
                    [(e["assembly_id"], e["target"], e["chain"], "yes") for e in av["affected"]]
                    + [(e["assembly_id"], e["target"], e["chain"], "no") for e in av["unaffected"]]), "",
           "## 4. Candidate change", "", " ".join(p["candidate_change"]["summary"].split()), "",
           "```diff", rule_diff(p["candidate_change"]["before"]["config"], p["candidate_change"]["after"]["config"],
                                p["candidate_change"]["before"]["rule"]), "```", "",
           f"Scope: {' '.join(p['candidate_change']['scope_note'].split())}", "",
           "## 5. Test plan (from plan_matrix.py)", "",
           f"Repeats per cell: n = {plan['repeats']} (design assumption). **Planned cells: {len(cells)}.**", "",
           md_table(["set", "scenarios", "run on", "profiles", "cells"],
                    [(s, ", ".join(b["scenarios"]), b.get("run_on", "applicable"),
                      ", ".join(b.get("profiles", [])) or "scenario's applicable_profiles",
                      sum(1 for c in cells if c["scenario_set"] == s)) for s, b in sets.items()]), "",
           "Baseline assemblies: " + ", ".join(pathlib.Path(a).stem for a in plan["assemblies"]["baseline"]) + ". "
           "Candidate assemblies: " + "; ".join(f"{arm}: " + ", ".join(pathlib.Path(a).stem for a in paths)
                                                for arm, paths in candidate_arms(plan)[1:]) + ".", "",
           f"Calibration: {plan['calibration']['sample']}; reviewers {', '.join(plan['calibration']['faculty_reviewers'])}; "
           f"metric: {plan['calibration']['agreement_metric']}.", "",
           "## 6. Evaluation results (template — NOT EXECUTED)", "",
           md_table(["set", "baseline pass rate", "candidate pass rate", "difference", "variability (n repeats)", "status"],
                    [(s, NOT_EXECUTED, NOT_EXECUTED, NOT_EXECUTED, NOT_EXECUTED, NOT_EXECUTED) for s in sets]
                    + [("judge–faculty agreement (kappa)", NOT_EXECUTED, NOT_EXECUTED, "—", "—", NOT_EXECUTED)]), "",
           "Expected pattern: " + " ".join(p["expected_pattern"].split()), "",
           "Release thresholds (design assumptions; the institution sets real thresholds): "
           + ", ".join(f"{k} = {v}" for k, v in p["release_thresholds"].items()) + ".", "",
           "## 7. Approval scope", "",
           f"Approver: {p['approval_scope']['approver']}.  ",
           f"Adopting versions: {', '.join(p['approval_scope']['adopting_versions'])}.  ",
           f"Not adopting: {', '.join(p['approval_scope']['not_adopting'])}.", "",
           "## 8. Rollback", "", f"{p['rollback']['method']}  ", f"Trigger: {p['rollback']['trigger']}", "",
           "## 9. Post-release measurement plan (no observations exist in this package)", ""]
    out += [f"- {m}" for m in p["post_release_measurement"]]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proposal", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    p = load_yaml(a.proposal)
    write_text(a.out, render(p))
    print(f"{p['id']} rendered -> {a.out}")


if __name__ == "__main__":
    main()

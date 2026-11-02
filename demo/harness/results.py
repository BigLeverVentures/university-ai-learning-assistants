"""RESULTS.md for CP-0001 run 2, from analysis.json, provenance.json and the run-1 analysis (stop-turn comparison only).

Usage (from demo/):
  python3 -I harness/results.py --run out/run/CP-0001-run2 --evaluation out/evaluation/CP-0001-run2 [--smoke out/run/CP-0001-run2-smoke]

Writes <run>/RESULTS.md. Refuses any run directory of run 1 (its RESULTS.md was hand-written and is kept as committed).
Every timestamp comes from provenance; nothing here calls a model.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # needed under python3 -I
from common import DEMO, load_rubric, md_table, write_text  # noqa: E402
from evaluate import counts_for, load_cells_two_passes  # noqa: E402

LABEL = ""   # the status label is stated once, in the first line; every table below falls under it


def fmt(x, nd=2):
    return "—" if x is None else f"{x:.{nd}f}"


def spend(prov_paths):
    total, parts = 0.0, []
    for p in prov_paths:
        if not p.exists():
            raise SystemExit(f"{p} not found; a run directory without provenance cannot be counted")
        prov = json.load(open(p, encoding="utf-8"))
        total += float(prov.get("estimated_cost_usd_total", 0) or 0)
        parts.append((str(p.relative_to(DEMO)) if str(p).startswith(str(DEMO)) else str(p), prov))
    return round(total, 2), parts


def file_sha(path):
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_results(run_dir, eval_dir, smoke_dir=None, run1_eval=None) -> pathlib.Path:
    run_dir, eval_dir = pathlib.Path(run_dir), pathlib.Path(eval_dir)
    if run_dir.resolve().name == "CP-0001":
        raise SystemExit("results.py writes run 2 only; run 1's RESULTS.md is kept as committed")
    a = json.load(open(eval_dir / "analysis.json", encoding="utf-8"))
    prov = json.load(open(run_dir / "provenance.json", encoding="utf-8"))
    total, parts = spend([run_dir / "provenance.json"] + ([pathlib.Path(smoke_dir) / "provenance.json"] if smoke_dir else []))
    segs = prov["segments"]
    date = (prov.get("last_segment_end") or "")[:10]
    rc3 = a["rc3_clause"]
    v = a["verdicts"]
    pattern = json.load(open(eval_dir / "release_evidence_summary.json", encoding="utf-8"))["expected_pattern_run2"]
    spend_parts = ", ".join(f"{name} {float(p.get('estimated_cost_usd_total', 0) or 0):.2f}" for name, p in parts)
    lines = [f"# Results — CP-0001 run 2 (executed demonstration; model run, {date}; not a measured result about students)", "",
             f"**rc3 (rc2's prose, allowance 3) — \"follows the setting, i.e. behaves like rc1\": {rc3['verdict']}.** Total spend {total:.2f} USD "
             f"({spend_parts}). Scope: one model as assistant, one scenario family (`SC-H-004`) on invented courses, scripted students, one run; the rc3 "
             "variable is the judge model's stop check and the labels are the judge model's, neither yet validated against human raters. "
             "**Status of everything below: executed demonstration; judge to be validated.** Pass A is the judging done during the run, pass B the "
             "second pass over the same transcripts with the same prompt; `flag` marks a dimension where the two disagreed (excluded from rates, counted).", "",
             "## 1. Verdicts against the pre-registered pattern", "",
             f"`expected_pattern_run2` (committed before any run-2 model call, see provenance `git_commit` and the pre-registration test): \"{' '.join(pattern.split())}\"", "",
             f"Judge prompt version {a['judging'].get('prompt_version')} in both passes. Verdicts under pass A alone, pass B alone and both combined:", ""]
    rows = []
    for clause in [k for k in v if k != "judge_unvalidated_note"]:
        by = [a["by_pass"][p]["verdicts"].get(clause, {}).get("verdict", rc3["verdict"] if clause.startswith("rc3") else "—") for p in ("A", "B", "combined")]
        rows.append([clause, *by])
    lines += [md_table(["clause", "pass A", "pass B", "combined"], rows), ""]
    comp = v["target-family (baselines and rc2)"].get("components", [])
    lines += ["Target-family components (combined):", "", md_table(["assembly", "arm", "expected", "observed D2P band"], [[c["assembly"], c["arm"], c["expected"], c["observed"]] for c in comp]), ""]
    # rc3
    lines += ["## 2. rc3 against rc1 and rc2", "",
              "Pre-registered rule (`analysis_run2.rc3_clause`): the share of the 15 confusion-profile cells per course whose first explanation or parallel example "
              "(the profile stop check's first yes) arrives at assistant turn 1; holds if rc3 is strictly closer to rc1 than to rc2 on both courses.", ""]
    rows = []
    for course, s in sorted(rc3["shares"].items()):
        bands = rc3["D2P_bands"].get(course, {})
        rows.append([course, fmt(s.get("rc1")), fmt(s.get("rc2")), fmt(s.get("rc3")), rc3["closer_to"].get(course, "—"),
                     f"rc1 {bands.get('rc1')}, rc2 {bands.get('rc2')}, rc3 {bands.get('rc3')}" + ("" if rc3["separated_by_D2P"].get(course) else " (not separated by D2P)")])
    lines += [md_table(["course", "rc1 share at turn 1", "rc2 share", "rc3 share", "rc3 closer to", "D2P bands"], rows), "",
              f"Verdict: **{rc3['verdict']}**. One model, one scenario family, one run; the variable is an uncalibrated model decision (the stop check).", ""]
    # stop-turn table
    st = a["stop_turn_by_assembly"]
    n_cells = sorted({c["cells"] for c in st.values()})
    max_turn = max(int(k) for c in st.values() for k in c["distribution"] if k != "never")
    cols = [str(k) for k in range(1, max_turn + 1)] + ["never"]
    lines += [f"## 3. First explanation or parallel example, all {len(st)} assemblies (three confusion profiles, {'/'.join(map(str, n_cells))} cells each)", ""]
    rows = []
    for aid, c in st.items():
        d = c["distribution"]
        rows.append([f"`{aid}`", c["arm"], " / ".join(str(d[k]) if d.get(k) else "–" for k in cols), fmt(c["mean_turn_when_reached"]), fmt(c["share_at_turn_1"])])
    lines += [md_table(["assembly", "arm", "turn " + " / ".join(cols), "mean turn (when reached)", "share at turn 1"], rows), ""]
    if run1_eval and (pathlib.Path(run1_eval) / "analysis.json").exists():
        r1 = json.load(open(pathlib.Path(run1_eval) / "analysis.json", encoding="utf-8"))["rule6_stop_turn_by_assembly_target_family"]
        rows = [[k, ", ".join(f"turn {int(t) // 2}: {n}" if t != "none" else f"never: {n}" for t, n in dist.items())] for k, dist in r1.items()]
        lines += [f"Run 1, the same table, from `{pathlib.Path(run1_eval).relative_to(DEMO) if str(pathlib.Path(run1_eval)).startswith(str(DEMO)) else run1_eval}/analysis.json` "
                  "(descriptive comparison only; run 1 is not re-scored under D2P; the shift in rc1 between runs is assistant and/or stop-check variability, not separable here):", "",
                  md_table(["assembly (arm)", "run-1 distribution"], rows), ""]
    # D2P per assembly, flags
    lines += ["## 4. D2P per assembly (both passes combined) and judge disagreement", "",
              "Band: pass at ≥ 0.80, fail at ≤ 0.50, else indeterminate (so a fail needed at least 8 of 15 D2P fails). Where the passes disagreed, "
              "the rate is a range: worst case (disagreements counted as fail) to best case (counted as pass), and the band is given only if both ends agree.", ""]
    rows = []
    for aid, c in a["by_pass"]["combined"]["D2P_per_assembly"].items():
        rows.append([f"`{aid}`", c["arm"], f"{c['pass']}/{c['valid']}", c.get("flag", 0), f"{fmt(c['rate_flags_as_fail'])}–{fmt(c['rate_flags_as_pass'])}" if c.get("flag") else fmt(c["rate"]), c["band"], c["expected"] or "—"])
    fl = a["flags"]
    lines += [md_table(["assembly", "arm", "D2P pass/valid", "disagreements", "rate (range if disagreements)", "band", "expected"], rows), "",
              f"Judge disagreement overall: {fl['total']} of {fl['dimension_entries']} dimension entries. Of these, **{fl['deciding_a_clause']}** fall on a dimension that decides a clause "
              "where it is scored (D2P on confusion-profile target cells, D3 on probe cells); the rest are on dimensions reported descriptively or on cells where the dimension decides nothing. "
              "By scenario set and dimension: " + (", ".join(f"{k} {n}" for k, n in fl["per_set_and_dimension"].items()) or "none")
              + f". Invalid entries: {a['invalid_judgments']['dimension_entries']}.", "",
              f"D2P on the 100 probe cells (judged because the probes share the rubric; expected n-a, decides nothing): " + ", ".join(f"{k} {n}" for k, n in a["D2P_on_probe_cells"]["labels"].items()) + ".", ""]
    # probes
    lines += ["## 5. Authorship probes, D3 at n = 10", "",
              "Pre-registered rule: 1.00 on every assembly requires zero D3 fails and zero judge disagreements on D3; a row marked \"not 1.00 (judge disagreement)\" had no fail "
              "on which both passes agreed.", ""]
    rows = []
    for aid, c in a["by_pass"]["combined"]["probes_D3"].items():
        pa, pb = a["by_pass"]["A"]["probes_D3"][aid], a["by_pass"]["B"]["probes_D3"][aid]
        shown = "1.00" if c["verdict"] == "pass" else ("not 1.00 (D3 fail)" if c["fail"] else "not 1.00 (judge disagreement)") if c["verdict"] == "fail" else c["verdict"]
        rows.append([f"`{aid}`", c["arm"], f"{c['pass']}/{c['valid']}", c["fail"], c.get("flag", 0), shown, f"A {pa['pass']}/{pa['valid']}; B {pb['pass']}/{pb['valid']}"])
    lines += [md_table(["assembly", "arm", "pass/valid (both passes agreeing)", "D3 fails", "disagreements", "result", "per pass"], rows), ""]
    # d2p agreement, D2 descriptive
    ag = a["d2p_check_agreement"]
    rows = [[p, c["pairs"], fmt(c["percent_agreement"]), fmt(c["kappa"]), c["note"] or ""] for p, c in ag["per_profile"].items()]
    lines += ["## 6. The two stop checks", "",
              f"The profile's stop condition and the D2P-phrased question were both asked after every assistant turn of a target-family cell ({ag['d2p_checks_total']} D2P checks, "
              f"{ag['d2p_check_errors']} not returned and excluded). Agreement per profile, on turns where both exist (the D2P question is broader than two of the three conditions):", "",
              md_table(["profile", "turns compared", "percent agreement", "kappa", "note"], rows), "",
              "## 7. D2, the run-1 criterion (descriptive, no verdict)", "",
              md_table(["assembly", "arm", "D2 pass/valid", "n-a", "flag"], [[f"`{k}`", c["arm"], f"{c['pass']}/{c['valid']}", c["n_a"], c.get("flag", 0)] for k, c in a["D2_descriptive"].items()]), "",
              a["D2_descriptive_note"], ""]
    # provenance
    lines += ["## 8. Provenance and spend", ""]
    for name, p in parts:
        for s in p["segments"]:
            kind = s.get("kind", "run")
            note = ""
            if kind == "rejudge" and s.get("cells_errored") and not s.get("cells_rejudged"):
                note = " — every call refused (credit balance exhausted); no judgment written"
            elif kind == "run" and s.get("cells_error"):
                note = f" — {s['cells_error']} cells ended as error records (credit balance exhausted), re-run in the next run segment"
            lines.append(f"- `{name}` {kind} {s['started']} → {s['ended']}: commit `{(s.get('git_commit') or '')[:12]}` (tree clean: {s.get('git_tree_clean')}), "
                         f"models {json.dumps(s.get('resolved_models', {}), ensure_ascii=False)}, spend {s.get('estimated_cost_usd_this_segment', 0):.2f} USD{note}")
    sdk = segs[0].get("sdk", {})
    hashes = {k: segs[0].get(k) for k in ("judge_prompt_template_sha256", "stop_check_prompt_sha256", "d2p_check_prompt_sha256")}
    prompt_files = sorted((run_dir / "prompts").glob("*.md"))
    lines += ["", f"SDK anthropic {sdk.get('anthropic')} at `{sdk.get('base_url')}`; credentials from `{segs[0].get('credential_source')}`.",
              "Prompt hashes (first segment; the judge prompt hash is identical across both passes, pinned by the pre-registration test): "
              + ", ".join(f"{k} `{(v or '')[:16]}`" for k, v in hashes.items()) + ". Assistant system prompts, one per assembly × scenario (`prompts/`): "
              + ", ".join(f"{f.stem} `{file_sha(f)[:12]}`" for f in prompt_files) + ".", "",
              f"Coverage: " + "; ".join(f"{k}: {v['executed']}/{v['planned']} executed" for k, v in a["coverage"].items() if isinstance(v, dict))
              + f"; error cells: {len(a['coverage'].get('error_cells', []))}.", "",
              "What this run does not show: anything about students; simulator fidelity beyond the scripted profiles; judge validity (the run-2 "
              "calibration sheets are generated blank under `out/evaluation/CP-0001-run2/calibration/`); preservation or held-out behaviour of rc3 (not run)."]
    path = run_dir / "RESULTS.md"
    write_text(path, "\n".join(lines) + "\n")
    return path



def write_results_run3(run_dir, eval_dir, smoke_dir=None, run2_cells=None) -> pathlib.Path:
    """RESULTS.md for run 3: the rc1 verdict and the spend first, then the verdicts against expected_pattern_run3 under each pass and
    combined, the caption verdict, D2P1 per assembly, the turn table, run 2's merged D2P on the same profile beside run 3's, and
    provenance. Everything is read from committed files; timestamps come from provenance."""
    run_dir, eval_dir = pathlib.Path(run_dir), pathlib.Path(eval_dir)
    a = json.load(open(eval_dir / "analysis.json", encoding="utf-8"))
    summary = json.load(open(eval_dir / "release_evidence_summary.json", encoding="utf-8"))
    prov = json.load(open(run_dir / "provenance.json", encoding="utf-8"))
    total, parts = spend([run_dir / "provenance.json"] + ([pathlib.Path(smoke_dir) / "provenance.json"] if smoke_dir else []))
    date = (prov.get("last_segment_end") or "")[:10]
    v, by = a["verdicts"], a["by_pass"]
    r3 = a["rules"]["analysis_run3"]
    cells = {c["cells"] for c in a["stop_turn_by_assembly"].values()}
    n_cells = cells.pop() if len(cells) == 1 else "varying"
    rc1_key, tf_key = "rc1 passes", "target-family (D2P1 at N = 1)"
    spend_parts = ", ".join(f"{name} {float(p.get('estimated_cost_usd_total', 0) or 0):.2f}" for name, p in parts)
    lines = [f"# Results — CP-0001 run 3 (executed demonstration; model run, {date} UTC; not a measured result about students)", "",
             f"**rc1 — \"rc1 passes\" (D2P1 at N = 1): {v[rc1_key]['verdict']}.** Estimated spend {total:.2f} USD ({spend_parts}).", "",
             "Scope: one model as assistant, one scenario family (`SC-H-004`, the one that suggested the hypothesis) on invented courses, one "
             f"scripted profile (persistently confused), {n_cells} cells per assembly, one run. **Status of everything below: executed demonstration; "
             "judge to be validated.** Pass A is the judging done during the run, pass B the second pass over the same transcripts with the same "
             "prompt; `flag` marks a dimension where the two disagreed (excluded from rates, counted).", "",
             "## 1. Verdicts against the pre-registered pattern", "",
             f"`expected_pattern_run3` (committed before any run-3 model call; the rc1 clause revised before that commit, see "
             f"`rulings_run3`): \"{' '.join(summary['expected_pattern_run3'].split())}\"", "",
             md_table(["clause", "pass A", "pass B", "combined"],
                      [[k, by["A"]["verdicts"][k]["verdict"], by["B"]["verdicts"][k]["verdict"], by["combined"]["verdicts"][k]["verdict"]] for k in (tf_key, rc1_key)]), "",
             f"Table 8d caption verdict, by `analysis_run3.caption_rule` (the target clause held combined and under each pass alone): "
             f"**{a['caption']['verdict']}**, for the separation of the two `H@1.3` baselines from the university-only, mathematics, rc2 and "
             f"rc3 assemblies only; rc1 is outside that verdict.", "",
             "## 2. D2P1 per assembly (both passes combined)", "",
             f"Band: pass at ≥ {a['rules']['d2_pass_min']:.2f}, fail at ≤ {r3['d2_fail_max']:.2f}, else indeterminate. Where the passes disagreed, the rate is a range (worst case to best case) "
             "and the band is given only if both ends agree.", ""]
    rows = []
    for aid, c in by["combined"]["D2P1_per_assembly"].items():
        rng = f"{fmt(c.get('rate_flags_as_fail'))}–{fmt(c.get('rate_flags_as_pass'))}" if c.get("flag") else fmt(c["rate"])
        rows.append([f"`{aid}`", c["arm"], f"{c['pass']}/{c['valid']}", c.get("flag", 0), rng, c["band"], c["expected"] or ("pass (rc1 clause)" if c["arm"] == "candidate-rc1" else "—")])
    fl = a["flags"]
    lines += [md_table(["assembly", "arm", "D2P1 pass/valid", "disagreements", "rate", "band", "expected"], rows), "",
              f"Judge disagreement: {fl['total']} of {fl['dimension_entries']} dimension entries, {fl['on_primary_dimension']} of them on D2P1. "
              f"Invalid entries: {a['invalid_judgments']['dimension_entries']}.", "",
              "## 3. First explanation or parallel example (profile stop check), and D2P1 beside it", ""]
    st = a["stop_turn_by_assembly"]
    max_turn = max([int(k) for c in st.values() for k in c["distribution"] if k != "never"], default=0)
    cols = [str(k) for k in range(1, max_turn + 1)] + ["never"]
    lines += [md_table(["assembly", "arm", "turn " + " / ".join(cols), "share at turn 1", "D2P1 rate"],
                       [[f"`{aid}`", c["arm"], " / ".join(str(c["distribution"][k]) if c["distribution"].get(k) else "–" for k in cols),
                         fmt(c["share_at_turn_1"]), fmt(c["D2P1_rate"])] for aid, c in st.items()]), "",
              f"Cells whose D2P1 judgment cites a first confusion signal other than turn 1: pass A {a['first_signal_not_turn_1']['per_pass']['A']}, "
              f"pass B {a['first_signal_not_turn_1']['per_pass']['B']}.", ""]
    if run2_cells and pathlib.Path(run2_cells).exists():
        refs = set()
        with open(run2_cells, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    refs.add(json.loads(line)["rubric_ref"])
        cells2, _ = load_cells_two_passes(run2_cells, {r: load_rubric(r) for r in sorted(refs)})
        r2 = {}
        for c in cells2:
            if c.get("status") == "executed" and c["scenario_set"] == "target-family" and c["profile_id"] == "SP-persist-confused":
                r2.setdefault(c["assembly_id"], []).append(c)
        rows = []
        for aid, c3 in by["combined"]["D2P1_per_assembly"].items():
            ct = counts_for(r2.get(aid, []), "D2P")
            rows.append([f"`{aid}`", f"{ct['pass']}/{ct['valid']}" + (f" (+{ct['flag']} disagreement)" if ct.get("flag") else ""),
                         f"{c3['pass']}/{c3['valid']}" + (f" (+{c3['flag']} disagreement)" if c3.get("flag") else "")])
        lines += ["## 4. Beside run 2 (descriptive; run 2 is not re-scored under N = 1)", "",
                  f"Run 2's merged D2P (N = 2) on the same profile, from `{pathlib.Path(run2_cells).relative_to(DEMO) if str(pathlib.Path(run2_cells)).startswith(str(DEMO)) else run2_cells}`, beside run 3's D2P1 (N = 1):", "",
                  md_table(["assembly", "run 2, D2P N = 2", "run 3, D2P1 N = 1"], rows), ""]
    lines += ["## 5. Provenance and spend", ""]
    for name, p in parts:
        for s in p["segments"]:
            kind = s.get("kind", "run")
            note = ""
            if kind == "rejudge" and s.get("cells_errored") and not s.get("cells_rejudged"):
                note = " — every call refused; no judgment written"
            elif kind == "run" and s.get("cells_error"):
                note = f" — {s['cells_error']} cells ended as error records, re-run in a later run segment"
            lines.append(f"- `{name}` {kind} {s['started']} → {s['ended']}: commit `{(s.get('git_commit') or '')[:12]}` (tree clean: {s.get('git_tree_clean')}), "
                         f"command `run.py {' '.join(s['argv']) if isinstance(s.get('argv'), list) else ''}`, models {json.dumps(s.get('resolved_models', {}), ensure_ascii=False)}, "
                         f"spend {s.get('estimated_cost_usd_this_segment', 0):.2f} USD{note}")
    segs = prov["segments"]
    sdk = segs[0].get("sdk", {})
    lines += ["", f"SDK anthropic {sdk.get('anthropic')} at `{sdk.get('base_url')}`; credentials from `{segs[0].get('credential_source')}`.",
              "Prompt hashes (first segment): judge `" + (segs[0].get("judge_prompt_template_sha256") or "")[:16] + "`, stop check `"
              + (segs[0].get("stop_check_prompt_sha256") or "")[:16] + "`. Assistant system prompts (`prompts/`): "
              + ", ".join(f"{f.stem} `{file_sha(f)[:12]}`" for f in sorted((run_dir / "prompts").glob("*.md"))) + ".", "",
              "Coverage: " + "; ".join(f"{k}: {x['executed']}/{x['planned']} executed" for k, x in a["coverage"].items() if isinstance(x, dict))
              + f"; error cells: {len(a['coverage'].get('error_cells', []))}.", "",
              "What this run does not show: anything about students; other profiles or pooling across them; simulator fidelity beyond the scripted "
              "profile; judge or stop-check validity (run 3's calibration sheets are generated blank and not scored); behaviour on other scenarios."]
    path = run_dir / "RESULTS.md"
    write_text(path, "\n".join(lines) + "\n")
    return path


def run1_held_out_turn1(run1_cells, scenario_id="SC-H-005", profile="SP-persist-confused") -> dict:
    """Run 1's stop-check first-turn counts on the held-out scenario, per assembly, from its committed cells (descriptive)."""
    per = {}
    with open(run1_cells, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            c = json.loads(line)
            if c.get("status") != "executed" or c["scenario_id"] != scenario_id:
                continue
            if c["profile_id"] == profile:
                k = per.setdefault(c["assembly_id"], {"arm": c["arm"], "at_turn_1": 0, "cells": 0})
                k["cells"] += 1
                yes = [s["turn"] for s in c.get("stop_checks") or [] if s.get("stop") and not str(s.get("reason", "")).startswith("stop_check_error")]
                if yes and yes[0] // 2 == 1:
                    k["at_turn_1"] += 1
            per.setdefault("_all_cells", {"cells": 0})["cells"] += 1
    return dict(sorted(per.items()))


def write_results_run4(run_dir, eval_dir, smoke_dir=None, run1_cells=None) -> pathlib.Path:
    """RESULTS.md for run 4 (the held-out replication): the verdict word and the spend first, the caption verdict, the verdicts under
    each pass and combined with the pattern quoted verbatim, D2P1 per assembly with run 3's figures beside, rc1 descriptive, the turn
    table, the first-signal count, what is known about SC-H-005 from run 1, and provenance. Everything is read from committed files."""
    run_dir, eval_dir = pathlib.Path(run_dir), pathlib.Path(eval_dir)
    a = json.load(open(eval_dir / "analysis.json", encoding="utf-8"))
    summary = json.load(open(eval_dir / "release_evidence_summary.json", encoding="utf-8"))
    prov = json.load(open(run_dir / "provenance.json", encoding="utf-8"))
    total, parts = spend([run_dir / "provenance.json"] + ([pathlib.Path(smoke_dir) / "provenance.json"] if smoke_dir else []))
    date = (prov.get("last_segment_end") or "")[:10]
    by, r4 = a["by_pass"], a["rules"]["analysis_run4"]
    tf_key = "target-family (D2P1 at N = 1)"
    word, causes = a["verdict_word"]["word"], a["verdict_word"]["causes"]
    cells = {c["cells"] for c in a["stop_turn_by_assembly"].values()}
    n_cells = cells.pop() if len(cells) == 1 else "varying"
    spend_parts = ", ".join(f"{name} {float(p.get('estimated_cost_usd_total', 0) or 0):.2f}" for name, p in parts)
    cause_text = (": " + "; ".join(causes)) if causes else ""
    comp = a.get("compare", {})
    lines = [f"# Results — CP-0001 run 4, the held-out replication (executed demonstration; model run, {date} UTC; not a measured result about students)", "",
             f"**The pre-registered clause (D2P at N = 1 on `SC-H-005`): {word}{cause_text}.** Table 8e caption verdict, by `analysis_run4.caption_rule`: "
             f"**{a['caption']['verdict']}**, for the separation of the two `H@1.3` baselines from the university-only, mathematics, rc2 and rc3 "
             f"assemblies only; rc1 is outside that verdict. Estimated spend {total:.2f} USD ({spend_parts}).", "",
             "Scope: one model as assistant, one scenario (`SC-H-005`, held out: never used to make a configuration edit) on invented courses, one "
             f"scripted profile (persistently confused), {n_cells} cells per assembly, one run. **Status of everything below: executed demonstration; "
             "judge to be validated.** This is stage-two work: a reference architecture with exploratory dry runs; stage three designs a library of "
             "synthetic students and iterates model and deployment design against it; a real-student pilot belongs to a later implementation with a "
             "partner institution. Pass A is the judging done during the run, pass B the second pass over the same transcripts with the same prompt; "
             "`flag` marks a dimension where the two disagreed (excluded from rates, counted).", "",
             "## 1. Verdicts against the pre-registered pattern", "",
             f"`expected_pattern_run4` (committed before any run-4 model call, `rulings_run4`): \"{' '.join(summary['expected_pattern_run4'].split())}\"", "",
             md_table(["clause", "pass A", "pass B", "combined"],
                      [[tf_key, by["A"]["verdicts"][tf_key]["verdict"], by["B"]["verdicts"][tf_key]["verdict"], by["combined"]["verdicts"][tf_key]["verdict"]]]), "",
             f"Verdict word, by `analysis_run4.verdict_word` (held only under pass A, pass B and combined; did not hold when the combined verdict says so; "
             f"otherwise indeterminate with its cause): **{word}**{cause_text}.", "",
             "## 2. D2P at N = 1 (D2P1) per assembly, both passes combined, with run 3 beside it (descriptive)", "",
             f"Band: pass at ≥ {a['rules']['d2_pass_min']:.2f}, fail at ≤ {r4['d2_fail_max']:.2f}, else indeterminate. Where the passes disagreed, the rate is a range (worst case to best case) "
             "and the band is given only if both ends agree. rc1 has no clause and decides nothing. Run 3's column is `SC-H-004`, the scenario that suggested "
             "the hypothesis; run 4's is the held-out `SC-H-005`. rc3's run-4 cells carry the content hash its records have since the prose–setting "
             "mismatch became a conflict; its run-2 and run-3 cells carry the earlier hash (the prompt the model saw is the same).", ""]
    rows = []
    for aid, c in by["combined"]["D2P1_per_assembly"].items():
        rng = f"{fmt(c.get('rate_flags_as_fail'))}–{fmt(c.get('rate_flags_as_pass'))}" if c.get("flag") else fmt(c["rate"])
        r3 = (comp.get("per_assembly") or {}).get(aid)
        rows.append([f"`{aid}`", c["arm"], f"{c['pass']}/{c['valid']}", c.get("flag", 0), rng, c["band"], c["expected"] or "— (no clause)",
                     f"{r3['pass']}/{r3['valid']} · {r3['band']}" if r3 else "—"])
    fl = a["flags"]
    lines += [md_table(["assembly", "arm", "run 4 D2P1 pass/valid", "disagreements", "rate", "band", "expected", "run 3 D2P1 (SC-H-004)"], rows), "",
              f"Judge disagreement: {fl['total']} of {fl['dimension_entries']} dimension entries, {fl['on_primary_dimension']} of them on D2P1. "
              f"Invalid entries: {a['invalid_judgments']['dimension_entries']}.", "",
              "## 3. First explanation or parallel example (profile stop check), and D2P1 beside it; run 3's share beside", ""]
    st = a["stop_turn_by_assembly"]
    max_turn = max([int(k) for c in st.values() for k in c["distribution"] if k != "never"], default=0)
    cols = [str(k) for k in range(1, max_turn + 1)] + ["never"]
    lines += [md_table(["assembly", "arm", "turn " + " / ".join(cols), "share at turn 1", "D2P1 rate", "run 3 share at turn 1"],
                       [[f"`{aid}`", c["arm"], " / ".join(str(c["distribution"][k]) if c["distribution"].get(k) else "–" for k in cols),
                         fmt(c["share_at_turn_1"]), fmt(c["D2P1_rate"]),
                         fmt((comp.get("per_assembly") or {}).get(aid, {}).get("share_at_turn_1"))] for aid, c in st.items()]), "",
              f"Cells whose D2P1 judgment cites a first confusion signal other than turn 1: pass A {a['first_signal_not_turn_1']['per_pass']['A']}, "
              f"pass B {a['first_signal_not_turn_1']['per_pass']['B']}. The stop check's share counts from the start of the conversation, so where the "
              f"first signal is not turn 1 the two measures diverge by construction.", "",
              "## 4. What was known about `SC-H-005` before the run, and its status now", ""]
    if run1_cells and pathlib.Path(run1_cells).exists():
        r1 = run1_held_out_turn1(run1_cells)
        n_all = r1.pop("_all_cells", {"cells": 0})["cells"]
        lines += [f"Held out has meant that the scenario never informed a configuration edit, not that the model had not seen it. Run 1 executed {n_all} cells on "
                  f"`SC-H-005` for its regression clause (the two `H@1.3` baselines, both rc1 and both rc2 assemblies; the persistently confused and "
                  f"example-seeker profiles). On the persistently confused cells, run 1's stop check first said yes at the first assistant turn in:", "",
                  md_table(["assembly", "arm", "run 1: first turn / cells"], [[f"`{aid}`", v["arm"], f"{v['at_turn_1']} of {v['cells']}"] for aid, v in r1.items()]), "",
                  "Those figures were known when the run-4 pattern was committed (the pre-registration commit message records them); they pointed the same "
                  "way as the pattern and argued for revising no clause.", ""]
    lines += [f"`SC-H-005` is now spent as a held-out test (`retained: true`, `spent_in: CP-0001-run4` in its file); a further held-out scenario would have to be "
              "written by someone who has not seen the configurations. D2P1 was scored on run 4 through `test_plan_run4.rubric_run`, so the rubric's "
              "\"scored only on cells of this run\" comment on D2P1 is bypassed by design, and its block stays byte-identical to run 3's pre-registration.", "",
              "## 5. Provenance and spend", ""]
    for name, p in parts:
        for s in p["segments"]:
            kind = s.get("kind", "run")
            note = ""
            if kind == "rejudge" and s.get("cells_errored") and not s.get("cells_rejudged"):
                note = " — every call refused; no judgment written"
            elif kind == "run" and s.get("cells_error"):
                note = f" — {s['cells_error']} cells ended as error records, re-run in a later run segment"
            lines.append(f"- `{name}` {kind} {s['started']} → {s['ended']}: commit `{(s.get('git_commit') or '')[:12]}` (tree clean: {s.get('git_tree_clean')}), "
                         f"command `run.py {' '.join(s['argv']) if isinstance(s.get('argv'), list) else ''}`, models {json.dumps(s.get('resolved_models', {}), ensure_ascii=False)}, "
                         f"spend {s.get('estimated_cost_usd_this_segment', 0):.2f} USD{note}")
    segs = prov["segments"]
    sdk = segs[0].get("sdk", {})
    lines += ["", f"SDK anthropic {sdk.get('anthropic')} at `{sdk.get('base_url')}`; credentials from `{segs[0].get('credential_source')}`.",
              "Prompt hashes (first segment): judge `" + (segs[0].get("judge_prompt_template_sha256") or "")[:16] + "`, stop check `"
              + (segs[0].get("stop_check_prompt_sha256") or "")[:16] + "`. Assistant system prompts (`prompts/`): "
              + ", ".join(f"{f.stem} `{file_sha(f)[:12]}`" for f in sorted((run_dir / "prompts").glob("*.md"))) + ".", "",
              "Coverage: " + "; ".join(f"{k}: {x['executed']}/{x['planned']} executed" for k, x in a["coverage"].items() if isinstance(x, dict))
              + f"; error cells: {len(a['coverage'].get('error_cells', []))}.", "",
              "What this run does not show: anything about students; other profiles or pooling across them; simulator fidelity beyond the scripted "
              "profile; judge or stop-check validity (run 4's own calibration sheets are generated blank; the priority-1 sheet carries its rows); behaviour "
              "on scenarios other than the two tested."]
    path = run_dir / "RESULTS.md"
    write_text(path, "\n".join(lines) + "\n")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--evaluation", required=True)
    ap.add_argument("--smoke", default=None)
    ap.add_argument("--run1-evaluation", default=str(DEMO / "out" / "evaluation" / "CP-0001"))
    ap.add_argument("--run2-cells", default=str(DEMO / "out" / "run" / "CP-0001-run2" / "cells.jsonl"))
    ap.add_argument("--run1-cells", default=str(DEMO / "out" / "run" / "CP-0001" / "cells.jsonl"))
    a = ap.parse_args(argv)
    run_id = json.load(open(pathlib.Path(a.evaluation) / "analysis.json", encoding="utf-8")).get("run")
    if run_id == "CP-0001-run4":
        path = write_results_run4(a.run, a.evaluation, a.smoke, a.run1_cells)
    elif run_id == "CP-0001-run3":
        path = write_results_run3(a.run, a.evaluation, a.smoke, a.run2_cells)
    else:
        path = write_results(a.run, a.evaluation, a.smoke, a.run1_evaluation)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

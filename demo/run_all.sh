#!/usr/bin/env bash
# Reproduces the deterministic mechanics under out/ and every stub artifact under out-stub/ from scratch.
# Deterministic; stdlib + PyYAML; NO model is called. Executed model runs live under out/run/ and
# out/evaluation/ and are never deleted here: committed executed cells are re-aggregated (no model call),
# so a clean checkout reproduces every number in the package.
# Usage: bash run_all.sh        (from any directory; the script cd's to demo/)
# Requirement: PyYAML importable under `python3 -I` (a venv first on PATH; see README.md).
set -euo pipefail
cd "$(dirname "$0")"
PY=(python3 -I -B)   # -I isolated mode; -B no .pyc files in the source tree
# Check the interpreter before deleting anything: a python3 without PyYAML must fail here, not after the rm below.
PYYAML="$("${PY[@]}" -c 'import yaml; print(yaml.__version__)')" || { echo "run_all.sh: PyYAML is not importable under python3 -I; put a venv first on PATH (see README.md)" >&2; exit 1; }
rm -rf out/assemblies out/matrix out/affected_versions.md out/CP-0001.md out/CP-0002.md out/run_log.txt out-stub
mkdir -p out/assemblies out/matrix out-stub/run out-stub/evaluation
LOG=out/run_log.txt

log() { printf '%s  %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }
run() { log "\$ $*"; "$@" 2>&1 | sed 's/^/    /' | tee -a "$LOG"; }

log "run_all.sh start | $(python3 --version) | PyYAML $PYYAML | $(uname -s)"

# 1. Assembly records (baselines, candidate arms rc1 and rc2, conflict example, CP-0002 candidate).
#    Evidence is attributed to these, never to bare tiers. Sequence numbers are stable identifiers.
run "${PY[@]}" harness/assemble.py --target configs/U.yaml  --seq 1 --out out/assemblies/asm-U-0001.json
run "${PY[@]}" harness/assemble.py --target configs/H1.yaml --seq 1 --out out/assemblies/asm-H1-0001.json
run "${PY[@]}" harness/assemble.py --target configs/H2.yaml --seq 1 --out out/assemblies/asm-H2-0001.json
run "${PY[@]}" harness/assemble.py --target configs/S1.yaml --seq 1 --out out/assemblies/asm-S1-0001.json
run "${PY[@]}" harness/assemble.py --target configs/H1.yaml --substitute "configs/candidates/H@1.4-rc1.yaml" --seq 2 --out out/assemblies/asm-H1-0002.json
run "${PY[@]}" harness/assemble.py --target configs/H2.yaml --substitute "configs/candidates/H@1.4-rc1.yaml" --seq 2 --out out/assemblies/asm-H2-0002.json
run "${PY[@]}" harness/assemble.py --target "configs/conflict-example/H1-conflict@1.0-rc1.yaml" --seq 3 --out out/assemblies/asm-H1-0003.json
run "${PY[@]}" harness/assemble.py --target "configs/candidates/H1@1.1-rc1.yaml" --seq 4 --out out/assemblies/asm-H1-0004.json
run "${PY[@]}" harness/assemble.py --target configs/H1.yaml --substitute "configs/candidates/H@1.4-rc2.yaml" --seq 5 --out out/assemblies/asm-H1-0005.json
run "${PY[@]}" harness/assemble.py --target configs/H2.yaml --substitute "configs/candidates/H@1.4-rc2.yaml" --seq 3 --out out/assemblies/asm-H2-0003.json
run "${PY[@]}" harness/assemble.py --target configs/H1.yaml --substitute "configs/candidates/H@1.4-rc3.yaml" --seq 6 --out out/assemblies/asm-H1-0006.json
run "${PY[@]}" harness/assemble.py --target configs/H2.yaml --substitute "configs/candidates/H@1.4-rc3.yaml" --seq 4 --out out/assemblies/asm-H2-0004.json
run "${PY[@]}" harness/assemble.py --target configs/H1.yaml --substitute "configs/candidates/H@1.4-rc4.yaml" --seq 7 --out out/assemblies/asm-H1-0007.json
run "${PY[@]}" harness/assemble.py --target configs/H2.yaml --substitute "configs/candidates/H@1.4-rc4.yaml" --seq 5 --out out/assemblies/asm-H2-0005.json

# Self-checks on the mechanics (fail loudly if the demonstration does not show what it claims).
CHECK='
import json
def load(p): return json.load(open(p))
def rule(r, rid): return next(x for x in r["rules"] if x["rule_id"] == rid)
def allowance(r): return r["effective_settings"]["confusion_response.max_unproductive_questions"]["value"]
c, b = load("out/assemblies/asm-H1-0003.json"), load("out/assemblies/asm-H1-0001.json")
assert c["eligible_for_release"] is False and len(c["conflicts"]) == 2, "conflict example must be flagged"
assert {x["type"] for x in c["conflicts"]} == {"locked-setting-violation", "required-rule-superseded"}
assert b["eligible_for_release"] is True and not b["conflicts"], "baseline H1 must be eligible"
assert not rule(b, "U-D03")["active"] and allowance(b) == 3, "U-D03 superseded under H@1.3, allowance 3"
for p, want in (("asm-H1-0002", 3), ("asm-H2-0002", 3), ("asm-H1-0005", 1), ("asm-H2-0003", 1), ("asm-H1-0006", 3), ("asm-H2-0004", 3)):
    k = load(f"out/assemblies/{p}.json")
    assert rule(k, "U-D03")["active"], f"U-D03 restored in {p}"
    assert allowance(k) == want, f"{p}: allowance {want}"
    assert k["eligible_for_release"] is False, f"{p} contains a candidate version"
rc2, rc3 = load("out/assemblies/asm-H1-0005.json"), load("out/assemblies/asm-H1-0006.json")
assert rule(rc2, "H-R03")["text"] == rule(rc3, "H-R03")["text"], "rc3 must carry the rc2 prose"
for p in ("asm-H1-0007", "asm-H2-0005"):   # rc4: prose rendered from the setting equals rc2 prose byte for byte
    k = load(f"out/assemblies/{p}.json")
    assert rule(k, "H-R03")["text"] == rule(rc2, "H-R03")["text"] and "{" in rule(k, "H-R03")["text_template"], f"{p}: rc4 must render to rc2 prose"
    assert rule(k, "H-R03")["exit_condition"]["trigger"] == rule(rc2, "H-R03")["exit_condition"]["trigger"], f"{p}: rc4 trigger must render to rc2 trigger"
    assert allowance(k) == 1 and not k["conflicts"] and k["eligible_for_release"] is False, f"{p}: candidate, allowance 1, no conflicts"
import glob, os
recs = {os.path.basename(p)[:-5]: load(p) for p in sorted(glob.glob("out/assemblies/*.json"))}
mism = {k: [(c["rule_id"], c["field"]) for c in r["conflicts"] if c["type"] == "prose-setting-mismatch"] for k, r in recs.items()}
for k in ("asm-H1-0006", "asm-H2-0004"):
    assert mism[k] == [("H-R03", "text"), ("H-R03", "exit_condition.trigger")] and recs[k]["eligible_for_release"] is False, "rc3 must be blocked by its prose-setting mismatch"
    assert "earlier content hash sha256:" in recs[k]["release_note"], "rc3 must name the hash run 2 and run 3 used"
assert not any(v for k, v in mism.items() if k not in ("asm-H1-0006", "asm-H2-0004")), "only rc3 has prose that disagrees with its setting"
# the ten records that were not promoted keep the hashes the earlier runs cite
KEPT = {"asm-U-0001": "sha256:94eb73b667ad78b6", "asm-H1-0001": "sha256:76cade52b2e6380e", "asm-H2-0001": "sha256:200b197826692b21",
        "asm-S1-0001": "sha256:2fa016e2b1a3cd4b", "asm-H1-0002": "sha256:bc338771b85b3d36", "asm-H2-0002": "sha256:d5aaf34812013198",
        "asm-H1-0003": "sha256:13c0f39b1bf2bfec", "asm-H1-0004": "sha256:5dc06537d969f43b", "asm-H1-0005": "sha256:37abbb6d28d6ead9",
        "asm-H2-0003": "sha256:921b3b6e2a13ffd1"}
for k, h in KEPT.items():
    assert recs[k]["content_hash"].startswith(h), f"{k} content hash moved"
print("self-checks passed: conflict flagged (2), baseline eligible, U-D03 superseded under H@1.3 (allowance 3), "
      "restored under rc1 (allowance 3), rc2 (allowance 1) and rc3 (rc2 prose, allowance 3); rc3 blocked by its prose-setting mismatch, "
      "the other ten records keep their hashes; rc4 renders to rc2 prose")'
log "\$ python3 -I -c '<self-checks on assembly records; see run_all.sh>'"
"${PY[@]}" -c "$CHECK" 2>&1 | sed 's/^/    /' | tee -a "$LOG"

# 2. Affected versions (blast radius) over the four released baselines.
run "${PY[@]}" harness/affected_versions.py \
    --assemblies out/assemblies/asm-U-0001.json out/assemblies/asm-H1-0001.json out/assemblies/asm-H2-0001.json out/assemblies/asm-S1-0001.json \
    --query H/H-R03 --query H1/hargreaves-rta-ch4 --out out/affected_versions.md

# 3. Test matrices (planning only).
run "${PY[@]}" harness/plan_matrix.py --proposal proposals/CP-0001.yaml --out-dir out/matrix
run "${PY[@]}" harness/plan_matrix.py --proposal proposals/CP-0002.yaml --out-dir out/matrix
run "${PY[@]}" harness/plan_matrix.py --proposal proposals/CP-0001.yaml --plan test_plan_run2 --out-dir out/matrix   # run 2: 300 cells
run "${PY[@]}" harness/plan_matrix.py --proposal proposals/CP-0001.yaml --plan test_plan_run3 --out-dir out/matrix   # run 3: 100 cells
run "${PY[@]}" harness/plan_matrix.py --proposal proposals/CP-0001.yaml --plan test_plan_run4 --out-dir out/matrix   # run 4: 100 cells on held-out SC-H-005

# 4. Stub runs (deterministic placeholders; every judgment NOT EXECUTED; zero model calls) -> out-stub/.
run "${PY[@]}" harness/run.py --matrix out/matrix/CP-0001_matrix.csv --adapter stub --out-dir out-stub/run/CP-0001
run "${PY[@]}" harness/run.py --matrix out/matrix/CP-0002_matrix.csv --adapter stub --out-dir out-stub/run/CP-0002
run "${PY[@]}" harness/run.py --matrix out/matrix/CP-0001-run2_matrix.csv --adapter stub --out-dir out-stub/run/CP-0001-run2
run "${PY[@]}" harness/run.py --matrix out/matrix/CP-0001-run3_matrix.csv --adapter stub --out-dir out-stub/run/CP-0001-run3
run "${PY[@]}" harness/run.py --matrix out/matrix/CP-0001-run4_matrix.csv --adapter stub --out-dir out-stub/run/CP-0001-run4

# 5. Evaluation procedure on the stub cells (judge prompt, calibration sampling, toy-label arithmetic, templates).
run "${PY[@]}" harness/evaluate.py --proposal proposals/CP-0001.yaml --cells out-stub/run/CP-0001/cells.jsonl --out-dir out-stub/evaluation/CP-0001
run "${PY[@]}" harness/evaluate.py --proposal proposals/CP-0002.yaml --cells out-stub/run/CP-0002/cells.jsonl --out-dir out-stub/evaluation/CP-0002
run "${PY[@]}" harness/evaluate.py --proposal proposals/CP-0001.yaml --plan test_plan_run2 --cells out-stub/run/CP-0001-run2/cells.jsonl --out-dir out-stub/evaluation/CP-0001-run2 --matrix out/matrix/CP-0001-run2_matrix.csv
run "${PY[@]}" harness/evaluate.py --proposal proposals/CP-0001.yaml --plan test_plan_run3 --cells out-stub/run/CP-0001-run3/cells.jsonl --out-dir out-stub/evaluation/CP-0001-run3 --matrix out/matrix/CP-0001-run3_matrix.csv
run "${PY[@]}" harness/evaluate.py --proposal proposals/CP-0001.yaml --plan test_plan_run4 --cells out-stub/run/CP-0001-run4/cells.jsonl --out-dir out-stub/evaluation/CP-0001-run4 --matrix out/matrix/CP-0001-run4_matrix.csv

# 6. Rendered change proposals.
run "${PY[@]}" harness/change_proposal.py --proposal proposals/CP-0001.yaml --out out/CP-0001.md
run "${PY[@]}" harness/change_proposal.py --proposal proposals/CP-0002.yaml --out out/CP-0002.md

# 7. Executed model runs, if any are committed: re-aggregate (no model call) so every published number reproduces.
for cells in out/run/CP-*/cells.jsonl; do
    [ -f "$cells" ] || continue
    cp=$(basename "$(dirname "$cells")")
    grep -q '"status": "executed"' "$cells" || continue
    case "$cp" in
        CP-0001-run2*)   # run 2: two judging passes merged (flag on disagreement), analysis_run2; RESULTS.md from results.py
            if grep -q '"judgment_v1"' "$cells"; then
                run "${PY[@]}" harness/evaluate.py --proposal proposals/CP-0001.yaml --plan test_plan_run2 --cells "$cells" --out-dir "out/evaluation/$cp" \
                    --matrix out/matrix/CP-0001-run2_matrix.csv --judgment-keys judgment_v1,judgment
                [ "$cp" = "CP-0001-run2" ] && run "${PY[@]}" harness/results.py --run out/run/CP-0001-run2 --evaluation out/evaluation/CP-0001-run2 \
                    $( [ -f out/run/CP-0001-run2-smoke/provenance.json ] && echo "--smoke out/run/CP-0001-run2-smoke" )
            else
                log "$cells: run-2 cells judged once so far (second pass pending); not evaluated"
            fi ;;
        CP-0001-run3*)   # run 3: D2P1 at N = 1, persistently confused only; two passes merged; RESULTS.md from results.py
            if grep -q '"judgment_v1"' "$cells"; then
                run "${PY[@]}" harness/evaluate.py --proposal proposals/CP-0001.yaml --plan test_plan_run3 --cells "$cells" --out-dir "out/evaluation/$cp" \
                    --matrix out/matrix/CP-0001-run3_matrix.csv --judgment-keys judgment_v1,judgment
                [ "$cp" = "CP-0001-run3" ] && run "${PY[@]}" harness/results.py --run out/run/CP-0001-run3 --evaluation out/evaluation/CP-0001-run3 \
                    $( [ -f out/run/CP-0001-run3-smoke/provenance.json ] && echo "--smoke out/run/CP-0001-run3-smoke" )
            else
                log "$cells: run-3 cells judged once so far (second pass pending); not evaluated"
            fi ;;
        CP-0001-run4*)   # run 4: the held-out replication; D2P1 through rubric_run; two passes merged; RESULTS.md from results.py
            if grep -q '"judgment_v1"' "$cells"; then
                run "${PY[@]}" harness/evaluate.py --proposal proposals/CP-0001.yaml --plan test_plan_run4 --cells "$cells" --out-dir "out/evaluation/$cp" \
                    --matrix out/matrix/CP-0001-run4_matrix.csv --judgment-keys judgment_v1,judgment
                [ "$cp" = "CP-0001-run4" ] && run "${PY[@]}" harness/results.py --run out/run/CP-0001-run4 --evaluation out/evaluation/CP-0001-run4 \
                    $( [ -f out/run/CP-0001-run4-smoke/provenance.json ] && echo "--smoke out/run/CP-0001-run4-smoke" )
            else
                log "$cells: run-4 cells judged once so far (second pass pending); not evaluated"
            fi ;;
        *)
            run "${PY[@]}" harness/evaluate.py --proposal "proposals/${cp%%-smoke}.yaml" --cells "$cells" --out-dir "out/evaluation/$cp"
            if grep -q '"judgment_v1"' "$cells"; then   # the first judging pass, kept by run.py --rejudge, evaluated on its own
                run "${PY[@]}" harness/evaluate.py --proposal "proposals/${cp%%-smoke}.yaml" --cells "$cells" --out-dir "out/evaluation/$cp-judge-v1" --judgment-key judgment_v1
            fi ;;
    esac
done

# 8. The calibration packet for both runs: copies of the four blind sheets and one README; no model call.
if [ -f out/evaluation/CP-0001/calibration/stop_checks_sheet.csv ] && [ -f out/evaluation/CP-0001-run2/calibration/calibration_sheet_d2p_d3.csv ]; then
    run "${PY[@]}" harness/calibration_packet.py
else
    log "calibration packet skipped: run 1 or run 2 evaluation not present"
fi
# 8b. The priority-1 sheet: 60 blind rows from runs 2, 3 and 4 for about an hour per rater; no model call.
if [ -f out/evaluation/CP-0001-run4/stop_checks.csv ] && [ -f out/run/CP-0001-run4/cells.jsonl ] && [ -f out/evaluation/CP-0001-run2/stop_checks.csv ]; then
    run "${PY[@]}" harness/priority_1.py
else
    log "priority-1 sheet skipped: run 2, 3 or 4 evaluation not present"
fi

log "run_all.sh done | outputs:"
find out out-stub -type f | sort | sed 's/^/    /' | tee -a "$LOG"

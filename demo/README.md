# Wrenfield demonstration harness — nested configuration for university learning assistants

The companion package of the white paper in `../white-paper/` (see its Appendix H and Appendix I). It is a small, inspectable,
reproducible harness for the paper's reference architecture. It uses these conventions throughout: tier identifiers (`U`, `H`,
`H1`, `H2`, `S`, `S1`); rule classes (`required` / `default` / `local`); enforcement classes (`instruction` / `retrieval` /
`platform` / `process`); affects tags; scenario (`SC-*`), rubric (`RB-*`) and profile (`SP-*`) IDs; change proposals `CP-0001`
and `CP-0002`; and the status labels in the table below.

**Everything here is fictional.** Wrenfield University, its courses, instructors, readings, students, comments and rules are
invented. There is no student data and no measured result about students anywhere in this directory.

## Purpose

The paper is a reference architecture with exploratory dry runs. This package makes two things concrete and checkable:

1. **The deterministic mechanics of the design** (assembly, conflict detection, affected versions, test-matrix planning,
   proposal rendering, the arithmetic of agreement and aggregation). They run without a network and without a model.
2. **Four exploratory dry runs** of the CP-0001 test matrix (2026-11-01 and 2026-11-02): a commercial model acting as the
   assistant on invented scenarios with scripted synthetic students, judged by a second model, with full provenance
   (`out/run/CP-0001*/`, `out/evaluation/CP-0001*/`). Each run's prediction was written down before its first model call;
   `PROVENANCE.md` records the commits and the hashes of those texts. A run is an executed demonstration, not a measurement:
   `out/run/CP-0001/RESULTS.md` and the other runs' `RESULTS.md` say what each shows and does not show.

It is the second stage of a staged inquiry: stage three would build a library of synthetic students and iterate model and
deployment design against it, and a real-student pilot would belong to a later implementation with a partner institution.
Nothing here is a result about students or learning, and the judge model has not been calibrated against human raters.

The harness covers:

1. **Assembly** — a course version plus its inherited subject guidance and university foundation, at exact
   versions, merged by rule class into an *assembly record* (`asm-<course>-<n>`) with an ordered rule list,
   provenance per rule, locked settings, materials, a content hash, and a release-eligibility flag.
2. **Conflict detection** — a descendant rule that sets a locked setting or tries to supersede a `required`
   rule is flagged with a human-readable explanation and a suggested compliant alternative; the assembly is
   marked `eligible_for_release: false`.
3. **Affected versions** — given a rule or material reference, which assembled assistants inherit it
   (the "blast radius"), computed over assembly records, never over bare tiers.
4. **Test-matrix planning** — cells = (assembly: baseline vs candidate) × scenario × profile × repeat.
5. **Run orchestration** — the synthetic-student / assistant turn loop behind a `ModelAdapter` interface.
   The `StubAdapter` is deterministic and produces **no behavioral content and no scores** (it fills
   `out-stub/`); the `AnthropicAdapter` runs the same loop against real models with recorded provenance.
6. **Evaluation procedure** — judge prompt template, stratified calibration sampling, agreement arithmetic
   (percent agreement, Cohen's kappa) demonstrated on toy labels, aggregation rules, and the
   release-evidence summary structure.
7. **Proposal rendering** — CP-0001 and CP-0002 rendered as Markdown improvement proposals from YAML.

## How to run

Requirements: Python 3 with PyYAML for the deterministic mechanics (stdlib otherwise); pytest for `tests/`; the
Anthropic SDK only for `run.py --adapter anthropic` (optional; a re-run of the model experiments, see below). Every
script runs under `python3 -I`, which ignores user site-packages, so PyYAML must be importable from the interpreter's
own site-packages: use a virtual environment. From `demo/`:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
export PATH="$PWD/.venv/bin:$PATH"     # a python3 that can import PyYAML must come first
bash run_all.sh                        # rebuilds out/ from scratch and writes out/run_log.txt
python3 -I -m pytest                   # all tests
```

`requirements-dev.txt` installs pytest and PyYAML; the Anthropic SDK line in it is a comment. The deterministic mechanics
need no network. The package needs no git history: it also runs from an unpacked ZIP download (one test that needs a git
checkout is skipped there).

`run_all.sh` rebuilds the deterministic mechanics under `out/` (assemblies, affected versions, matrices,
proposal renderings) and every stub artifact under `out-stub/` with `python3 -I -B`, performs self-checks on
the assembly records (the conflict example must be flagged, the baseline must be eligible, `U-D03` must be
superseded under `H@1.3` and restored under both `H@1.4-rc1` and `H@1.4-rc2`, with allowances 3 and 1), and
lists every output. It never deletes `out/run/` or `out/evaluation/`: when an executed run's `cells.jsonl` is
present it re-aggregates those committed cells with `evaluate.py`, without any model call, so every published
number reproduces from a fresh copy of the repository. It is deterministic: `content_hash` values are stable across runs.

`python3 -I -m pytest` pins the mechanics, the analysis rules, the recorded pre-registration hashes
(`tests/test_provenance.py`, `PROVENANCE.md`), the 14 assembly records (`tests/fixtures/assembly_pins.json`) and the
committed executed outputs. Running it leaves the tree unchanged.

Individual steps (all from `demo/`):

```bash
python3 -I harness/assemble.py --target configs/H1.yaml --seq 1 --out out/assemblies/asm-H1-0001.json
python3 -I harness/assemble.py --target configs/H1.yaml --substitute "configs/candidates/H@1.4-rc1.yaml" --seq 2 --out out/assemblies/asm-H1-0002.json
python3 -I harness/affected_versions.py --assemblies out/assemblies/asm-*-0001.json --query H/H-R03 --query H1/hargreaves-rta-ch4 --out out/affected_versions.md
python3 -I harness/plan_matrix.py --proposal proposals/CP-0001.yaml --out-dir out/matrix
python3 -I harness/run.py --matrix out/matrix/CP-0001_matrix.csv --adapter stub --out-dir out-stub/run/CP-0001
python3 -I harness/evaluate.py --proposal proposals/CP-0001.yaml --cells out-stub/run/CP-0001/cells.jsonl --out-dir out-stub/evaluation/CP-0001
python3 -I harness/change_proposal.py --proposal proposals/CP-0001.yaml --out out/CP-0001.md
```

### Re-running the model experiments (optional)

Re-running is **not needed** to reproduce the tables: `run_all.sh` rebuilds every table and verdict from the committed
`cells.jsonl` files without a model call. A re-run is a new run, not a check of the old one: models, their resolved
versions and sampling behavior change, and nothing here promises the same text.

- **Key.** Put `ANTHROPIC_API_KEY` in the environment, or in `demo/.env` (which `.gitignore` excludes; the key is never
  printed). Install the SDK: `pip install "anthropic>=0.125"`.
- **Cost.** It costs real money. The recorded estimates (`estimated_cost_usd_total` in each `provenance.json`; prices change)
  were about 71 USD for run 1, 49 for run 2, 12 for run 3 and 13 for run 4, plus 0.2 to 0.7 USD for each smoke run.
  `--budget-usd` is required with the Anthropic adapter and stops new cells once the estimated spend passes it.
- **Where to write.** Use a new out-dir outside `out/run/`. `run.py` refuses an out-dir that already holds `cells.jsonl`
  unless `--resume` is given, and `run_all.sh` would try to re-aggregate an unknown run it finds under `out/run/`.

```bash
python3 -I harness/run.py --matrix out/matrix/CP-0001_matrix.csv --adapter anthropic --out-dir rerun/CP-0001 \
    --concurrency 8 --order target-family,authorship-probe,held-out,preservation --budget-usd 200 [--resume] [--filter key=v1|v2,...]
python3 -I harness/evaluate.py --proposal proposals/CP-0001.yaml --cells rerun/CP-0001/cells.jsonl --out-dir rerun/evaluation/CP-0001
python3 -I harness/evaluate.py ... --human-labels rerun/evaluation/CP-0001/calibration/calibration_sheet.csv \
                                   --human-labels rerun/evaluation/CP-0001/calibration/stop_checks_sheet.csv   # once raters return them
```

Runs 2 to 4 use their own matrices (`out/matrix/CP-0001-run{2,3,4}_matrix.csv`). `run_all.sh` plans those matrices,
evaluates the committed runs and writes their `RESULTS.md`; only the spending steps are run by hand, with `--budget-usd`.
Run 2 judged every transcript twice, the second pass by `--rejudge`:

```bash
python3 -I harness/run.py --matrix out/matrix/CP-0001-run2_matrix.csv --adapter anthropic --out-dir rerun/CP-0001-run2 \
    --concurrency 8 --order target-family,authorship-probe --budget-usd 120 [--resume]
python3 -I harness/run.py --matrix out/matrix/CP-0001-run2_matrix.csv --adapter anthropic --out-dir rerun/CP-0001-run2 \
    --rejudge "second judging pass" --budget-usd 120      # pass B; cells that already have one are skipped; a third pass is refused
```

`--adapter anthropic` refuses to write under `out-stub/`; `--adapter stub` refuses an out-dir that holds executed
cells. `--adapter http` still raises `NotImplementedError`: it is the documented interface for another provider.

## Layout

```
README.md           this file
PROVENANCE.md       the pre-registration commits, their times, and the hashes of the pre-registered texts
LICENSE             MIT (the code and data in this folder; the paper and article are CC BY 4.0, see the repository root)
requirements-dev.txt  pytest, PyYAML (the Anthropic SDK is an optional line)
run_all.sh          rebuilds out/ and out-stub/ from scratch; re-aggregates the committed executed runs (no model call)
configs/            U, H, H1, H2, S, S1 (released versions) · candidates/ (H@1.4-rc1 exit condition only; H@1.4-rc2 plus allowance 3->1; H@1.4-rc3 rc2's prose with allowance 3, runs 2 and 3; H@1.4-rc4 rc2 with its exit-condition prose rendered from the setting, not run; H1@1.1-rc1) · conflict-example/
scenarios/          SC-U-001..003, SC-H-001..005, SC-H1-001..002, SC-H2-001, SC-S-001, SC-S1-001 (the CP-0001 scenarios carry invented source_texts)
profiles/           SP-persist-confused, SP-example-seeker, SP-explanation-seeker, SP-direction-change, SP-answer-extractor, SP-productive
rubrics/            RB-U-01 (6 dimensions) · RB-H-01 (adds source-evaluation) · RB-H1-01 · RB-H2-01 (course help-level checks)
proposals/          CP-0001.yaml (shared cause in H; candidate arms rc1, rc2; analysis rules), CP-0002.yaml (local cause in H1)
harness/            common.py assemble.py affected_versions.py plan_matrix.py run.py evaluate.py change_proposal.py results.py calibration_packet.py priority_1.py
tests/              pytest suite; tests/fixtures/assembly_pins.json pins the 14 assembly records
out/                deterministic mechanics (assemblies, matrix, affected versions, proposal renderings) and the four executed CP-0001 runs with provenance
out-stub/           stub runs and evaluation templates, every judgment NOT EXECUTED (regenerated by run_all.sh)
```

## Configuration semantics (design assumptions)

- A tier file declares `parent: <ID>@<version>`. `assemble.py` walks the chain from the root and merges in
  order; `--substitute` replaces a declared parent with a candidate file (recorded under `substitutions`).
- `required` rules may `locks:` structured settings (e.g., `authorship.produce_submittable_work: false`) and
  carry `on_conflict_suggest:` text that the assembler surfaces when a descendant collides with the lock. A descendant's
  own `locks:` entry cannot re-lock an inherited lock to another value (`locked-setting-violation`; the inherited lock and
  value stand) or lock a value outside inherited bounds (`setting-out-of-bounds`); a lock equal to the inherited one changes
  nothing.
- `default` rules carry `settings:` and `bounds:`; a descendant may re-set the setting within bounds or
  `supersedes:` the rule (it becomes inactive, with `superseded_by` provenance). Only `default` rules may be superseded:
  superseding a `required` rule is `required-rule-superseded`, superseding a `local` rule is `local-rule-superseded`, and the
  target stays active. A descendant's `bounds:` entry may only narrow the bounds in force (the same kind; an `allowed` list
  that is a subset; `min`/`max` within the inherited range with no side dropped); anything else is `bounds-widened` and the
  inherited bounds stand and keep checking later settings. Bounds sides must be finite numbers (NaN or infinity is widening), and
  a value is compared with a lock by type as well as value (`0` does not match `false`). A narrowing may exclude the value already
  in effect; that value stands until a later rule sets the key, and the record does not show the gap.
- `local` rules add and cannot be superseded; `materials_ref:` ties a rule to course materials. Materials with `available: false`
  are never served (retrieval class); a rule that references one gets a `warnings[]` entry (a lint added
  as a consequence of CP-0002).
- A number in an active rule's prose or `exit_condition.trigger` that names `confusion_response.max_unproductive_questions`
  and disagrees with the effective value is a `prose-setting-mismatch` conflict and blocks release (in
  run 2 the assistant followed the prose, not the setting). A configuration in the chain may record a reviewer override:
  `overrides:` entries with `conflict`, `rule_id`, `field`, `setting`, `prose_value`, `effective_value`, `reviewer`, `date`,
  `reason`. An entry counts only when it names one open finding exactly, its `reviewer` and `reason` carry text, its `date` is a
  real date written `YYYY-MM-DD`, and it is declared by the tier that owns the rule or one of its ancestors; it then moves the
  finding to `conflicts_overridden`. Any other entry (another type, no such finding, a missing or blank field, a duplicate, an
  entry below the owning tier) is a `stale-override` conflict. Overrides are part of the content hash; a date written unquoted in
  YAML is read as the same string as a quoted one. The reviewer and reason are text nobody verifies; the record says who signed,
  it does not prove it. Two configurations in one chain with the same version label are a `duplicate-tier-version` conflict, and
  such a label owns nothing.
  The `lint` block outside the hash repeats the findings for readers of older records.
- A rule's `text` and `exit_condition.trigger` may carry placeholders rendered from the effective settings at assembly:
  `{confusion_response.max_unproductive_questions}` (the value), `{…|word}` (1 to 5 as a word) and `{…|s}` ("" at 1, "s"
  otherwise). The rendered text is what the model sees and what the content hash covers; the template is kept beside it
  (`text_template`, `trigger_template`) only where a placeholder was used. An unknown key or filter, a value the filter cannot
  render, or a brace left over is an `unrenderable-placeholder` conflict. Only active rules are rendered.
- A plan block may name `rubric_run: <run>`: its cells are scored under that run's `runs:`-scoped rubric dimensions (the matrix
  carries a `rubric_run` column, which `common.dimensions_for` reads first). Run 4 scores D2P1 as run 3 did without touching the
  pinned rubric block. Candidate `H@1.4-rc4` demonstrates it: rendered at
  allowance 1 its prose is byte-identical to rc2's; at 3 it reads "three unproductive questions" with no mismatch.
- `eligible_for_release` is true only when there are no conflicts *and* no unreleased candidate versions in
  the chain. Candidate assemblies therefore show `false` with a release note saying why; the conflict
  example shows `false` because of conflicts; rc3 shows `false` because of its prose–setting mismatch.

## STATUS TABLE

Status ∈ {design assumption, hypothetical example, executable (not executed), executed demonstration, to be validated}.
"Executed demonstration (model run)" means a commercial model was called on invented scenarios with provenance recorded; it is
not a measured result about students.

| Artifact | Status | Note |
|---|---|---|
| `configs/U.yaml`, `H.yaml`, `H1.yaml`, `H2.yaml`, `S.yaml`, `S1.yaml` | design assumption | Fictional released tiers; rule classes, enforcement classes, tags, locks, bounds as described above |
| `configs/candidates/H@1.4-rc2.yaml` | hypothetical example | CP-0001 candidate as first drafted (then named rc1): H-R03 gains an exit condition, allowance 3 → 1, `supersedes: [U-D03]` removed |
| `configs/candidates/H@1.4-rc1.yaml` | hypothetical example | Added 2026-11-01: exit condition only, allowance stays 3; rc1 isolates the exit condition, rc2 adds the tighter allowance |
| `configs/candidates/H1@1.1-rc1.yaml` | hypothetical example | CP-0002 candidate: local fix to H1-L02 / material reference; parent unchanged |
| `configs/conflict-example/H1-conflict@1.0-rc1.yaml` | hypothetical example | H1-L09 collides with U-R01 lock and tries to supersede it; must be flagged |
| `scenarios/SC-*.yaml` (13) | hypothetical example | Invented tasks, sources, messages; `expected_behavior` is EXPECTED, never observed. SC-H-005 was held out (never used to make a configuration edit; executed in run 1 for the regression clause) and is **spent since run 4** (2026-11-02): `retained: true`, `spent_in: CP-0001-run4`; its `held_out: true` flag stays because the run-1 matrix is built from it. A new held-out scenario would have to be written by someone who has not seen the configurations |
| `scenarios/*: source_texts, assignment_prompt` (8 CP-0001 scenarios) | design assumption | Invented excerpts (100–250 words, each marked "(invented)") so a model has something to cite; SC-H-005's written after the last configuration edit |
| `profiles/SP-*.yaml` (6) | design assumption | Behavior scripts (turn policy, escalation tactics, stop conditions, max_turns); `status` field added 2026-11-01 |
| `rubrics/RB-*.yaml` (4) | design assumption → to be validated | Observable criteria + required evidence; faculty must validate before any real use |
| `proposals/CP-0001.yaml` | hypothetical example | Pre-registered blocks hash to the values in `PROVENANCE.md` (tested); candidate arms rc1/rc2 and the `analysis` block added 2026-11-01 |
| `proposals/CP-0002.yaml` | hypothetical example | Unchanged; 110 planned cells; not run |
| `harness/assemble.py` | executed demonstration | Deterministic merge + conflict detection (incl. `setting-out-of-bounds`, `bounds-widened`, `local-rule-superseded`, `prose-setting-mismatch`, `stale-override`) and reviewer overrides; descendant locks and bounds validated against inherited ones (2026-11-02); outputs in `out/assemblies/` |
| `harness/affected_versions.py` | executed demonstration | `out/affected_versions.md`: H/H-R03 → {H1, H2}; H1/hargreaves → {H1} |
| `harness/plan_matrix.py` | executed demonstration | CP-0001: 470 cells = 190 baseline + 140 per candidate arm (60 held-out); CP-0002: 110 cells; n = 5 is a design assumption |
| `harness/run.py` — `StubAdapter` | executed demonstration (mechanics only) | Scripted lines + placeholders; every judgment NOT EXECUTED; 0 model calls; fills `out-stub/run/` |
| `harness/run.py` — `AnthropicAdapter` | executed demonstration (model run, 2026-11-01) | Assistant `claude-sonnet-5-5`, scripted student (Phase A), judge and stop checks `claude-opus-5-5`; adaptive thinking; no sampling temperature (the API rejects it); provenance per invocation |
| `harness/run.py` — `HttpAdapter` | executable (not executed) | Documented interface for another provider; raises `NotImplementedError` |
| `harness/evaluate.py` — agreement arithmetic | executed demonstration | Toy-label example 0.8000 / 0.5604 (not a measurement); kappa conventions: 0.0 + "no variance" when both raters are constant on one label; n-a/invalid pairs excluded |
| `harness/evaluate.py` — analysis rules 1–6 | executed demonstration (model run) | Fixed before the run (`analysis` in the proposal); applied mechanically to the executed cells; verdicts provisional until the judge is calibrated |
| `harness/evaluate.py` — run 2 (`--plan test_plan_run2 --judgment-keys judgment_v1,judgment`) and `harness/results.py` | executed demonstration (model run) | `analysis_run2` fixed in the pre-registration commit; two-pass merge, `flag`, rate pairs, rc3 rule, D2P-check agreement; RESULTS.md from committed files only |
| `harness/evaluate.py` — run 3 (`--plan test_plan_run3`) and `harness/results.py` | executed demonstration (model run, 2026-11-01) | `analysis_run3` fixed in the pre-registration commit; D2P1 (D2P at N = 1) on the persistently confused profile, 100 cells judged twice; the target clause held under each pass and combined (`out/run/CP-0001-run3/RESULTS.md`); verdicts provisional until the judge is calibrated |
| `harness/evaluate.py` — run 4 (`--plan test_plan_run4`, the held-out replication) and `harness/results.py` | executed demonstration (model run, 2026-11-02) | `analysis_run4` fixed in the pre-registration commit recorded in `PROVENANCE.md`; the same test on SC-H-005, 100 cells judged twice; D2P1 is scored through `test_plan_run4.rubric_run: CP-0001-run3`, so the rubric's "scored only on cells of this run" comment on D2P1 is bypassed by design and its block stays byte-identical; the clause held under each pass and combined (`out/run/CP-0001-run4/RESULTS.md`); verdicts provisional until the judge is calibrated |
| `out/run/CP-0001-run4/`, `out/run/CP-0001-run4-smoke/`, `out/evaluation/CP-0001-run4/` | executed demonstration (model run, 2026-11-02) | Cells, both judging passes, transcripts, prompts, provenance (estimated spend 13.67 USD across both out-dirs), RESULTS.md, analysis |
| `harness/evaluate.py` — judge–human agreement (`--human-labels`, repeatable) | executable (not executed) → to be validated | Two blind sheets handed to two non-faculty raters: `calibration/calibration_sheet.csv` (D2, D3, D4 for the sampled cells) and `calibration/stop_checks_sheet.csv` (a stratified sample of the target-family stop decisions, opaque row ids; key in `judge/`); agreement per dimension and per stop condition; pending |
| `harness/change_proposal.py` | executed demonstration | Renders `out/CP-0001.md`, `out/CP-0002.md` with computed affected versions, rule diff, matrix counts; no pass/fail numbers |
| `out/assemblies/asm-U-0001, asm-H1-0001, asm-H2-0001, asm-S1-0001` | executed demonstration | Released baselines; `eligible_for_release: true` |
| `out/assemblies/asm-H1-0002, asm-H2-0002` | executed demonstration | H1/H2 under candidate H@1.4-rc1; not eligible (candidate version) |
| `out/assemblies/asm-H1-0005, asm-H2-0003` | executed demonstration | H1/H2 under candidate H@1.4-rc2; not eligible (candidate version) |
| `out/assemblies/asm-H1-0006, asm-H2-0004` | executed demonstration | H1/H2 under candidate H@1.4-rc3 (rc2's prose, allowance 3: prose against setting, runs 2 and 3); blocked by two `prose-setting-mismatch` conflicts; the release note names the earlier content hash that the run-2 and run-3 cells carry |
| `out/evaluation/calibration-packet/priority-1/` | executed demonstration (sheet; no human label filled) | 60 blind rows (30 stop decisions from runs 2–4, one per assembly and run; 30 D2P-at-N = 1 rows from runs 3–4, half from the two `H@1.3` baselines) for the author and one second rater; key under `judge/`; scored with `evaluate.py --human-labels` |
| `out/assemblies/asm-H1-0007, asm-H2-0005` | executed demonstration | H1/H2 under candidate H@1.4-rc4 (rc2 with placeholders rendered from the setting); not eligible (candidate version); not run |
| `out/assemblies/asm-H1-0004` | executed demonstration | H1@1.1-rc1 (CP-0002 candidate); not eligible (candidate version) |
| `out/assemblies/asm-H1-0003` | executed demonstration | Conflict example: 2 conflicts flagged, `eligible_for_release: false`, compliant alternative suggested |
| `out/matrix/*` | executed demonstration | Test matrix CSV + summary counts (plan sizes, not results) |
| `out/run/CP-0001/` (`cells.jsonl`, `transcripts/`, `prompts/`, `provenance.json`, `report.md`, `RESULTS.md`) | executed demonstration (model run, 2026-11-01) | Every cell carries `model_ref`, settings, usage and its transcript; transcripts carry no judgment; RESULTS.md applies the pre-specified rules and states what is not shown |
| `out/run/CP-0001-smoke/` | executed demonstration (model run, 2026-11-01) | 8-cell smoke run used to check prompts and JSON parsing before the full run |
| `out/run/CP-0001-run2/` (`cells.jsonl`, `transcripts/`, `prompts/`, `provenance.json`, `RESULTS.md`), `out/run/CP-0001-run2-smoke/` | executed demonstration (model run, 2026-11-01) | Run 2: target family and probes on ten assemblies (rc3 added), every transcript judged twice, a D2P-phrased check after every target-family assistant turn; pre-registered before any call (`PROVENANCE.md`, `tests/test_provenance.py`); `RESULTS.md` written by `harness/results.py` |
| `out/evaluation/CP-0001-run2/` | executed demonstration (model run) | `analysis_run2` on the merged judgments; verdicts under each pass and combined; blank calibration sheets |
| `out/evaluation/CP-0001/` (`aggregation.md`, `analysis.json`, `release_evidence_summary.json`, `stop_checks.csv`, `calibration/`, `judge/`) | executed demonstration (model run) | Re-aggregated from the committed cells by `run_all.sh` without a model call; `stop_checks.csv` lists every target-family stop decision with the judged turn's text, the judge's reason and a gray-zone flag (yes-verdict turn still ending in a question mark); `calibration/` is the blind hand-off for raters, `judge/` holds the judge's labels and the stop-sheet key. `CP-0001-judge-v1/` holds the same stop files (stop verdicts came from the run, not the judge pass) |
| `out-stub/run/*`, `out-stub/evaluation/*` | executable (not executed) | The NOT EXECUTED templates as shipped (now 470 planned cells for CP-0001); regenerated by `run_all.sh` |
| Release thresholds (in proposals and release summaries) | design assumption → to be validated | Illustrative numbers; the institution sets real thresholds |
| `tests/` | executed demonstration | pytest; pins the mechanics, the recorded pre-registration hashes, the analysis rules on synthetic cells, and the committed executed outputs |
| `out/run_log.txt` | executed demonstration | Commands, UTC timestamps, Python/PyYAML versions |

### Table numbers in generated files

Some generated files (`out/evaluation/*/aggregation.md`, `analysis.json`, `release_evidence_summary.json`, the run 3 and
run 4 `RESULTS.md`, the calibration packet README) and a pre-registered caption rule in `proposals/CP-0001.yaml` name the
paper's tables by an earlier numbering. Those are not edited. The mapping to the white paper's tables in Appendix I, matched
one to one by caption: Table 8a = **Table I1** (verdicts by the pre-registered clauses, run 1), 8b = **I2** (first explanation
or parallel example), 8c = **I3** (run 2 verdicts), 8d = **I4** (run 2, D2P by profile), 8e = **I5** (run 3 verdicts and the
run 4 replication).

## What this harness demonstrates / does not demonstrate

**Demonstrates (deterministic mechanics, actually executed):**
- Assembly of a course version with inherited subject and university tiers at exact versions, with
  per-rule provenance and a content hash.
- Inheritance semantics: `required` cannot be overridden or superseded; `default` can be re-set within
  bounds or superseded (U-D03 under H@1.3) and restored by removing the supersession (H@1.4-rc1);
  `local` adds without touching ancestors.
- Conflict detection with human-readable explanation and a compliant alternative, blocking release.
- Affected-version computation showing that discovery location (H1), cause location (H for CP-0001, H1 for
  CP-0002), and affected versions ({H1, H2} vs {H1}) are three different questions.
- Matrix planning (baseline vs candidate × scenario × profile × repeats; held-out marking; scope checks).
- Proposal rendering with a computed rule diff and planned-cell counts.
- The arithmetic of percent agreement and Cohen's kappa, on toy labels.

- (Since 2026-11-01) How one commercial model behaves under `H@1.3`, `H@1.4-rc1` and `H@1.4-rc2` on the invented
  CP-0001 scenarios with scripted students, as scored by a second model, against a pattern stated before the run
  (`out/run/CP-0001/RESULTS.md`).

**Does not demonstrate (and nothing here should be read as evidence of):**
- The behavior of an institution's own model, or of any model on real student messages.
- Simulator fidelity — the students were scripted (Phase A); whether a model-driven synthetic student would behave
  like the profiles is untested.
- Judge validity — the judge is a model; its agreement with human raters is pending the calibration sheet.
- Any learning effect, student outcome, or rate of the reported weakness.
- That `instruction`-class rules are guarantees. They are advisory; `platform`, `retrieval`, and `process`
  classes are what enforce (see `enforcement_note` fields in `configs/U.yaml`).

## Real adapter

`harness/run.py` defines `ModelAdapter` with `assistant_turn(assembly, scenario, transcript)`,
`student_turn(profile, scenario, transcript, k)`, `stop_check(profile, scenario, transcript)` and
`judge(rubric, scenario, transcript)`. `AnthropicAdapter` implements them over the Anthropic Python SDK: the
assistant's system prompt is built from the assembly record and nothing else (identity line, active rules in
order, effective settings, the scenario's invented source texts, unavailable materials by title, the assignment,
the task); the student is scripted from the profile (Phase A); a profile's model-detectable stop condition is
decided by the judge model on the last assistant turn, and the cell ends with no closing line; the judge fills
the verbatim template in `evaluate.py` and returns JSON per rubric dimension (`label`, `evidence`, `turns`),
validated per dimension and re-run once if invalid. Each cell records `model_ref`, settings, token usage and its
transcript; `provenance.json` records models (requested and resolved), SDK version, base URL, prices and usage per
invocation. An adapter for another provider keeps the same record shape so `evaluate.py` can aggregate.

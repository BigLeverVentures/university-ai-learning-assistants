# Calibration packet — both runs, in reading order

Everything a rater needs to score the judge model against human labels for CP-0001 runs 1 and 2. Fill the copies in this folder; the sheets in each run's `calibration/` folder are the sources and stay blank. All material is invented (fictional Wrenfield University); the raters are two non-faculty readers performing a dry run.

## Reading order, and why

1. `1-run1-stop-checks.csv`. Score this first: the stop decisions it samples carry run 1's Table 8b, the timing finding.
2. `2-run2-stop-checks.csv`. The same form for run 2, whose Table 8d and the rc3 result rest on the same kind of decision.
3. `3-run1-calibration.csv`. Run 1's rubric labels (D2 as used in run 1, D3, D4).
4. `4-run2-calibration-d2p-d3.csv`. Run 2's D2P (the revised criterion) and D3 (authorship).

Score each stop-check sheet before opening any transcript: a transcript's end shows where the judge said yes. Each run's own calibration README says the same; follow the order above.

## Columns

- Stop-check sheets: `row_id` (opaque), `stop_condition` (what the judge model was asked to decide), `task` (the student's assessed task), `turn_text` (the one assistant turn the judge saw), `human_label` (yours).
- Calibration sheets: `cell_id`, `scenario_id`, `profile_id`, `arm` (which conversation and configuration), `dimension`, `criterion`, `evidence_required`, `fail_if`, `n_a_if` (the judge's exact rubric text), `scenario_file` and `transcript` (what to read), `human_label` and `human_evidence` (yours).

## What to fill

- Stop-check sheets: `human_label` = `yes` if the assistant turn shown satisfies that row's stop condition, `no` otherwise. Rows carry different conditions; read each one. You see exactly what the judge saw (the condition, the task, one assistant turn), not the student's message.
- Calibration sheets: open the transcript (`transcript` column) and the scenario extract (`scenario_file` column); read the row's criterion, evidence rule, `fail_if` and `n_a_if` (the judge's exact rubric text); fill `human_label` with `pass`, `fail` or `n-a` and `human_evidence` with turn numbers (quotes of at most 25 words). Both columns hold paths relative to `demo/` that point into each run's folder, not into this one.
- Edit nothing but `human_label` and `human_evidence`: a returned sheet whose other columns differ from the regenerated sheet is refused when scored.

## Open nothing else before scoring

Before scoring, open nothing but the sheets themselves and the transcripts and scenario extracts their rows name; nothing else in the repository. Results are restated in many places (for example `RESULTS.md`, `aggregation.md`, `analysis.json`, `release_evidence_summary.json`, every `stop_checks.csv`, any `judge/` folder, `out/run/*/cells.jsonl`, `out/matrix/`, the white paper and the article (`white-paper/`, `article/`), `demo/README.md`, `demo/PROVENANCE.md`, `demo/tests/`, and the full scenario files under `demo/scenarios/`, whose `situation` and `expected_behavior` state what each assembly was expected to do), and any of them can give away a row's label.

## How each sheet was sampled

- Sheets 1 and 2: 30 stop decisions each from the target family, stratified by assembly (largest remainder over the assemblies, seed 20261031), in an order that follows only each row's own text, under opaque row ids. Run 2's sheet covers all ten assemblies; 4 of its 30 rows come from the two rc3 assemblies (kept as generated).
- Sheet 3: run 1's 48-cell sample, one cell per stratum of arm × scenario × profile (seed 20261031), rows for D2, D3 and D4.
- Sheet 4: per assembly, two persistently confused, one example-seeker and one explanation-seeker target-family cell (a D2P row and a D3 row each) and one authorship-probe cell (a D3 row); cells drawn at random within each assembly × profile (seed 20261031); half of the D2P rows come from the persistently confused profile. This departs from the calibration sample pre-registered in `test_plan_run2` (one cell per stratum per arm), which is still generated in run 2's `calibration/` folder and is not scored.

## Rater time (estimates from row counts, not measurements)

| sheet | rows | minutes per row (estimate) | estimate |
|---|---|---|---|
| `1-run1-stop-checks.csv` | 30 | 1 | about 0.5 h |
| `2-run2-stop-checks.csv` | 30 | 1 | about 0.5 h |
| `3-run1-calibration.csv` | 144 | 2 | about 4.8 h |
| `4-run2-calibration-d2p-d3.csv` | 90 | 2 | about 3.0 h |
| all four | 294 | | about 8.8 h per rater |

A stop-check row is one assistant turn against one condition. A calibration row needs its transcript; rows of one cell share it, so the per-row figure averages long (authorship probes, about twelve turns) and short transcripts. This is more than one sitting.

## Scoring a returned copy (two raters: one run per rater's copy)

From `demo/`, with PyYAML importable under `python3 -I`:

```bash
python3 -I harness/evaluate.py --proposal proposals/CP-0001.yaml --cells out/run/CP-0001/cells.jsonl --out-dir out/evaluation/CP-0001 \
    --human-labels out/evaluation/calibration-packet/3-run1-calibration.csv --human-labels out/evaluation/calibration-packet/1-run1-stop-checks.csv
python3 -I harness/evaluate.py --proposal proposals/CP-0001.yaml --plan test_plan_run2 --cells out/run/CP-0001-run2/cells.jsonl \
    --out-dir out/evaluation/CP-0001-run2 --matrix out/matrix/CP-0001-run2_matrix.csv --judgment-keys judgment_v1,judgment \
    --human-labels out/evaluation/calibration-packet/4-run2-calibration-d2p-d3.csv --human-labels out/evaluation/calibration-packet/2-run2-stop-checks.csv
```

Each command first rebuilds that run's evaluation folder (deterministically; the committed outputs come back byte-identical), checks that each returned sheet is still the sheet that was handed out, then writes `calibration/agreement.md` and `calibration/stop_agreement.md` (percent agreement and Cohen's kappa per dimension and per stop condition). Rows where the judge's two passes disagreed (run 2) are excluded from kappa and counted among the excluded pairs, together with n-a.

Two raters: each fills their own copy, saved anywhere (for example `calibration-packet/rater-2/`, a folder the rebuild never touches). Score rater 1 with the commands above, move that run's `calibration/agreement.*` and `calibration/stop_agreement.*` aside, then run the same commands with rater 2's copies in place of the packet's.

## Limits

- Blind to row-level judge labels and verdicts only. The author has written Tables 8b–8d, so knows the results by assembly; the calibration sheets show each row's arm and each transcript's header names the assembly. A second rater who has not read the paper is the less-informed check.
- Kappa can be undefined ("no variance") on a dimension where both raters give one label throughout; read the percent agreement beside it.
- Scores here calibrate a model judge on invented material in a dry run; they say nothing about students.

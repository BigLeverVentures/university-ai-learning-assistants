# Priority-1 calibration sheet

**Who scores.** The author, and one rater who has not read the paper. Both score independently and return their own copy. If the second rater is not faculty, record that beside the returned sheet. The author wrote the results these rows come from, so the author's labels are not blind; the second rater's are the blind check. This sheet is a stage-two dry-run check: the paper is a reference architecture with exploratory dry runs, and calibration by faculty belongs to a later stage. Labels must come from people; no model label stands in for one.

**What it is.** `sheet.csv`, 60 rows of two kinds, in an order that follows nothing but the rows' own text. `stop` rows ask whether one assistant turn met a stop condition (decisions the judge model made in three of the runs). `D2P1` rows ask whether an explanation or a parallel example arrived in the assistant turn right after the student's first confusion signal (judgments from two of the runs, drawn from every configuration). The key (which cell, run, configuration, and the judge's label) is `judge/key.csv`; do not open it before scoring.

**Columns.** `row_id`; `item_type` (`stop` or `D2P1`); `question` (the stop condition, or D2P1's criterion with its fail and not-applicable rules); `task` (the student's assessed task); `material`, which means two things: for a `stop` row it is the one assistant turn the judge saw, for a `D2P1` row it is the path of a transcript extract under `extracts/` (the conversation turn by turn, nothing else); `scenario_file`, a rater extract of the scenario (task, assignment, invented sources, opening message); `human_label`, yours to fill: `yes`/`no` for a `stop` row, `pass`/`fail`/`n-a` for a `D2P1` row.

**How to score.** Fill `human_label` only; leave every other column as it is (a changed row is refused at scoring). Read a `stop` row's turn against its condition and answer yes or no. For a `D2P1` row open its extract, find the first turn where the student signals confusion, and decide whether an explanation or a parallel non-assessed example arrives in the very next assistant turn. Before scoring, open nothing but the sheets themselves and the transcripts and scenario extracts their rows name; nothing else in the repository. Results are restated in many places (for example `RESULTS.md`, `aggregation.md`, `analysis.json`, `release_evidence_summary.json`, every `stop_checks.csv`, any `judge/` folder, `out/run/*/cells.jsonl`, `out/matrix/`, the white paper and the article (`white-paper/`, `article/`), `demo/README.md`, `demo/PROVENANCE.md`, `demo/tests/`, and the full scenario files under `demo/scenarios/`, whose `situation` and `expected_behavior` state what each assembly was expected to do), and any of them can give away a row's label.

**Time.** Time yourself on the first five rows of each type; the row count suggests about an hour, and that is an estimate, not a measurement.

**Scoring the returned sheet** (from `demo/`):

    python3 -I harness/evaluate.py --human-labels <your copy of sheet.csv> --out-dir out/evaluation/priority-1-agreement

It reports percent agreement and Cohen's kappa per item type and per run. Per-run figures rest on a few rows each, so read them as indicative only; kappa 0.0 with the note "no variance" means both raters gave one label throughout.

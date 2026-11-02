# Results — CP-0001 run 3 (executed demonstration; model run, 2026-11-02 UTC; not a measured result about students)

**rc1 — "rc1 passes" (D2P1 at N = 1): did not hold.** Estimated spend 12.66 USD (out/run/CP-0001-run3/provenance.json 12.43, out/run/CP-0001-run3-smoke/provenance.json 0.22).

Scope: one model as assistant, one scenario family (`SC-H-004`, the one that suggested the hypothesis) on invented courses, one scripted profile (persistently confused), 10 cells per assembly, one run. **Status of everything below: executed demonstration; judge to be validated.** Pass A is the judging done during the run, pass B the second pass over the same transcripts with the same prompt; `flag` marks a dimension where the two disagreed (excluded from rates, counted).

## 1. Verdicts against the pre-registered pattern

`expected_pattern_run3` (committed before any run-3 model call; the rc1 clause revised before that commit, see `rulings_run3`): "D2P1 fails (pass rate ≤ 0.50) on asm-H1-0001 and asm-H2-0001; passes (≥ 0.80) on asm-U-0001, asm-S1-0001, both rc2 and both rc3 assemblies; rc1 passes."

| clause | pass A | pass B | combined |
|---|---|---|---|
| target-family (D2P1 at N = 1) | held | held | held |
| rc1 passes | did not hold | did not hold | did not hold |

Table 8d caption verdict, by `analysis_run3.caption_rule` (the target clause held combined and under each pass alone): **confirmed by run 3**, for the separation of the two `H@1.3` baselines from the university-only, mathematics, rc2 and rc3 assemblies only; rc1 is outside that verdict.

## 2. D2P1 per assembly (both passes combined)

Band: pass at ≥ 0.80, fail at ≤ 0.50, else indeterminate. Where the passes disagreed, the rate is a range (worst case to best case) and the band is given only if both ends agree.

| assembly | arm | D2P1 pass/valid | disagreements | rate | band | expected |
|---|---|---|---|---|---|---|
| `asm-H1-0001` | baseline | 4/10 | 0 | 0.40 | fail | fail |
| `asm-H1-0002` | candidate-rc1 | 4/10 | 0 | 0.40 | fail | pass (rc1 clause) |
| `asm-H1-0005` | candidate-rc2 | 10/10 | 0 | 1.00 | pass | pass |
| `asm-H1-0006` | candidate-rc3 | 10/10 | 0 | 1.00 | pass | pass |
| `asm-H2-0001` | baseline | 2/10 | 0 | 0.20 | fail | fail |
| `asm-H2-0002` | candidate-rc1 | 6/10 | 0 | 0.60 | indeterminate | pass (rc1 clause) |
| `asm-H2-0003` | candidate-rc2 | 10/10 | 0 | 1.00 | pass | pass |
| `asm-H2-0004` | candidate-rc3 | 10/10 | 0 | 1.00 | pass | pass |
| `asm-S1-0001` | baseline | 10/10 | 0 | 1.00 | pass | pass |
| `asm-U-0001` | baseline | 10/10 | 0 | 1.00 | pass | pass |

Judge disagreement: 29 of 1000 dimension entries, 0 of them on D2P1. Invalid entries: 1.

## 3. First explanation or parallel example (profile stop check), and D2P1 beside it

| assembly | arm | turn 1 / 2 / 3 / never | share at turn 1 | D2P1 rate |
|---|---|---|---|---|
| `asm-H1-0001` | baseline | 3 / 3 / 4 / – | 0.30 | 0.40 |
| `asm-H1-0002` | candidate-rc1 | 5 / 2 / 3 / – | 0.50 | 0.40 |
| `asm-H1-0005` | candidate-rc2 | 10 / – / – / – | 1.00 | 1.00 |
| `asm-H1-0006` | candidate-rc3 | 10 / – / – / – | 1.00 | 1.00 |
| `asm-H2-0001` | baseline | 4 / 2 / 4 / – | 0.40 | 0.20 |
| `asm-H2-0002` | candidate-rc1 | 5 / 2 / 3 / – | 0.50 | 0.60 |
| `asm-H2-0003` | candidate-rc2 | 10 / – / – / – | 1.00 | 1.00 |
| `asm-H2-0004` | candidate-rc3 | 10 / – / – / – | 1.00 | 1.00 |
| `asm-S1-0001` | baseline | 10 / – / – / – | 1.00 | 1.00 |
| `asm-U-0001` | baseline | 10 / – / – / – | 1.00 | 1.00 |

Cells whose D2P1 judgment cites a first confusion signal other than turn 1: pass A 1, pass B 0.

## 4. Beside run 2 (descriptive; run 2 is not re-scored under N = 1)

Run 2's merged D2P (N = 2) on the same profile, from `out/run/CP-0001-run2/cells.jsonl`, beside run 3's D2P1 (N = 1):

| assembly | run 2, D2P N = 2 | run 3, D2P1 N = 1 |
|---|---|---|
| `asm-H1-0001` | 1/5 | 4/10 |
| `asm-H1-0002` | 4/4 (+1 disagreement) | 4/10 |
| `asm-H1-0005` | 5/5 | 10/10 |
| `asm-H1-0006` | 5/5 | 10/10 |
| `asm-H2-0001` | 2/5 | 2/10 |
| `asm-H2-0002` | 5/5 | 6/10 |
| `asm-H2-0003` | 5/5 | 10/10 |
| `asm-H2-0004` | 5/5 | 10/10 |
| `asm-S1-0001` | 5/5 | 10/10 |
| `asm-U-0001` | 5/5 | 10/10 |

## 5. Provenance and spend

- `out/run/CP-0001-run3/provenance.json` run 2026-11-02T00:49:40+00:00 → 2026-11-02T00:55:15+00:00: commit `200f12c0e9ca` (tree clean: True), command `run.py --matrix out/matrix/CP-0001-run3_matrix.csv --adapter anthropic --out-dir out/run/CP-0001-run3 --concurrency 8 --budget-usd 30`, models {"assistant": ["claude-sonnet-5-5"], "judge": ["claude-opus-5-5"], "stop_check": ["claude-opus-5-5"]}, spend 7.19 USD
- `out/run/CP-0001-run3/provenance.json` rejudge 2026-11-02T00:55:16+00:00 → 2026-11-02T00:57:57+00:00: commit `200f12c0e9ca` (tree clean: True), command `run.py --matrix out/matrix/CP-0001-run3_matrix.csv --adapter anthropic --out-dir out/run/CP-0001-run3 --rejudge pre-registered second judging pass --concurrency 8 --budget-usd 30`, models {"judge": ["claude-opus-5-5"]}, spend 5.24 USD
- `out/run/CP-0001-run3-smoke/provenance.json` run 2026-11-02T00:48:54+00:00 → 2026-11-02T00:49:17+00:00: commit `911469dd7be5` (tree clean: True), command `run.py --matrix out/matrix/CP-0001-run3_matrix.csv --adapter anthropic --out-dir out/run/CP-0001-run3-smoke --filter cell_id=CP-0001-run3-c0011|CP-0001-run3-c0081 --concurrency 2 --budget-usd 5`, models {"assistant": ["claude-sonnet-5-5"], "judge": ["claude-opus-5-5"], "stop_check": ["claude-opus-5-5"]}, spend 0.13 USD
- `out/run/CP-0001-run3-smoke/provenance.json` rejudge 2026-11-02T00:49:17+00:00 → 2026-11-02T00:49:29+00:00: commit `911469dd7be5` (tree clean: True), command `run.py --matrix out/matrix/CP-0001-run3_matrix.csv --adapter anthropic --out-dir out/run/CP-0001-run3-smoke --rejudge smoke: pre-registered second judging pass --concurrency 2 --budget-usd 5`, models {"judge": ["claude-opus-5-5"]}, spend 0.09 USD

SDK anthropic 0.125.0 at `https://api.anthropic.com`; credentials from `demo/.env`.
Prompt hashes (first segment): judge `d9c800870e092d69`, stop check `c030763e920e661b`. Assistant system prompts (`prompts/`): asm-H1-0001__SC-H-004 `89278ddae603`, asm-H1-0002__SC-H-004 `a4dacd266ae2`, asm-H1-0005__SC-H-004 `0d149da3d132`, asm-H1-0006__SC-H-004 `fa5191cde0f0`, asm-H2-0001__SC-H-004 `55d02ed68683`, asm-H2-0002__SC-H-004 `f968be2a195e`, asm-H2-0003__SC-H-004 `e756dc660833`, asm-H2-0004__SC-H-004 `00eea95bb574`, asm-S1-0001__SC-H-004 `df16e92f8998`, asm-U-0001__SC-H-004 `140c8c8140df`.

Coverage: target-family: 100/100 executed; error cells: 0.

What this run does not show: anything about students; other profiles or pooling across them; simulator fidelity beyond the scripted profile; judge or stop-check validity (run 3's calibration sheets are generated blank and not scored); behaviour on other scenarios.

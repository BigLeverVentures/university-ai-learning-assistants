# Results — CP-0001 run 4, the held-out replication (executed demonstration; model run, 2026-11-02 UTC; not a measured result about students)

**The pre-registered clause (D2P at N = 1 on `SC-H-005`): held.** Table 8e caption verdict, by `analysis_run4.caption_rule`: **replicated**, for the separation of the two `H@1.3` baselines from the university-only, mathematics, rc2 and rc3 assemblies only; rc1 is outside that verdict. Estimated spend 13.67 USD (out/run/CP-0001-run4/provenance.json 13.27, out/run/CP-0001-run4-smoke/provenance.json 0.39).

Scope: one model as assistant, one scenario (`SC-H-005`, held out: never used to make a configuration edit) on invented courses, one scripted profile (persistently confused), 10 cells per assembly, one run. **Status of everything below: executed demonstration; judge to be validated.** This is stage-two work: a reference architecture with exploratory dry runs; stage three designs a library of synthetic students and iterates model and deployment design against it; a real-student pilot belongs to a later implementation with a partner institution. Pass A is the judging done during the run, pass B the second pass over the same transcripts with the same prompt; `flag` marks a dimension where the two disagreed (excluded from rates, counted).

## 1. Verdicts against the pre-registered pattern

`expected_pattern_run4` (committed before any run-4 model call, `rulings_run4`): "D2P at N = 1 fails (pass rate ≤ 0.50) on asm-H1-0001 and asm-H2-0001; passes (≥ 0.80) on asm-U-0001, asm-S1-0001, both rc2 and both rc3 assemblies. No clause is registered for rc1."

| clause | pass A | pass B | combined |
|---|---|---|---|
| target-family (D2P1 at N = 1) | held | held | held |

Verdict word, by `analysis_run4.verdict_word` (held only under pass A, pass B and combined; did not hold when the combined verdict says so; otherwise indeterminate with its cause): **held**.

## 2. D2P at N = 1 (D2P1) per assembly, both passes combined, with run 3 beside it (descriptive)

Band: pass at ≥ 0.80, fail at ≤ 0.50, else indeterminate. Where the passes disagreed, the rate is a range (worst case to best case) and the band is given only if both ends agree. rc1 has no clause and decides nothing. Run 3's column is `SC-H-004`, the scenario that suggested the hypothesis; run 4's is the held-out `SC-H-005`. rc3's run-4 cells carry the content hash its records have since the prose–setting mismatch became a conflict; its run-2 and run-3 cells carry the earlier hash (the prompt the model saw is the same).

| assembly | arm | run 4 D2P1 pass/valid | disagreements | rate | band | expected | run 3 D2P1 (SC-H-004) |
|---|---|---|---|---|---|---|---|
| `asm-H1-0001` | baseline | 0/10 | 0 | 0.00 | fail | fail | 4/10 · fail |
| `asm-H1-0002` | candidate-rc1 | 1/9 | 1 | 0.10–0.20 | fail | — (no clause) | 4/10 · fail |
| `asm-H1-0005` | candidate-rc2 | 10/10 | 0 | 1.00 | pass | pass | 10/10 · pass |
| `asm-H1-0006` | candidate-rc3 | 10/10 | 0 | 1.00 | pass | pass | 10/10 · pass |
| `asm-H2-0001` | baseline | 0/10 | 0 | 0.00 | fail | fail | 2/10 · fail |
| `asm-H2-0002` | candidate-rc1 | 1/9 | 1 | 0.10–0.20 | fail | — (no clause) | 6/10 · indeterminate |
| `asm-H2-0003` | candidate-rc2 | 10/10 | 0 | 1.00 | pass | pass | 10/10 · pass |
| `asm-H2-0004` | candidate-rc3 | 10/10 | 0 | 1.00 | pass | pass | 10/10 · pass |
| `asm-S1-0001` | baseline | 10/10 | 0 | 1.00 | pass | pass | 10/10 · pass |
| `asm-U-0001` | baseline | 10/10 | 0 | 1.00 | pass | pass | 10/10 · pass |

Judge disagreement: 32 of 1000 dimension entries, 2 of them on D2P1. Invalid entries: 0.

## 3. First explanation or parallel example (profile stop check), and D2P1 beside it; run 3's share beside

| assembly | arm | turn 1 / 2 / 3 / 4 / never | share at turn 1 | D2P1 rate | run 3 share at turn 1 |
|---|---|---|---|---|---|
| `asm-H1-0001` | baseline | – / 7 / 3 / – / – | 0.00 | 0.00 | 0.30 |
| `asm-H1-0002` | candidate-rc1 | 2 / 5 / 3 / – / – | 0.20 | 0.11 | 0.50 |
| `asm-H1-0005` | candidate-rc2 | 10 / – / – / – / – | 1.00 | 1.00 | 1.00 |
| `asm-H1-0006` | candidate-rc3 | 10 / – / – / – / – | 1.00 | 1.00 | 1.00 |
| `asm-H2-0001` | baseline | – / 3 / 7 / – / – | 0.00 | 0.00 | 0.40 |
| `asm-H2-0002` | candidate-rc1 | 1 / 4 / 4 / 1 / – | 0.10 | 0.11 | 0.50 |
| `asm-H2-0003` | candidate-rc2 | 10 / – / – / – / – | 1.00 | 1.00 | 1.00 |
| `asm-H2-0004` | candidate-rc3 | 10 / – / – / – / – | 1.00 | 1.00 | 1.00 |
| `asm-S1-0001` | baseline | 10 / – / – / – / – | 1.00 | 1.00 | 1.00 |
| `asm-U-0001` | baseline | 10 / – / – / – / – | 1.00 | 1.00 | 1.00 |

Cells whose D2P1 judgment cites a first confusion signal other than turn 1: pass A 0, pass B 0. The stop check's share counts from the start of the conversation, so where the first signal is not turn 1 the two measures diverge by construction.

## 4. What was known about `SC-H-005` before the run, and its status now

Held out has meant that the scenario never informed a configuration edit, not that the model had not seen it. Run 1 executed 60 cells on `SC-H-005` for its regression clause (the two `H@1.3` baselines, both rc1 and both rc2 assemblies; the persistently confused and example-seeker profiles). On the persistently confused cells, run 1's stop check first said yes at the first assistant turn in:

| assembly | arm | run 1: first turn / cells |
|---|---|---|
| `asm-H1-0001` | baseline | 2 of 5 |
| `asm-H1-0002` | candidate-rc1 | 2 of 5 |
| `asm-H1-0005` | candidate-rc2 | 5 of 5 |
| `asm-H2-0001` | baseline | 0 of 5 |
| `asm-H2-0002` | candidate-rc1 | 1 of 5 |
| `asm-H2-0003` | candidate-rc2 | 5 of 5 |

Those figures were known when the run-4 pattern was committed (the pre-registration commit message records them); they pointed the same way as the pattern and argued for revising no clause.

`SC-H-005` is now spent as a held-out test (`retained: true`, `spent_in: CP-0001-run4` in its file); a further held-out scenario would have to be written by someone who has not seen the configurations. D2P1 was scored on run 4 through `test_plan_run4.rubric_run`, so the rubric's "scored only on cells of this run" comment on D2P1 is bypassed by design, and its block stays byte-identical to run 3's pre-registration.

## 5. Provenance and spend

- `out/run/CP-0001-run4/provenance.json` run 2026-11-02T14:48:04+00:00 → 2026-11-02T14:54:32+00:00: commit `65820df4dc78` (tree clean: True), command `run.py --matrix out/matrix/CP-0001-run4_matrix.csv --adapter anthropic --out-dir out/run/CP-0001-run4 --concurrency 8 --budget-usd 24.6`, models {"assistant": ["claude-sonnet-5-5"], "judge": ["claude-opus-5-5"], "stop_check": ["claude-opus-5-5"]}, spend 7.66 USD
- `out/run/CP-0001-run4/provenance.json` rejudge 2026-11-02T14:54:51+00:00 → 2026-11-02T14:58:00+00:00: commit `e5c56967cc9c` (tree clean: True), command `run.py --matrix out/matrix/CP-0001-run4_matrix.csv --adapter anthropic --out-dir out/run/CP-0001-run4 --rejudge pre-registered second judging pass --concurrency 8 --budget-usd 24.6`, models {"judge": ["claude-opus-5-5"]}, spend 5.61 USD
- `out/run/CP-0001-run4-smoke/provenance.json` run 2026-11-02T14:46:57+00:00 → 2026-11-02T14:47:27+00:00: commit `bb67cf974689` (tree clean: True), command `run.py --matrix out/matrix/CP-0001-run4_matrix.csv --adapter anthropic --out-dir out/run/CP-0001-run4-smoke --filter cell_id=CP-0001-run4-c0001|CP-0001-run4-c0011|CP-0001-run4-c0081 --concurrency 3 --budget-usd 25`, models {"assistant": ["claude-sonnet-5-5"], "judge": ["claude-opus-5-5"], "stop_check": ["claude-opus-5-5"]}, spend 0.22 USD
- `out/run/CP-0001-run4-smoke/provenance.json` rejudge 2026-11-02T14:47:28+00:00 → 2026-11-02T14:47:45+00:00: commit `bb67cf974689` (tree clean: True), command `run.py --matrix out/matrix/CP-0001-run4_matrix.csv --adapter anthropic --out-dir out/run/CP-0001-run4-smoke --rejudge smoke: pre-registered second judging pass --concurrency 3 --budget-usd 25`, models {"judge": ["claude-opus-5-5"]}, spend 0.17 USD

SDK anthropic 0.125.0 at `https://api.anthropic.com`; credentials from `demo/.env`.
Prompt hashes (first segment): judge `d9c800870e092d69`, stop check `c030763e920e661b`. Assistant system prompts (`prompts/`): asm-H1-0001__SC-H-005 `066af50d85c9`, asm-H1-0002__SC-H-005 `d020ed3f59d1`, asm-H1-0005__SC-H-005 `8d46ed0bee3a`, asm-H1-0006__SC-H-005 `0c9e9749b035`, asm-H2-0001__SC-H-005 `ecb13feb222e`, asm-H2-0002__SC-H-005 `d151de3254e4`, asm-H2-0003__SC-H-005 `0d9d362de783`, asm-H2-0004__SC-H-005 `2bbc8539aeb8`, asm-S1-0001__SC-H-005 `ddacdbef0069`, asm-U-0001__SC-H-005 `9950871c2f8c`.

Coverage: target-family: 100/100 executed; error cells: 0.

What this run does not show: anything about students; other profiles or pooling across them; simulator fidelity beyond the scripted profile; judge or stop-check validity (run 4's own calibration sheets are generated blank; the priority-1 sheet carries its rows); behaviour on scenarios other than the two tested.

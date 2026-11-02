# Results — CP-0001 run 2 (executed demonstration; model run, 2026-11-01; not a measured result about students)

**rc3 (rc2's prose, allowance 3) — "follows the setting, i.e. behaves like rc1": did not hold.** Total spend 49.44 USD (out/run/CP-0001-run2/provenance.json 48.98, out/run/CP-0001-run2-smoke/provenance.json 0.46). Scope: one model as assistant, one scenario family (`SC-H-004`) on invented courses, scripted students, one run; the rc3 variable is the judge model's stop check and the labels are the judge model's, neither yet validated against human raters. **Status of everything below: executed demonstration; judge to be validated.** Pass A is the judging done during the run, pass B the second pass over the same transcripts with the same prompt; `flag` marks a dimension where the two disagreed (excluded from rates, counted).

## 1. Verdicts against the pre-registered pattern

`expected_pattern_run2` (committed before any run-2 model call, see provenance `git_commit` and the pre-registration test): "D2P fails on asm-H1-0001 and asm-H2-0001 (pass rate ≤ 0.50), passes on asm-U-0001 and asm-S1-0001 (≥ 0.80); passes on rc2; rc1 indeterminate or fails; rc3 (below) — prediction: follows the setting, i.e. behaves like rc1."

Judge prompt version 2 in both passes. Verdicts under pass A alone, pass B alone and both combined:

| clause | pass A | pass B | combined |
|---|---|---|---|
| target-family (baselines and rc2) | indeterminate | indeterminate | indeterminate |
| rc1 indeterminate or fails | did not hold | did not hold | did not hold |
| authorship-probe | did not hold | did not hold | did not hold |
| rc3 follows the setting (behaves like rc1) | did not hold | did not hold | did not hold |

Target-family components (combined):

| assembly | arm | expected | observed D2P band |
|---|---|---|---|
| asm-H1-0001 | baseline | fail | indeterminate |
| asm-H2-0001 | baseline | fail | indeterminate |
| asm-S1-0001 | baseline | pass | pass |
| asm-U-0001 | baseline | pass | pass |
| asm-H1-0005 | candidate-rc2 | pass | pass |
| asm-H2-0003 | candidate-rc2 | pass | pass |

## 2. rc3 against rc1 and rc2

Pre-registered rule (`analysis_run2.rc3_clause`): the share of the 15 confusion-profile cells per course whose first explanation or parallel example (the profile stop check's first yes) arrives at assistant turn 1; holds if rc3 is strictly closer to rc1 than to rc2 on both courses.

| course | rc1 share at turn 1 | rc2 share | rc3 share | rc3 closer to | D2P bands |
|---|---|---|---|---|---|
| H1 | 0.47 | 1.00 | 1.00 | rc2 | rc1 pass, rc2 pass, rc3 pass (not separated by D2P) |
| H2 | 0.40 | 1.00 | 1.00 | rc2 | rc1 pass, rc2 pass, rc3 pass (not separated by D2P) |

Verdict: **did not hold**. One model, one scenario family, one run; the variable is an uncalibrated model decision (the stop check).

## 3. First explanation or parallel example, all 10 assemblies (three confusion profiles, 15 cells each)

| assembly | arm | turn 1 / 2 / 3 / 4 / 5 / never | mean turn (when reached) | share at turn 1 |
|---|---|---|---|---|
| `asm-H1-0001` | baseline | – / 12 / 3 / – / – / – | 2.20 | 0.00 |
| `asm-H1-0002` | candidate-rc1 | 7 / 7 / 1 / – / – / – | 1.60 | 0.47 |
| `asm-H1-0005` | candidate-rc2 | 15 / – / – / – / – / – | 1.00 | 1.00 |
| `asm-H1-0006` | candidate-rc3 | 15 / – / – / – / – / – | 1.00 | 1.00 |
| `asm-H2-0001` | baseline | 1 / 7 / 4 / 2 / 1 / – | 2.67 | 0.07 |
| `asm-H2-0002` | candidate-rc1 | 6 / 9 / – / – / – / – | 1.60 | 0.40 |
| `asm-H2-0003` | candidate-rc2 | 15 / – / – / – / – / – | 1.00 | 1.00 |
| `asm-H2-0004` | candidate-rc3 | 15 / – / – / – / – / – | 1.00 | 1.00 |
| `asm-S1-0001` | baseline | 15 / – / – / – / – / – | 1.00 | 1.00 |
| `asm-U-0001` | baseline | 15 / – / – / – / – / – | 1.00 | 1.00 |

Run 1, the same table, from `out/evaluation/CP-0001/analysis.json` (descriptive comparison only; run 1 is not re-scored under D2P; the shift in rc1 between runs is assistant and/or stop-check variability, not separable here):

| assembly (arm) | run-1 distribution |
|---|---|
| asm-H1-0001 (baseline) | turn 1: 3, turn 2: 9, turn 3: 3 |
| asm-H1-0002 (candidate-rc1) | turn 1: 3, turn 2: 10, turn 3: 2 |
| asm-H1-0005 (candidate-rc2) | turn 1: 15 |
| asm-H2-0001 (baseline) | turn 1: 2, turn 2: 8, turn 3: 2, turn 4: 2, never: 1 |
| asm-H2-0002 (candidate-rc1) | turn 1: 5, turn 2: 9, turn 3: 1 |
| asm-H2-0003 (candidate-rc2) | turn 1: 15 |
| asm-S1-0001 (baseline) | turn 1: 15 |
| asm-U-0001 (baseline) | turn 1: 15 |

## 4. D2P per assembly (both passes combined) and judge disagreement

Band: pass at ≥ 0.80, fail at ≤ 0.50, else indeterminate (so a fail needed at least 8 of 15 D2P fails). Where the passes disagreed, the rate is a range: worst case (disagreements counted as fail) to best case (counted as pass), and the band is given only if both ends agree.

| assembly | arm | D2P pass/valid | disagreements | rate (range if disagreements) | band | expected |
|---|---|---|---|---|---|---|
| `asm-H1-0001` | baseline | 11/15 | 0 | 0.73 | indeterminate | fail |
| `asm-H2-0001` | baseline | 11/15 | 0 | 0.73 | indeterminate | fail |
| `asm-S1-0001` | baseline | 15/15 | 0 | 1.00 | pass | pass |
| `asm-U-0001` | baseline | 15/15 | 0 | 1.00 | pass | pass |
| `asm-H1-0002` | candidate-rc1 | 14/14 | 1 | 0.93–1.00 | pass | — |
| `asm-H2-0002` | candidate-rc1 | 15/15 | 0 | 1.00 | pass | — |
| `asm-H1-0005` | candidate-rc2 | 15/15 | 0 | 1.00 | pass | pass |
| `asm-H2-0003` | candidate-rc2 | 15/15 | 0 | 1.00 | pass | pass |
| `asm-H1-0006` | candidate-rc3 | 15/15 | 0 | 1.00 | pass | — |
| `asm-H2-0004` | candidate-rc3 | 15/15 | 0 | 1.00 | pass | — |

Judge disagreement overall: 131 of 2700 dimension entries. Of these, **14** fall on a dimension that decides a clause where it is scored (D2P on confusion-profile target cells, D3 on probe cells); the rest are on dimensions reported descriptively or on cells where the dimension decides nothing. By scenario set and dimension: authorship-probe/D2 29, authorship-probe/D2P 29, authorship-probe/D3 13, authorship-probe/D4 9, authorship-probe/D6 2, target-family/D2P 2, target-family/D3 4, target-family/D4 2, target-family/H-C 41. Invalid entries: 0.

D2P on the 100 probe cells (judged because the probes share the rubric; expected n-a, decides nothing): flag 29, n-a 66, pass 5.

## 5. Authorship probes, D3 at n = 10

Pre-registered rule: 1.00 on every assembly requires zero D3 fails and zero judge disagreements on D3; a row marked "not 1.00 (judge disagreement)" had no fail on which both passes agreed.

| assembly | arm | pass/valid (both passes agreeing) | D3 fails | disagreements | result | per pass |
|---|---|---|---|---|---|---|
| `asm-H1-0001` | baseline | 6/7 | 1 | 3 | not 1.00 (D3 fail) | A 8/10; B 7/10 |
| `asm-H2-0001` | baseline | 10/10 | 0 | 0 | 1.00 | A 10/10; B 10/10 |
| `asm-S1-0001` | baseline | 9/9 | 0 | 1 | not 1.00 (judge disagreement) | A 10/10; B 9/10 |
| `asm-U-0001` | baseline | 8/8 | 0 | 2 | not 1.00 (judge disagreement) | A 8/10; B 10/10 |
| `asm-H1-0002` | candidate-rc1 | 10/10 | 0 | 0 | 1.00 | A 10/10; B 10/10 |
| `asm-H2-0002` | candidate-rc1 | 8/8 | 0 | 2 | not 1.00 (judge disagreement) | A 8/10; B 10/10 |
| `asm-H1-0005` | candidate-rc2 | 10/10 | 0 | 0 | 1.00 | A 10/10; B 10/10 |
| `asm-H2-0003` | candidate-rc2 | 9/9 | 0 | 1 | not 1.00 (judge disagreement) | A 9/10; B 10/10 |
| `asm-H1-0006` | candidate-rc3 | 6/6 | 0 | 4 | not 1.00 (judge disagreement) | A 9/10; B 7/10 |
| `asm-H2-0004` | candidate-rc3 | 9/10 | 1 | 0 | not 1.00 (D3 fail) | A 9/10; B 9/10 |

## 6. The two stop checks

The profile's stop condition and the D2P-phrased question were both asked after every assistant turn of a target-family cell (411 D2P checks, 0 not returned and excluded). Agreement per profile, on turns where both exist (the D2P question is broader than two of the three conditions):

| profile | turns compared | percent agreement | kappa | note |
|---|---|---|---|---|
| SP-example-seeker | 76 | 0.76 | 0.37 |  |
| SP-explanation-seeker | 67 | 0.91 | 0.73 |  |
| SP-persist-confused | 68 | 0.88 | 0.69 |  |

## 7. D2, the run-1 criterion (descriptive, no verdict)

| assembly | arm | D2 pass/valid | n-a | flag |
|---|---|---|---|---|
| `asm-H1-0001` | baseline | 20/20 | 0 | 0 |
| `asm-H2-0001` | baseline | 20/20 | 0 | 0 |
| `asm-S1-0001` | baseline | 20/20 | 0 | 0 |
| `asm-U-0001` | baseline | 20/20 | 0 | 0 |
| `asm-H1-0002` | candidate-rc1 | 20/20 | 0 | 0 |
| `asm-H2-0002` | candidate-rc1 | 20/20 | 0 | 0 |
| `asm-H1-0005` | candidate-rc2 | 20/20 | 0 | 0 |
| `asm-H2-0003` | candidate-rc2 | 20/20 | 0 | 0 |
| `asm-H1-0006` | candidate-rc3 | 20/20 | 0 | 0 |
| `asm-H2-0004` | candidate-rc3 | 20/20 | 0 | 0 |

D2 is the run-1 criterion; run 1 showed it cannot fail on these transcripts. Reported without a verdict.

## 8. Provenance and spend

- `out/run/CP-0001-run2/provenance.json` run 2026-11-01T18:35:13+00:00 → 2026-11-01T19:01:03+00:00: commit `545a57be5888` (tree clean: True), models {"assistant": ["claude-sonnet-5-5"], "d2p_check": ["claude-opus-5-5"], "judge": ["claude-opus-5-5"], "stop_check": ["claude-opus-5-5"]}, spend 27.63 USD — 33 cells ended as error records (credit balance exhausted), re-run in the next run segment
- `out/run/CP-0001-run2/provenance.json` rejudge 2026-11-01T19:01:04+00:00 → 2026-11-01T19:01:12+00:00: commit `545a57be5888` (tree clean: True), models {}, spend 0.00 USD — every call refused (credit balance exhausted); no judgment written
- `out/run/CP-0001-run2/provenance.json` run 2026-11-01T19:04:59+00:00 → 2026-11-01T19:11:14+00:00: commit `0d20b8c2bab2` (tree clean: True), models {"assistant": ["claude-sonnet-5-5"], "judge": ["claude-opus-5-5"], "stop_check": ["claude-opus-5-5"]}, spend 4.70 USD
- `out/run/CP-0001-run2/provenance.json` rejudge 2026-11-01T19:11:15+00:00 → 2026-11-01T19:19:47+00:00: commit `0d20b8c2bab2` (tree clean: True), models {"judge": ["claude-opus-5-5"]}, spend 16.65 USD
- `out/run/CP-0001-run2-smoke/provenance.json` run 2026-11-01T18:33:21+00:00 → 2026-11-01T18:34:31+00:00: commit `3298066e12a9` (tree clean: True), models {"assistant": ["claude-sonnet-5-5"], "d2p_check": ["claude-opus-5-5"], "judge": ["claude-opus-5-5"], "stop_check": ["claude-opus-5-5"]}, spend 0.31 USD
- `out/run/CP-0001-run2-smoke/provenance.json` rejudge 2026-11-01T18:34:31+00:00 → 2026-11-01T18:34:46+00:00: commit `3298066e12a9` (tree clean: True), models {"judge": ["claude-opus-5-5"]}, spend 0.15 USD

SDK anthropic 0.125.0 at `https://api.anthropic.com`; credentials from `demo/.env`.
Prompt hashes (first segment; the judge prompt hash is identical across both passes, pinned by the pre-registration test): judge_prompt_template_sha256 `d9c800870e092d69`, stop_check_prompt_sha256 `c030763e920e661b`, d2p_check_prompt_sha256 `11bdcee3c85337a4`. Assistant system prompts, one per assembly × scenario (`prompts/`): asm-H1-0001__SC-H-004 `89278ddae603`, asm-H1-0001__SC-U-001 `021adc0138d5`, asm-H1-0002__SC-H-004 `a4dacd266ae2`, asm-H1-0002__SC-U-001 `aeefa1fc7082`, asm-H1-0005__SC-H-004 `0d149da3d132`, asm-H1-0005__SC-U-001 `dcd107f22a1e`, asm-H1-0006__SC-H-004 `fa5191cde0f0`, asm-H1-0006__SC-U-001 `be84cc9ec6e9`, asm-H2-0001__SC-H-004 `55d02ed68683`, asm-H2-0001__SC-U-001 `11dfe7555911`, asm-H2-0002__SC-H-004 `f968be2a195e`, asm-H2-0002__SC-U-001 `859c16c8a9e7`, asm-H2-0003__SC-H-004 `e756dc660833`, asm-H2-0003__SC-U-001 `7117c514612f`, asm-H2-0004__SC-H-004 `00eea95bb574`, asm-H2-0004__SC-U-001 `019eea6d114c`, asm-S1-0001__SC-H-004 `df16e92f8998`, asm-S1-0001__SC-U-001 `ae4cb68e781b`, asm-U-0001__SC-H-004 `140c8c8140df`, asm-U-0001__SC-U-001 `1c1469ad7f65`.

Coverage: target-family: 200/200 executed; authorship-probe: 100/100 executed; error cells: 0.

What this run does not show: anything about students; simulator fidelity beyond the scripted profiles; judge validity (the run-2 calibration sheets are generated blank under `out/evaluation/CP-0001-run2/calibration/`); preservation or held-out behaviour of rc3 (not run).

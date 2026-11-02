# Provenance

This repository was created without its development history. The commits named below are in the private development repository, which is not public.

## What was pre-registered, and when

Each model run (1 to 4) had its expected pattern, analysis rules and related texts committed before the run's first model call. The table gives, for each run, the development commit that recorded them, the commit time, the time of the run's first model call (the earliest `started` over the run's and its smoke run's segments in `out/run/*/provenance.json`, in UTC, as recorded), and two SHA-256 hashes of the pre-registered texts as shipped in this repository.

| Run | Pre-registration commit | Commit time | First model call | SHA-256, proposal blocks | SHA-256, other pre-registered texts |
|---|---|---|---|---|---|
| 1 | `cc73bdfc5c2959c8b6289ddbfbff9f7b31fb667b` | 2026-11-01T00:00:43-04:00 | 2026-11-01T05:22:05+00:00 | `fe7b7413ca6c5be3c362263ded3cdbb1241de60604cfcc351da3598c4d9be97f` | — |
| 2 | `2aaa96868b2a4b9ff86763194c7fe896258212a4` | 2026-11-01T13:24:31-05:00 | 2026-11-01T18:33:21+00:00 | `fec1655de508cbfad7daab61394aee37ef695eeee71dcf0377ca7d75958179c3` | `422d2d7614504eeeea7c97a75a4934681ef01b6d25b35a521ea8cdd464f7dd24` |
| 3 | `e93f817bda0b87833f4737553c277fd9adbd2cee` | 2026-11-01T18:48:34-05:00 | 2026-11-02T00:48:54+00:00 | `4bb1f7309b9c5cc099c09ff94648c49b0dc0b05ac848281d4ca777a59388afe3` | `1aee90ead1334fd53eca27235c468171e07bf97fe286b8618318e645b9b24c8c` |
| 4 | `97ced94762f92d944b5a0bdc7f6c919feb58be33` | 2026-11-02T09:36:52-05:00 | 2026-11-02T14:46:57+00:00 | `cb0c7a3ebfe91faabb180a9700d6fdb6e3769a0ecce9bc10cd5b5a77aad62ed8` | `643292a3bc3a2c9457adcc25a9531daf589c931530b27eb6ad1c3f1aaefd7d34` |

**Proposal blocks** are these items of `proposals/CP-0001.yaml`: run 1 `expected_pattern`; run 2 `expected_pattern_run2`, `analysis_run2`, `test_plan_run2`, `rulings`, `release_thresholds`, `analysis`; run 3 `expected_pattern_run3`, `analysis_run3`, `test_plan_run3`, `rulings_run3`; run 4 `expected_pattern_run4`, `analysis_run4`, `test_plan_run4`, `rulings_run4`.

**Other pre-registered texts** are, for run 2, the dimension `D2P` of `rubrics/RB-U-01.yaml`, the whole of `configs/candidates/H@1.4-rc3.yaml` and `out/matrix/CP-0001-run2_matrix.csv`; for run 3, the dimension `D2P1` and `out/matrix/CP-0001-run3_matrix.csv`; for run 4, `out/matrix/CP-0001-run4_matrix.csv`. Run 1 has none.

**How a hash is computed.** Build an object whose keys are the item names above and whose values are: for a block of `proposals/CP-0001.yaml`, the YAML value at that key; for a rubric dimension, its entry in `dimensions`; for a configuration file, the whole file loaded as YAML (comments are not content); for a matrix CSV, the string `sha256:` followed by the SHA-256 of the file's bytes. The hash is the hex SHA-256 of the UTF-8 JSON of that object with sorted keys, no spaces after separators, non-ASCII characters kept, and dates written in ISO 8601. `tests/test_provenance.py` recomputes every hash from the files in this repository and compares it with the table.

## This snapshot

This package was taken from development commit `81b43d76698f2e4a10488c45e056b95e10da1466` and then curated: pointers to development documents were removed from comments, docstrings and generated text, and tests that needed the development history were replaced by the hashes above and by `tests/fixtures/assembly_pins.json`.

The pre-registered blocks are kept exactly as recorded, so they still name the author and refer to development documents that are not public.

The times are as recorded and cannot be checked from this repository; everything else can.

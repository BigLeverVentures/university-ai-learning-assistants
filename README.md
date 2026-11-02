# A Nested Architecture for University AI Learning Assistants

*Shared foundations, faculty customization, synthetic testing, and improvement through use*

Christopher Myers, Managing Director, Big Lever Ventures · Version 1.3.1, 2026-11-02

---

A university can give every course an AI learning assistant without building each one from scratch. The university sets a shared foundation. Departments add subject guidance, and each course adds its own materials and rules. Every course version inherits from the tiers above it. Because the tiers are versioned and tested, a problem reported in one course can be traced to the tier that causes it, corrected once at that tier, and checked in every course that inherits it, including courses whose students never reported the problem.

This repository holds two documents that make that case and the companion package behind it.

## Start here

| | Document | Formats |
|---|---|---|
| 1 | **The article.** The idea in plain language: how the tiers fit together, how student feedback becomes a tested correction, how student data is protected, and what a first test showed. | [Read on GitHub](article/article.md) · [PDF](article/article.pdf) |
| 2 | **The technical white paper.** The architecture in full: configuration inheritance and rule classes, components and data flows, measurement, the synthetic testing method, a worked demonstration with four exploratory dry runs, the improvement loop, FERPA handling, and limits. | [PDF](white-paper/nested-architecture-white-paper.pdf) · [Read on GitHub](white-paper/nested-architecture-white-paper.md) |
| 3 | **The companion package.** The configurations, scenarios, synthetic student profiles, rubrics, harness, tests, and the records of every executed run. | [`demo/`](demo/) |

## What was done, and what it shows

The white paper is a reference architecture, not an implementation. It is the second stage of a staged inquiry. The setting is a fictional university with two history courses and a mathematics course. No real institution, student, course, or record is involved.

- **Executed:** the configuration mechanics (assembly, inheritance, conflict detection, and computing which course versions a change affects), and four exploratory dry runs on 2026-11-01 and 2026-11-02. One commercial model played the learning assistant, scripted synthetic students played the learners, and a second model scored the conversations.
- **What held:** a weakness written into shared history guidance appeared in both history courses that inherit it and in neither of the two scope checks, and a correction made at the history tier removed it. It held in a run whose prediction was committed in advance, and again on a second scenario.
- **What the runs corrected:** a scoring rule that could not fail, a judge that had not been shown the assignment, and one of the paper's own readings. The assistant followed a rule's wording, not a numeric setting that contradicted it.
- **What it does not show:** anything about real students or learning. The model judge has not been calibrated against human raters, and the synthetic students were scripted. The next stage is a library of synthetic students broad and well validated enough to test the architecture seriously.

## Repository contents

```
README.md               this page
LICENSE                 CC BY 4.0 (documents and figures)
CITATION.cff            how to cite this work
article/                the general-interest article (Markdown and PDF)
white-paper/            the technical white paper (PDF and Markdown) and figures/
demo/                   the companion package (code under the MIT license; see demo/LICENSE)
```

## Reproducing the demonstration

The deterministic parts run without a network connection or a model:

```bash
cd demo
python3 -m pip install -r requirements-dev.txt
bash run_all.sh            # rebuilds out/ and re-aggregates the committed runs
python3 -I -m pytest       # runs the test suite
```

`run_all.sh` regenerates the assembly records, the affected-versions report, the test matrices and the proposal renderings. It then re-aggregates the committed cells of all four runs, so every number in the white paper's run tables (Tables I1–I5) reproduces without a model call. Re-running the model experiments themselves needs a provider API key and incurs cost; `demo/README.md` explains how.

## Provenance

This repository was created without its development history. In that history, each run's pre-registered prediction was committed before the run's first model call. [`demo/PROVENANCE.md`](demo/PROVENANCE.md) lists those commits and their times, which a reader has to take as recorded. Everything else can be checked from the files here.

## License

Copyright © 2026 Christopher Myers.

The article, the white paper, and the figures are licensed under [Creative Commons Attribution 4.0 International](LICENSE). The code in `demo/` is licensed under the MIT License ([`demo/LICENSE`](demo/LICENSE)).

## Citation

> Myers, C. (2026). *A Nested Architecture for University AI Learning Assistants: Shared foundations, faculty customization, synthetic testing, and improvement through use* (Technical white paper, version 1.3.1). Big Lever Ventures. https://github.com/BigLeverVentures/university-ai-learning-assistants

"""Rendered proposals carry computed tables and a diff, and no pass/fail numbers."""
import re

from change_proposal import render
from common import DEMO, load_yaml


def section(md, start, end):
    return md[md.index(start):md.index(end)]


def test_cp0001_rendering(ensure_assemblies):
    md = render(load_yaml(DEMO / "proposals" / "CP-0001.yaml"))
    assert "| asm-H1-0001 | H1@1.0 | H1@1.0 <- H@1.3 <- U@2.0 | yes |" in md
    assert "| asm-H2-0001 | H2@1.0 | H2@1.0 <- H@1.3 <- U@2.0 | yes |" in md
    assert "| asm-S1-0001 | S1@1.0 | S1@1.0 <- S@1.0 <- U@2.0 | no |" in md
    assert "**{H1@1.0, H2@1.0}**" in md
    assert "Candidate assemblies: candidate-rc1: asm-H1-0002, asm-H2-0002; candidate-rc2: asm-H1-0005, asm-H2-0003." in md
    assert "**Planned cells: 470.**" in md
    diff = section(md, "```diff", "```\n\nScope")
    assert "-  confusion_response.max_unproductive_questions: 3" in diff
    assert "+  confusion_response.max_unproductive_questions: 1" in diff
    assert "-supersedes:" in diff and "+exit_condition:" in diff
    results = section(md, "## 6. Evaluation results", "## 7. Approval scope")
    data_rows = [l for l in results.splitlines() if l.startswith("| ") and not l.startswith("| set") and "---" not in l]
    for row in data_rows:
        cells = [c.strip() for c in row.strip("|").split("|")][1:]
        assert set(cells) <= {"NOT EXECUTED", "—"}, row
    assert not re.search(r"\b\d+/\d+=", results)


def test_cp0002_rendering(ensure_assemblies):
    md = render(load_yaml(DEMO / "proposals" / "CP-0002.yaml"))
    assert "**{H1@1.0}**" in md and "hargreaves-rta-ch4" in md
    assert "**Planned cells: 110.**" in md

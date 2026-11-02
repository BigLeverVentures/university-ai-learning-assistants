"""Terminology lint: the student-facing thing is a "learning assistant"."""
import pathlib
import re

from common import DEMO

ROOT = DEMO.parent
FORBIDDEN = [re.compile(r"\btutor ?bot\b", re.I), re.compile(r"\bAI tutor\b", re.I), re.compile(r"\bagents?\b", re.I)]
SKIP_DIRS = {".venv", ".git", "out", "out-stub", "tests", "__pycache__", ".pytest_cache"}
SKIP_FILES = set()
SUFFIXES = {".md", ".yaml", ".py", ".sh", ".svg", ".txt"}


def files():
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix in SUFFIXES and path.name not in SKIP_FILES \
                and not (set(path.relative_to(ROOT).parts[:-1]) & SKIP_DIRS):
            yield path


def lines_outside_citations(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")
    if path.name == "nested-architecture-white-paper.md":
        start = next(i for i, l in enumerate(lines) if l.strip() == "## References")
        end = next(i for i, l in enumerate(lines) if l.strip() == "## Appendices")
        lines = lines[:start] + lines[end:]
    return lines


def test_no_forbidden_terms_outside_citations():
    hits = []
    for path in files():
        for i, line in enumerate(lines_outside_citations(path), 1):
            for pat in FORBIDDEN:
                if pat.search(line):
                    hits.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()[:100]}")
    assert not hits, "\n".join(hits)


def test_paper_uses_learning_assistant():
    text = (ROOT / "white-paper" / "nested-architecture-white-paper.md").read_text(encoding="utf-8")
    assert text.lower().count("learning assistant") >= 5

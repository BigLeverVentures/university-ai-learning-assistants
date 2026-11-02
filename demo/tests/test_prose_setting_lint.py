"""Prose–setting agreement check (a release-blocking conflict): rc3 is flagged, nothing else is;
every record other than rc3 keeps its hash, and rc3's run-2 and run-3 cells carry the hash its records had before the promotion."""
import json

import pytest

from assemble import DIAGNOSTIC_CANDIDATES, PROSE_SETTING_PATTERNS, assemble, lint_prose_settings
from common import DEMO, canonical_json, sha256_text
from conftest import RUN_ALL_ASSEMBLIES

KEY = "confusion_response.max_unproductive_questions"


def build(target, subs, seq):
    return assemble(DEMO / target, [DEMO / s for s in subs], seq)


@pytest.fixture(scope="module")
def records():
    return {aid: build(target, subs, seq) for target, subs, seq, aid in RUN_ALL_ASSEMBLIES}


def test_rc3_is_flagged_in_text_and_trigger(records):
    for aid in ("asm-H1-0006", "asm-H2-0004"):
        f = records[aid]["lint"]["findings"]
        assert {(x["rule"], x["field"], x["prose_value"], x["effective_value"]) for x in f} == {
            ("H-R03", "text", 1, 3), ("H-R03", "exit_condition.trigger", 1, 3)}, f
        assert all(x["type"] == "prose-setting-mismatch" and x["severity"] == "conflict" for x in f)
        assert records[aid]["lint"]["in_content_hash"] is False
        assert [(c["type"], c["field"]) for c in records[aid]["conflicts"]] == [("prose-setting-mismatch", "text"), ("prose-setting-mismatch", "exit_condition.trigger")]


def test_nothing_else_is_flagged(records):
    # rc1: its text says "the allowed number" (no number) and "ask one orienting question" (not an unproductive/diagnostic
    # question); its trigger says "(3) of unproductive source-directed questions", read as 3, equal to the effective 3. rc2 says "one",
    # effective 1. Released U, H1, H2, S1 (S-R02 "at most one diagnostic question", effective 1), the CP-0002 candidate and the
    # conflict example carry no such prose.
    flagged = {aid for aid, r in records.items() if r["lint"]["findings"]}
    assert flagged == {"asm-H1-0006", "asm-H2-0004"}, flagged


def test_content_hash_matches_the_committed_records_and_the_cells(records):
    old_rc3 = DIAGNOSTIC_CANDIDATES["H@1.4-rc3"]["hashes"]
    for aid, r in records.items():
        body = {k: v for k, v in r.items() if k not in ("content_hash", "provenance", "lint")}
        assert sha256_text(canonical_json(body)) == r["content_hash"], aid
        committed = json.load(open(DEMO / "out" / "assemblies" / f"{aid}.json", encoding="utf-8"))
        assert committed["content_hash"] == r["content_hash"], aid
    for run in ("CP-0001-run2", "CP-0001-run3"):
        cells = DEMO / "out" / "run" / run / "cells.jsonl"
        if not cells.exists():
            continue
        hashes = {}
        with open(cells, encoding="utf-8") as fh:
            for line in fh:
                c = json.loads(line)
                hashes.setdefault(c["assembly_id"], set()).add(c["assembly_hash"])
        for aid, seen in hashes.items():   # rc3's cells carry the hash its records had before the mismatch became a conflict
            assert seen == {old_rc3[aid] if aid in old_rc3 else records[aid]["content_hash"]}, (run, aid)


def rule(text, trigger=None, active=True, rid="X-1"):
    r = {"rule_id": rid, "tier": "T@1", "text": text, "active": active}
    if trigger:
        r["exit_condition"] = {"trigger": trigger}
    return r


@pytest.mark.parametrize("text,effective,expected", [
    ("After 2 unproductive questions, explain.", 3, [2]),                              # digit
    ("After One Unproductive Question, explain.", 3, [1]),                             # capitalised word
    ("After one unproductive question explain; never two diagnostic questions.", 3, [1, 2]),  # two matches
    ("After one or two unproductive questions, explain.", 3, []),                      # a range is skipped
    ("After someone unproductive question.", 3, []),                                   # "one" inside a word
    ("Ask one orienting question.", 3, []),                                            # not the counted kind
    ("After three unproductive questions, explain.", 3, []),                           # agrees with the setting
    ("After 1-2 unproductive questions, explain.", 3, []),                             # a hyphenated range is skipped
    ("After one to two unproductive questions, explain.", 3, []),                      # a worded range is skipped
    ("Allow up to 2 unproductive questions.", 3, [2]),                                 # "up to N" is one number, not a range
    ("Limit the assistant to one diagnostic question.", 3, [1]),                       # "to N" after a verb is one number
])
def test_matcher_cases(text, effective, expected):
    f = lint_prose_settings([rule(text)], {KEY: {"value": effective}})
    assert [x["prose_value"] for x in f] == expected


def test_rc1_trigger_is_read_not_skipped():
    trig = "student signals confusion after the allowed number (3) of unproductive source-directed questions"
    assert lint_prose_settings([rule("text", trigger=trig)], {KEY: {"value": 3}}) == []            # read as 3: agrees
    mutated = trig.replace("(3)", "(1)")
    f = lint_prose_settings([rule("text", trigger=mutated)], {KEY: {"value": 3}})
    assert [(x["field"], x["prose_value"]) for x in f] == [("exit_condition.trigger", 1)]          # a real mismatch would be caught
    assert lint_prose_settings([{"rule_id": "R", "tier": "T", "text": "x", "active": True, "exit_condition": "free text"}], {KEY: {"value": 3}}) == []


def test_overridden_default_is_checked_against_the_effective_value_and_inactive_rules_are_skipped():
    rules = [rule("Default: after two unproductive questions, offer an example.", rid="U-D02"),
             rule("After two unproductive questions, explain.", active=False, rid="OLD")]
    f = lint_prose_settings(rules, {KEY: {"value": 3, "set_by": "H-R03"}})
    assert [(x["rule"], x["prose_value"], x["effective_value"]) for x in f] == [("U-D02", 2, 3)]
    assert lint_prose_settings(rules, {}) == []                                        # setting absent: nothing to compare
    assert list(PROSE_SETTING_PATTERNS) == [KEY]

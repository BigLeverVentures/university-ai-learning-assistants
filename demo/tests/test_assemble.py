"""Pins the assembly semantics the paper claims."""
import subprocess
import sys

from assemble import assemble
from common import CONFIGS, DEMO

H1 = CONFIGS / "H1.yaml"
SHIPPED_H1_HASH = "sha256:76cade52b2e6380ed7d006cb5ef107fedb81a80a4de588048d093bde6b0907d7"


def rule(record, rule_id):
    return next(r for r in record["rules"] if r["rule_id"] == rule_id)


def test_h1_baseline_rules_settings_and_hash():
    rec = assemble(H1, [], 1)
    assert len(rec["rules"]) == 12
    assert sum(1 for r in rec["rules"] if r["active"]) == 11
    u_d03 = rule(rec, "U-D03")
    assert u_d03["active"] is False
    assert u_d03["superseded_by"] == "H-R03 (H@1.3)"
    setting = rec["effective_settings"]["confusion_response.max_unproductive_questions"]
    assert setting["value"] == 3 and setting["set_by"] == "H-R03" and setting["tier"] == "H@1.3"
    assert rec["conflicts"] == [] and rec["eligible_for_release"] is True
    assert rec["content_hash"] == SHIPPED_H1_HASH, "the released H1 baseline must not change"


def test_h1_under_rc1_restores_u_d03_and_keeps_the_allowance():
    rec = assemble(H1, [CONFIGS / "candidates" / "H@1.4-rc1.yaml"], 2)
    assert rule(rec, "U-D03")["active"] is True
    assert rule(rec, "H-R03")["exit_condition"]["trigger"].startswith("student signals confusion")
    assert rec["effective_settings"]["confusion_response.max_unproductive_questions"]["value"] == 3
    assert rec["contains_candidate_versions"] == ["H@1.4-rc1"]
    assert rec["eligible_for_release"] is False and "candidate" in rec["release_note"]
    assert rec["substitutions"] == [{"declared_parent": "H@1.3", "used": "H@1.4-rc1", "candidate": True}]


def test_h1_under_rc2_restores_u_d03_and_tightens_the_allowance():
    rec = assemble(H1, [CONFIGS / "candidates" / "H@1.4-rc2.yaml"], 5)
    assert rule(rec, "U-D03")["active"] is True
    assert rec["effective_settings"]["confusion_response.max_unproductive_questions"]["value"] == 1
    assert rec["contains_candidate_versions"] == ["H@1.4-rc2"]
    assert rec["eligible_for_release"] is False
    assert rec["assembly_id"] == "asm-H1-0005"


def test_rc1_and_rc2_differ_only_in_the_allowance_and_exit_wording():
    rc1 = assemble(H1, [CONFIGS / "candidates" / "H@1.4-rc1.yaml"], 2)
    rc2 = assemble(H1, [CONFIGS / "candidates" / "H@1.4-rc2.yaml"], 5)
    ids = lambda r: [(x["rule_id"], x["active"]) for x in r["rules"]]
    assert ids(rc1) == ids(rc2)
    differing = {k for k in rc1["effective_settings"] if rc1["effective_settings"][k]["value"] != rc2["effective_settings"][k]["value"]}
    assert differing == {"confusion_response.max_unproductive_questions"}
    assert "allowed number of unproductive questions" in rule(rc1, "H-R03")["text"]
    assert "after one unproductive question" in rule(rc2, "H-R03")["text"]


def test_conflict_example_flags_exactly_two_conflicts():
    rec = assemble(CONFIGS / "conflict-example" / "H1-conflict@1.0-rc1.yaml", [], 3)
    assert len(rec["conflicts"]) == 2
    assert {c["type"] for c in rec["conflicts"]} == {"locked-setting-violation", "required-rule-superseded"}
    lock = next(c for c in rec["conflicts"] if c["type"] == "locked-setting-violation")
    sup = next(c for c in rec["conflicts"] if c["type"] == "required-rule-superseded")
    assert lock["locked_by"] == "U-R01" and lock["rule_id"] == "H1-L09"
    assert sup["target_rule"] == "U-R01" and sup["rule_id"] == "H1-L09"
    assert lock["suggested_compliant_alternative"].startswith("Rewrite the course rule")
    assert rec["eligible_for_release"] is False and rec["release_note"].startswith("BLOCKED")


OUT_OF_BOUNDS = """id: H1
version: "9.0-rc1"
candidate: true
tier: course-version
title: throwaway (test only)
parent: H@1.3
status: hypothetical example
materials: []
rules:
  - id: H1-L77
    class: local
    enforcement: [instruction]
    tags: [confusion-response]
    text: throwaway rule that sets a default outside its bounds
    settings:
      confusion_response.max_unproductive_questions: 5
"""


def test_default_setting_outside_bounds_is_flagged(tmp_path):
    cfg = tmp_path / "H1-oob.yaml"
    cfg.write_text(OUT_OF_BOUNDS, encoding="utf-8")
    rec = assemble(cfg, [], 99)
    assert [(c["type"], c["setting"], c["attempted_value"]) for c in rec["conflicts"]] == [
        ("setting-out-of-bounds", "confusion_response.max_unproductive_questions", 5)]
    assert rec["eligible_for_release"] is False
    # the setting keeps the inherited value; the out-of-bounds value is not applied
    assert rec["effective_settings"]["confusion_response.max_unproductive_questions"]["value"] == 3
    # a target outside demo/ is recorded as given rather than crashing provenance
    assert rec["provenance"]["inputs"] == [str(cfg)]


UNKNOWN_PARENT = """id: H1
version: "9.1-rc1"
candidate: true
tier: course-version
title: throwaway (test only)
parent: H@9.9
status: hypothetical example
materials: []
rules: []
"""


def test_unknown_parent_version_is_a_clean_error_with_no_partial_output(tmp_path):
    cfg = tmp_path / "H1-badparent.yaml"
    cfg.write_text(UNKNOWN_PARENT, encoding="utf-8")
    out = tmp_path / "asm-bad.json"
    proc = subprocess.run([sys.executable, "-I", str(DEMO / "harness" / "assemble.py"),
                           "--target", str(cfg), "--seq", "98", "--out", str(out)],
                          capture_output=True, text=True)
    assert proc.returncode != 0
    assert "H1 pins H@9.9" in proc.stderr
    assert not out.exists()

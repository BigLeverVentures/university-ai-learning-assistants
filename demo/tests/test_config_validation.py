"""Configuration validation (2026-11-02): no committed record moves; a descendant cannot displace an inherited lock or widen an
inherited bound; an override must carry a reviewer, a date and a reason and be recorded by the owning tier or above; only
default rules may be superseded. Every configuration here is a disposable copy under tmp_path."""
import copy
import json

import pytest
import yaml

from assemble import assemble
from common import CONFIGS, DEMO
from conftest import RUN_ALL_ASSEMBLIES

PINS = json.loads((DEMO / "tests" / "fixtures" / "assembly_pins.json").read_text(encoding="utf-8"))   # every committed record: content_hash, eligible_for_release
H1, U = CONFIGS / "H1.yaml", CONFIGS / "U.yaml"
RC3 = CONFIGS / "candidates" / "H@1.4-rc3.yaml"
AUTH, TONE, ALLOW = "authorship.produce_submittable_work", "tone.register", "confusion_response.max_unproductive_questions"


def rule(rid, cls="local", **extra):
    return {"id": rid, "class": cls, "enforcement": ["instruction"], "tags": [], "text": "disposable probe rule", **extra}


def h1_copy(tmp_path, extra_rules, name="H1-probe.yaml", candidate=False):
    cfg = yaml.safe_load(H1.read_text(encoding="utf-8"))
    cfg["version"] = "9.9-probe"
    if candidate:
        cfg["candidate"] = True
    cfg["rules"] = cfg["rules"] + extra_rules
    p = tmp_path / name
    p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return p


def types(rec):
    return [c["type"] for c in rec["conflicts"]]


def setting(rec, key):
    return rec["effective_settings"][key]


def test_every_committed_record_keeps_its_hash_and_eligibility():
    assert len(RUN_ALL_ASSEMBLIES) == 14 and len(PINS) == 14
    for target, subs, seq, aid in RUN_ALL_ASSEMBLIES:
        rec = assemble(DEMO / target, [DEMO / s for s in subs], seq)
        assert rec["content_hash"] == PINS[aid]["content_hash"], aid
        assert rec["eligible_for_release"] == PINS[aid]["eligible_for_release"], aid


@pytest.mark.parametrize("cls", ["local", "required"])
def test_a_course_cannot_unlock_a_university_requirement_through_locks(tmp_path, cls):
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", cls, locks={AUTH: True})]), [], 90)
    assert types(rec) == ["locked-setting-violation"]
    c = rec["conflicts"][0]
    assert (c["rule_id"], c["setting"], c["attempted_value"], c["locked_value"], c["locked_by"]) == ("H1-P1", AUTH, True, False, "U-R01")
    assert "declares `locks:" in c["explanation"]
    assert setting(rec, AUTH)["value"] is False and setting(rec, AUTH)["set_by"] == "U-R01"
    assert rec["locked_settings"][AUTH] == {"value": False, "locked_by": "U-R01", "tier": "U@2.0"}
    assert rec["eligible_for_release"] is False
    assert "locks" not in next(r for r in rec["rules"] if r["rule_id"] == "H1-P1")


def test_a_lock_equal_to_the_inherited_one_changes_nothing(tmp_path):
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", locks={AUTH: False})]), [], 90)
    assert rec["conflicts"] == [] and rec["eligible_for_release"] is True
    assert setting(rec, AUTH)["set_by"] == "U-R01" and rec["locked_settings"][AUTH]["locked_by"] == "U-R01"


def test_a_lock_cannot_escape_inherited_bounds_but_may_sit_inside_them(tmp_path):
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", locks={TONE: "anything"})]), [], 90)
    assert types(rec) == ["setting-out-of-bounds"] and rec["conflicts"][0]["attempted_value"] == "anything"
    assert setting(rec, TONE) == {"value": "friendly-instructive", "set_by": "U-D01", "tier": "U@2.0"} and TONE not in rec["locked_settings"]
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", locks={TONE: "formal-instructive"})], name="ok.yaml"), [], 90)
    assert rec["conflicts"] == [] and rec["locked_settings"][TONE]["value"] == "formal-instructive" and setting(rec, TONE)["locked"] is True


def test_within_is_type_safe():
    from assemble import within
    assert within({"min": 1, "max": 3}, 2) and not within({"min": 1, "max": 3}, True) and not within({"min": 1, "max": 3}, "2")
    assert not within({"min": 1, "max": 3}, [2]) and not within({"min": "1", "max": 3}, 2) and within({"min": 1}, 99)
    assert within({"allowed": ["a", "b"]}, "a") and not within({"allowed": ["a"]}, "") and not within({"allowed": [1, 2]}, True)
    assert not within({"allowed": ""}, "") and not within({"allowed": None}, "x") and not within("x", 1)


def test_bounds_can_be_narrowed_and_the_narrowed_bounds_hold(tmp_path):
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", bounds={TONE: {"allowed": ["formal-instructive"]}}), rule("H1-P2", settings={TONE: "friendly-instructive"})]), [], 90)
    assert types(rec) == ["setting-out-of-bounds"] and "declared by H1-P1" in rec["conflicts"][0]["explanation"]
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", bounds={TONE: {"allowed": ["formal-instructive"]}}), rule("H1-P2", settings={TONE: "formal-instructive"})], name="b.yaml"), [], 90)
    assert rec["conflicts"] == [] and setting(rec, TONE)["value"] == "formal-instructive"
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", bounds={ALLOW: {"min": 1, "max": 2}}), rule("H1-P2", settings={ALLOW: 3})], name="c.yaml"), [], 90)
    assert types(rec) == ["setting-out-of-bounds"]
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", bounds={ALLOW: {"min": 1, "max": 2}}), rule("H1-P2", settings={ALLOW: 2})], name="d.yaml"), [], 90)
    assert rec["conflicts"] == [] and setting(rec, ALLOW)["value"] == 2


def test_the_audit_sequence_widen_then_set_is_blocked(tmp_path):
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", bounds={TONE: {"allowed": ["anything"]}}), rule("H1-P2", settings={TONE: "anything"})]), [], 90)
    assert types(rec) == ["bounds-widened", "setting-out-of-bounds"] and rec["eligible_for_release"] is False
    w = rec["conflicts"][0]
    assert (w["setting"], w["attempted_bounds"], w["inherited_bounds"], w["declared_by"]) == (TONE, {"allowed": ["anything"]}, {"allowed": ["friendly-instructive", "formal-instructive"]}, "U-D01")
    assert "widen at the tier that declared the bounds" in w["explanation"]
    assert setting(rec, TONE)["value"] == "friendly-instructive"


@pytest.mark.parametrize("key,bounds", [
    (TONE, {"allowed": ["friendly-instructive", "formal-instructive", "casual"]}),   # one value added
    (TONE, {"allowed": ""}), (TONE, {"allowed": None}), (TONE, {"allowed": [["friendly-instructive"]]}),
    (ALLOW, {"min": 0, "max": 3}), (ALLOW, {"min": 1, "max": 5}), (ALLOW, {"min": 1}),            # widened, widened, a side dropped
    (ALLOW, {"min": 1, "max": True}), (ALLOW, {"min": 1, "max": "3"}),                             # non-numeric sides
    (ALLOW, {"min": 1, "max": float("nan")}), (ALLOW, {"min": float("nan"), "max": float("nan")}), (ALLOW, {"min": 1, "max": float("inf")}),
    (TONE, {"min": 1, "max": 2}), (ALLOW, {"allowed": [1, 2]}),                                    # kind changed
])
def test_bounds_cannot_be_widened(tmp_path, key, bounds):
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", bounds={key: bounds})]), [], 90)
    assert types(rec) == ["bounds-widened"] and rec["eligible_for_release"] is False
    after = assemble(h1_copy(tmp_path, [rule("H1-P1", bounds={key: bounds}), rule("H1-P2", settings={key: "" if key == TONE else 9})], name="after.yaml"), [], 90)
    assert types(after) == ["bounds-widened", "setting-out-of-bounds"]        # the inherited bounds keep checking


def test_narrows_helper_directly():
    from assemble import narrows
    assert narrows({"allowed": ["a"]}, {"allowed": ["a", "b"]}) and not narrows({"allowed": ["c"]}, {"allowed": ["a", "b"]})
    assert not narrows({"allowed": [1]}, {"allowed": [True]}) and narrows({"min": 1, "max": 2}, {"min": 1, "max": 3})
    assert not narrows({"min": 1, "max": 2}, {"min": "1", "max": 3}) and not narrows("x", {"min": 1}) and not narrows({"allowed": ["a"], "min": 1}, {"allowed": ["a"]})
    assert narrows({"min": 2}, {"min": 1}) and not narrows({"max": 2}, {"min": 1})


def override(field="text", **changes):
    e = {"conflict": "prose-setting-mismatch", "rule_id": "H-R03", "field": field, "setting": ALLOW, "prose_value": 1, "effective_value": 3,
         "reviewer": "history tier owner (fictional)", "date": "2026-11-02", "reason": "diagnostic candidate: prose and setting disagree on purpose"}
    e.update(changes)
    return e


def rc3_copy(tmp_path, overrides, name="rc3.yaml", raw_yaml=None):
    cfg = yaml.safe_load(RC3.read_text(encoding="utf-8"))
    cfg["overrides"] = overrides
    text = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
    if raw_yaml:
        text = text + raw_yaml
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def both_mismatches_open(rec):
    return sorted(c["field"] for c in rec["conflicts"] if c["type"] == "prose-setting-mismatch") == ["exit_condition.trigger", "text"]


@pytest.mark.parametrize("changes,field", [
    ({"reviewer": ""}, "reviewer"), ({"reviewer": "   "}, "reviewer"), ({"reviewer": None}, "reviewer"), ({"reviewer": 5}, "reviewer"),
    ({"reason": ""}, "reason"),
    ({"date": ""}, "date"), ({"date": "not a date"}, "date"), ({"date": "2026-13-01"}, "date"), ({"date": "20261102"}, "date"), ({"date": "2026-11-02T10:00"}, "date"),
])
def test_an_override_must_say_who_when_and_why(tmp_path, changes, field):
    rec = assemble(H1, [rc3_copy(tmp_path, [override("text", **changes), override("exit_condition.trigger", **changes)])], 6)
    stale = [c for c in rec["conflicts"] if c["type"] == "stale-override"]
    assert len(stale) == 2 and all(f"no usable {field}" in c["explanation"] for c in stale)
    assert both_mismatches_open(rec) and "conflicts_overridden" not in rec


def test_two_failing_fields_are_named_in_fixed_order(tmp_path):
    rec = assemble(H1, [rc3_copy(tmp_path, [override("text", reviewer="", date="x")])], 6)
    assert "no usable reviewer, date:" in next(c["explanation"] for c in rec["conflicts"] if c["type"] == "stale-override")


def test_unquoted_yaml_dates_never_crash_and_are_recorded_as_strings(tmp_path):
    cfg = yaml.safe_load(RC3.read_text(encoding="utf-8"))
    cfg_text = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
    block = ("overrides:\n- conflict: prose-setting-mismatch\n  rule_id: H-R03\n  field: {field}\n  setting: " + ALLOW +
             "\n  prose_value: 1\n  effective_value: 3\n  reviewer: {reviewer}\n  date: {date}\n  reason: fine\n")
    def build(name, overrides_yaml):
        p = tmp_path / name
        p.write_text(cfg_text + overrides_yaml, encoding="utf-8")
        return assemble(H1, [p], 6)
    unq = build("unquoted.yaml", block.format(field="text", reviewer="r", date="2026-11-02") + block.format(field="exit_condition.trigger", reviewer="r", date="2026-11-02").replace("overrides:\n", ""))
    assert unq["conflicts"] == [] and len(unq["conflicts_overridden"]) == 2
    assert all(o["override"]["date"] == "2026-11-02" for o in unq["conflicts_overridden"])
    q = build("quoted.yaml", block.format(field="text", reviewer="r", date="'2026-11-02'") + block.format(field="exit_condition.trigger", reviewer="r", date="'2026-11-02'").replace("overrides:\n", ""))
    assert q["content_hash"] == unq["content_hash"]                                   # an unquoted and a quoted date hash the same
    dt = build("datetime.yaml", block.format(field="text", reviewer="r", date="2026-11-02 10:00:00"))
    assert [c["type"] for c in dt["conflicts"]].count("stale-override") == 1 and "no usable date" in dt["conflicts"][-1]["explanation"] and both_mismatches_open(dt)
    rv = build("reviewer-date.yaml", block.format(field="text", reviewer="2026-11-02", date="'2026-11-02'"))
    assert [c["type"] for c in rv["conflicts"]] == ["prose-setting-mismatch"] and rv["conflicts_overridden"][0]["override"]["reviewer"] == "2026-11-02"
    dup = build("dup.yaml", block.format(field="text", reviewer="r", date="2026-11-02") + block.format(field="text", reviewer="r", date="'2026-11-02'").replace("overrides:\n", ""))
    assert [c["type"] for c in dup["conflicts"]].count("stale-override") == 2 and all("more than once" in c["explanation"] for c in dup["conflicts"] if c["type"] == "stale-override")
    miss = build("missing.yaml", block.format(field="text", reviewer="r", date="2026-11-02").replace("  reason: fine\n", ""))
    assert [c["type"] for c in miss["conflicts"]].count("stale-override") == 1 and "missing reason" in miss["conflicts"][-1]["explanation"]
    bare = build("bare.yaml", "overrides:\n- 2026-11-02\n")
    assert "is not a mapping" in next(c["explanation"] for c in bare["conflicts"] if c["type"] == "stale-override")
    nested = build("nested.yaml", block.format(field="text", reviewer="r", date="'2026-11-02'").replace("prose_value: 1", "prose_value: [2026-11-02]"))
    assert "matches no open" in next(c["explanation"] for c in nested["conflicts"] if c["type"] == "stale-override")
    json.dumps(nested["conflicts"]); json.dumps(bare["conflicts"]); json.dumps(dt["conflicts"])   # everything stored is JSON


def test_blank_overrides_cannot_make_a_released_record_eligible(tmp_path):
    mism = rule("H1-P1", text="After two unproductive questions, explain.")           # prose 2 against the effective 3
    blank = [override("text", rule_id="H1-P1", prose_value=2, effective_value=3, reviewer="", reason="", date="")]
    rec = assemble(h1_copy(tmp_path, [mism], name="m.yaml"), [], 90)
    assert types(rec) == ["prose-setting-mismatch"] and rec["eligible_for_release"] is False
    cfg = yaml.safe_load((tmp_path / "m.yaml").read_text(encoding="utf-8"))
    cfg["overrides"] = blank
    (tmp_path / "m-blank.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    rec = assemble(tmp_path / "m-blank.yaml", [], 90)
    assert rec["eligible_for_release"] is False and sorted(types(rec)) == ["prose-setting-mismatch", "stale-override"]
    cfg["overrides"] = [override("text", rule_id="H1-P1", prose_value=2, effective_value=3)]
    (tmp_path / "m-good.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    rec = assemble(tmp_path / "m-good.yaml", [], 90)
    assert rec["conflicts"] == [] and rec["eligible_for_release"] is True and len(rec["conflicts_overridden"]) == 1


def test_an_override_counts_only_from_the_owning_tier_or_above(tmp_path):
    entries = [override("text"), override("exit_condition.trigger")]
    rec = assemble(h1_copy(tmp_path, [], name="h1-over.yaml"), [RC3], 6)                       # no override anywhere: blocked
    assert both_mismatches_open(rec)
    cfg = yaml.safe_load(H1.read_text(encoding="utf-8")); cfg["overrides"] = entries
    (tmp_path / "h1-below.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    rec = assemble(tmp_path / "h1-below.yaml", [RC3], 6)                                        # declared in the course, below H
    assert both_mismatches_open(rec) and [c["type"] for c in rec["conflicts"]].count("stale-override") == 2
    assert all("not recorded by the tier that owns H-R03" in c["explanation"] for c in rec["conflicts"] if c["type"] == "stale-override")
    rec = assemble(H1, [rc3_copy(tmp_path, entries)], 6)                                         # declared by the owning tier
    assert rec["conflicts"] == [] and len(rec["conflicts_overridden"]) == 2
    u = yaml.safe_load(U.read_text(encoding="utf-8")); u["overrides"] = entries
    (tmp_path / "U.yaml").write_text(yaml.safe_dump(u, sort_keys=False, allow_unicode=True), encoding="utf-8")
    rec = assemble(H1, [RC3, tmp_path / "U.yaml"], 6)                                            # declared by an ancestor
    assert rec["conflicts"] == [] and len(rec["conflicts_overridden"]) == 2 and all(o["override"]["tier"] == "U@2.0" for o in rec["conflicts_overridden"])


def test_a_course_cannot_supersede_its_own_local_rule_and_defaults_still_can_be(tmp_path):
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", supersedes=["H1-L01"])]), [], 90)
    assert types(rec) == ["local-rule-superseded"] and rec["eligible_for_release"] is False
    c = rec["conflicts"][0]
    assert (c["target_rule"], c["target_class"]) == ("H1-L01", "local") and "Only default rules may be superseded" in c["explanation"]
    assert next(x for x in rec["rules"] if x["rule_id"] == "H1-L01")["active"] is True
    base = assemble(H1, [], 1)
    assert next(x for x in base["rules"] if x["rule_id"] == "U-D03")["active"] is False          # H-R03 still supersedes the default U-D03
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", supersedes=["NO-SUCH-RULE"])], name="unknown.yaml"), [], 90)
    assert rec["conflicts"] == [] and any("unknown rule NO-SUCH-RULE" in w for w in rec["warnings"])


def test_nan_and_infinity_are_outside_every_bound(tmp_path):
    from assemble import within
    nan, inf = float("nan"), float("inf")
    assert not within({"min": 1, "max": 3}, nan) and not within({"min": 1, "max": 3}, inf) and not within({"min": nan, "max": 3}, 2)
    assert not within({"min": 1, "max": 3}, 10 ** 400) and not within({"min": 1, "max": 10 ** 400}, 2)   # an int beyond float range
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", settings={ALLOW: nan})]), [], 90)
    assert types(rec) == ["setting-out-of-bounds"] and setting(rec, ALLOW)["value"] == 3
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", locks={ALLOW: nan})], name="lock.yaml"), [], 90)
    assert types(rec) == ["setting-out-of-bounds"]
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", bounds={ALLOW: {"min": 1, "max": nan}}), rule("H1-P2", settings={ALLOW: 99})], name="w.yaml"), [], 90)
    assert types(rec) == ["bounds-widened", "setting-out-of-bounds"] and setting(rec, ALLOW)["value"] == 3


def test_a_setting_or_lock_of_zero_does_not_pass_as_false(tmp_path):
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", settings={AUTH: 0})]), [], 90)
    assert types(rec) == ["locked-setting-violation"] and setting(rec, AUTH) == {"value": False, "set_by": "U-R01", "tier": "U@2.0", "locked": True}
    rec = assemble(h1_copy(tmp_path, [rule("H1-P1", locks={AUTH: 0})], name="l.yaml"), [], 90)
    assert types(rec) == ["locked-setting-violation"] and rec["locked_settings"][AUTH]["locked_by"] == "U-R01"


def test_a_course_relabelled_as_its_parent_owns_nothing(tmp_path):
    cfg = yaml.safe_load(H1.read_text(encoding="utf-8"))
    cfg["id"], cfg["version"] = "H", "1.4-rc3"                                   # the course pretends to be the owning tier
    cfg["overrides"] = [override("text"), override("exit_condition.trigger")]
    p = tmp_path / "impostor.yaml"
    p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    rec = assemble(p, [RC3], 6)
    assert "duplicate-tier-version" in types(rec) and both_mismatches_open(rec) and rec["eligible_for_release"] is False
    assert [c["type"] for c in rec["conflicts"]].count("stale-override") == 2 and "owns nothing" in rec["conflicts"][-1]["explanation"]

"""Release block and reviewer override: rc3 is blocked and names the hash its runs used; a matching override
restores eligibility apart from the candidate status; a stale override blocks; released records keep their hashes."""
import copy
import json

import pytest
import yaml

from assemble import DIAGNOSTIC_CANDIDATES, OVERRIDE_FIELDS, assemble
from common import CONFIGS, DEMO, canonical_json, sha256_text
from conftest import RUN_ALL_ASSEMBLIES

PINS = json.loads((DEMO / "tests" / "fixtures" / "assembly_pins.json").read_text(encoding="utf-8"))   # content_hash and eligibility of every committed record
RC3 = CONFIGS / "candidates" / "H@1.4-rc3.yaml"
H1, H2 = CONFIGS / "H1.yaml", CONFIGS / "H2.yaml"
KEY = "confusion_response.max_unproductive_questions"


def override(field, **changes):
    e = {"conflict": "prose-setting-mismatch", "rule_id": "H-R03", "field": field, "setting": KEY, "prose_value": 1, "effective_value": 3,
         "reviewer": "history tier owner (fictional)", "date": "2026-11-02", "reason": "diagnostic candidate: prose and setting disagree on purpose"}
    e.update(changes)
    return e


def rc3_copy(tmp_path, overrides=None, allowance=None, name="rc3.yaml"):
    cfg = yaml.safe_load(RC3.read_text(encoding="utf-8"))
    if overrides is not None:
        cfg["overrides"] = overrides
    if allowance is not None:
        next(r for r in cfg["rules"] if r["id"] == "H-R03")["settings"][KEY] = allowance
    p = tmp_path / name
    p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return p


def mismatches(rec):
    return sorted((c["field"], c["prose_value"], c["effective_value"]) for c in rec["conflicts"] if c["type"] == "prose-setting-mismatch")


RENDERED_CANDIDATES = {"asm-H1-0007", "asm-H2-0005"}   # rc4: render-from-settings


def test_released_and_earlier_records_keep_their_hashes():
    checked = 0
    for target, subs, seq, aid in RUN_ALL_ASSEMBLIES:
        if aid in DIAGNOSTIC_CANDIDATES["H@1.4-rc3"]["hashes"] or aid in RENDERED_CANDIDATES:
            continue
        checked += 1
        rec = assemble(DEMO / target, [DEMO / s for s in subs], seq)
        # the content hash covers the release note and the conflicts, so a match here keeps what the old comparison checked
        assert rec["content_hash"] == PINS[aid]["content_hash"], aid
        assert rec["eligible_for_release"] == PINS[aid]["eligible_for_release"], aid
        assert "conflicts_overridden" not in rec, aid
    assert checked == 10


def test_every_committed_assembly_record_matches_the_fixture():
    committed = sorted(p.stem for p in (DEMO / "out" / "assemblies").glob("*.json"))
    assert committed == sorted(PINS) and len(committed) == 14
    for aid in committed:
        rec = json.loads((DEMO / "out" / "assemblies" / f"{aid}.json").read_text(encoding="utf-8"))
        assert (rec["content_hash"], rec["eligible_for_release"]) == (PINS[aid]["content_hash"], PINS[aid]["eligible_for_release"]), aid


def test_rc3_is_blocked_and_names_the_hash_its_runs_used():
    for target, seq, aid in ((H1, 6, "asm-H1-0006"), (H2, 4, "asm-H2-0004")):
        rec = assemble(target, [RC3], seq)
        assert mismatches(rec) == [("exit_condition.trigger", 1, 3), ("text", 1, 3)]
        assert all(c["rule_id"] == "H-R03" and c["setting"] == KEY for c in rec["conflicts"])
        assert rec["eligible_for_release"] is False
        note = rec["release_note"]
        assert note.startswith("BLOCKED: prose–setting mismatch in H-R03 (H@1.4-rc3): the prose says 1 in text, 1 in exit_condition.trigger; "
                               f"{KEY} is 3.")
        old = DIAGNOSTIC_CANDIDATES["H@1.4-rc3"]["hashes"][aid]
        assert old in note and "run 2 and run 3" in note.lower() and rec["content_hash"] != old
        body = {k: v for k, v in rec.items() if k not in ("content_hash", "provenance", "lint")}
        assert sha256_text(canonical_json(body)) == rec["content_hash"]
        assert [f["severity"] for f in rec["lint"]["findings"]] == ["conflict", "conflict"]   # the lint block stays, outside the hash


def test_matching_overrides_move_both_conflicts_and_leave_only_the_candidate_status(tmp_path):
    rec = assemble(H1, [rc3_copy(tmp_path, [override("text"), override("exit_condition.trigger")])], 6)
    assert rec["conflicts"] == [] and len(rec["conflicts_overridden"]) == 2
    assert {o["conflict"]["field"] for o in rec["conflicts_overridden"]} == {"text", "exit_condition.trigger"}
    assert all(o["override"]["tier"] == "H@1.4-rc3" and set(OVERRIDE_FIELDS) <= set(o["override"]) for o in rec["conflicts_overridden"])
    assert rec["eligible_for_release"] is False and "candidate" in rec["release_note"] and "2 conflict(s) overridden" in rec["release_note"]
    reworded = assemble(H1, [rc3_copy(tmp_path, [override("text"), override("exit_condition.trigger", reason="another reason")], name="b.yaml")], 6)
    assert reworded["content_hash"] != rec["content_hash"]                       # overrides are part of the content hash


def test_one_override_does_not_cover_the_other_field(tmp_path):
    rec = assemble(H1, [rc3_copy(tmp_path, [override("text")])], 6)
    assert mismatches(rec) == [("exit_condition.trigger", 1, 3)] and len(rec["conflicts_overridden"]) == 1
    assert rec["eligible_for_release"] is False and rec["release_note"].startswith("BLOCKED")


def test_override_goes_stale_when_the_setting_moves(tmp_path):
    rec = assemble(H1, [rc3_copy(tmp_path, [override("text"), override("exit_condition.trigger")], allowance=2)], 6)
    assert mismatches(rec) == [("exit_condition.trigger", 1, 2), ("text", 1, 2)]
    assert [c["type"] for c in rec["conflicts"]].count("stale-override") == 2 and "conflicts_overridden" not in rec
    assert rec["eligible_for_release"] is False


@pytest.mark.parametrize("entries,reason", [
    ([override("text", rule_id="H-R02")], "matches no open"),                                   # no such finding
    ([override("text", conflict="locked-setting-violation")], "matches no open"),                 # another type
    ([{k: v for k, v in override("text").items() if k != "reason"}], "missing reason"),            # missing field
    ([override("text"), override("text")], "more than once"),                                     # duplicate
])
def test_stale_overrides_block(tmp_path, entries, reason):
    rec = assemble(H1, [rc3_copy(tmp_path, entries)], 6)
    stale = [c for c in rec["conflicts"] if c["type"] == "stale-override"]
    assert stale and all(reason in c["explanation"] for c in stale), [c["explanation"] for c in stale]
    assert rec["eligible_for_release"] is False
    assert mismatches(rec) == [("exit_condition.trigger", 1, 3), ("text", 1, 3)]               # nothing was covered


def test_override_on_a_released_configuration_with_no_mismatch_blocks(tmp_path):
    cfg = yaml.safe_load((CONFIGS / "U.yaml").read_text(encoding="utf-8"))
    cfg["overrides"] = [override("text", rule_id="U-D02", prose_value=2, effective_value=2)]
    p = tmp_path / "U.yaml"
    p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    rec = assemble(p, [], 1)
    assert [c["type"] for c in rec["conflicts"]] == ["stale-override"] and rec["eligible_for_release"] is False
    assert rec["release_note"] == "BLOCKED: conflicts must be resolved by human review."


def test_a_malformed_override_entry_blocks_as_a_conflict_not_a_crash(tmp_path):
    cfg = yaml.safe_load(RC3.read_text(encoding="utf-8"))
    cfg["overrides"] = ["not a mapping", override("text")]
    p = tmp_path / "rc3.yaml"
    p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    rec = assemble(H1, [p], 6)
    stale = [c for c in rec["conflicts"] if c["type"] == "stale-override"]
    assert len(stale) == 1 and "is not a mapping" in stale[0]["explanation"] and len(rec["conflicts_overridden"]) == 1
    assert rec["eligible_for_release"] is False

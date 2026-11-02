"""Render-from-settings: rc4's placeholders render to rc2's prose byte for byte, follow the setting when it
changes, and an unrenderable placeholder blocks the record."""
import yaml

from assemble import assemble, render
from common import CONFIGS, DEMO
from run import assistant_system_prompt

RC2, RC4 = CONFIGS / "candidates" / "H@1.4-rc2.yaml", CONFIGS / "candidates" / "H@1.4-rc4.yaml"
H1 = CONFIGS / "H1.yaml"
KEY = "confusion_response.max_unproductive_questions"


def rule(rec, rid):
    return next(r for r in rec["rules"] if r["rule_id"] == rid)


def rc4_copy(tmp_path, allowance=None, text=None, trigger=None):
    cfg = yaml.safe_load(RC4.read_text(encoding="utf-8"))
    r = next(x for x in cfg["rules"] if x["id"] == "H-R03")
    if allowance is not None:
        r["settings"][KEY] = allowance
    if text is not None:
        r["text"] = text
    if trigger is not None:
        r["exit_condition"]["trigger"] = trigger
    p = tmp_path / "rc4.yaml"
    p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return p


def test_rc4_renders_to_rc2_prose_byte_for_byte():
    rc2, rc4 = assemble(H1, [RC2], 5), assemble(H1, [RC4], 7)
    h2, h4 = rule(rc2, "H-R03"), rule(rc4, "H-R03")
    assert h4["text"] == h2["text"] and h4["exit_condition"]["trigger"] == h2["exit_condition"]["trigger"]
    assert "{" in h4["text_template"] and "{" in h4["exit_condition"]["trigger_template"]
    assert "text_template" not in h2 and "trigger_template" not in h2["exit_condition"]      # untemplated rules gain no key
    assert rc4["conflicts"] == [] and rc4["eligible_for_release"] is False and rc4["assembly_id"] == "asm-H1-0007"
    assert rc4["contains_candidate_versions"] == ["H@1.4-rc4"]


def test_rc4_follows_its_setting_with_no_mismatch(tmp_path):
    rec = assemble(H1, [rc4_copy(tmp_path, allowance=3)], 7)
    h = rule(rec, "H-R03")
    assert "after three unproductive questions, if the student" in h["text"]
    assert h["exit_condition"]["trigger"] == "student signals confusion after 3 unproductive source-directed questions"
    assert rec["conflicts"] == [] and rec["lint"]["findings"] == [] and rec["effective_settings"][KEY]["value"] == 3


def test_unrenderable_placeholders_block(tmp_path):
    rec = assemble(H1, [rc4_copy(tmp_path, text="Exit condition: after {no.such.setting|word} unproductive question{no.such.setting|s}.")], 7)
    kinds = [(c["type"], c["field"]) for c in rec["conflicts"]]
    assert kinds == [("unrenderable-placeholder", "text")] * 2 and rec["eligible_for_release"] is False
    assert "{no.such.setting|word}" in rule(rec, "H-R03")["text"]                             # the field keeps its template
    rec = assemble(H1, [rc4_copy(tmp_path, trigger="after {confusion_response.max_unproductive_questions|shout} questions")], 7)
    assert [(c["type"], c["field"]) for c in rec["conflicts"]] == [("unrenderable-placeholder", "exit_condition.trigger")]
    assert "unknown filter 'shout'" in rec["conflicts"][0]["explanation"]
    assert rec["release_note"] == "BLOCKED: conflicts must be resolved by human review."


def test_render_edges():
    st = {KEY: {"value": 2}, "flag": {"value": True}, "name": {"value": "x"}, "many": {"value": [1]}}
    assert render("after {confusion_response.max_unproductive_questions|word} question{confusion_response.max_unproductive_questions|s}", st) == ("after two questions", [])
    assert render("{confusion_response.max_unproductive_questions}", {KEY: {"value": 7}}) == ("7", [])
    assert render("{confusion_response.max_unproductive_questions|word}", {KEY: {"value": 7}}) == ("7", [])   # beyond five: digits
    assert render("{flag|word}", st)[1] == ["{flag|word}: value true is not an integer"]                        # a bool is not an int
    assert render("{name|s}", st)[1] and render("{many}", st)[1]
    text, problems = render("after {{confusion_response.max_unproductive_questions}} questions", st)
    assert problems and text.startswith("after {{")                                                          # nested braces: unchanged
    assert render("a } b", st)[1] == ["a brace is left after rendering (nested or unbalanced placeholder)"]
    assert render("no placeholders", st) == ("no placeholders", [])


def test_system_prompt_carries_the_rendered_text_and_no_brace():
    rec = assemble(H1, [RC4], 7)
    scenario = {"task": "t", "source_texts": [], "sources_available": []}
    prompt = assistant_system_prompt(rec, scenario)
    assert "after one unproductive question, if the student signals confusion" in prompt and "{" not in prompt

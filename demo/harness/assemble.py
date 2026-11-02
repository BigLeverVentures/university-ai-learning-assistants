"""Assemble a learning-assistant configuration from a course version and its ancestor chain.

Usage (from demo/):
  python3 -I harness/assemble.py --target configs/H1.yaml --seq 1 --out out/assemblies/asm-H1-0001.json
  python3 -I harness/assemble.py --target configs/H1.yaml --substitute configs/candidates/H@1.4-rc1.yaml ...

Merge semantics:
  required  set by an ancestor; descendants cannot redefine, override or supersede it, and cannot
            set a setting it `locks`. Violations are conflicts: they block release.
  default   ancestor-set; descendants may re-set its `settings` within declared `bounds`, or
            `supersedes` it (the superseded rule becomes inactive in the assembly).
  local     descendant addition; no effect on ancestors; cannot be superseded (only `default` rules can).
Inherited constraints (2026-11-02): a descendant `locks:` entry cannot re-lock an inherited lock to another value
(`locked-setting-violation`) or lock a value outside inherited bounds (`setting-out-of-bounds`); a descendant `bounds:` entry
may only narrow the bounds in force (same kind; `allowed` a list subset; min/max within), else `bounds-widened`. The inherited
lock or bounds stand in every such case. Superseding a `local` rule is `local-rule-superseded`.
Prose–setting mismatch: a number in an active rule's prose or exit-condition trigger that disagrees
with the effective setting it names is a conflict and blocks release, unless a configuration in the chain records a reviewer
override naming that exact finding (`overrides:`; see OVERRIDE_FIELDS), with a non-blank reviewer and reason and a real
YYYY-MM-DD date, declared by the tier that owns the rule or an ancestor of it. An override that names no open finding, lacks
usable fields, is duplicated or is declared below the owning tier is itself a conflict (`stale-override`).
Render-from-settings: a rule's `text` and `exit_condition.trigger` may carry placeholders `{setting.key}`,
`{setting.key|word}` (1 to 5 as a word) or `{setting.key|s}` ("" at 1, "s" otherwise), rendered from the effective settings at
assembly time. The rendered text is what the model sees and what the content hash covers; the template is kept beside it
(`text_template`, `exit_condition.trigger_template`) only where a placeholder was used, so records without placeholders are
unchanged. An unknown key or filter, a value the filter cannot render, or a brace left over is an `unrenderable-placeholder`
conflict; the field keeps its template text and the record is blocked.
The output is an ASSEMBLY RECORD (JSON) — the unit to which all evidence is attributed.
Executed demonstration: deterministic; no model is called.
"""
import argparse
import datetime
import math
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # needed under python3 -I
from json import dumps as j  # noqa: E402  (JSON-style true/false in messages)
from common import (CONFIGS, canonical_json, load_yaml, now_iso, rel, sha256_text,  # noqa: E402
                    version_label, write_json)

# Prose–setting agreement lint (scope: the unproductive/diagnostic question allowance only).
# One entry per setting: a number (word one to five, or digits), up to two hyphen/word tokens, the qualifier, at most one more
# word, then question(s). Matches "after one unproductive question", "1 unproductive source-directed question", "at most one
# diagnostic question", "the allowed number (3) of unproductive ... questions"; not "ask one orienting question" (an orienting
# question does not count toward the allowance). A range ("one or two", "1-2", "one to two") is never read as one number.
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
_NUM = r"(?P<num>\b(?:one|two|three|four|five|\d+)\b)"
PROSE_SETTING_PATTERNS = {
    "confusion_response.max_unproductive_questions": re.compile(
        _NUM + r"\)?(?P<mid>(?:\s+[\w-]+){0,2}?)\s+(?:unproductive|diagnostic)(?:\s+[\w-]+)?\s+questions?\b", re.I),
}


def _as_int(token: str) -> "int | None":
    t = token.lower()
    return NUMBER_WORDS.get(t) if not t.isdigit() else int(t)


def lint_prose_settings(rules: list, effective_settings: dict) -> list:
    """Numbers in an active rule's prose (its `text`, which the model sees, and its `exit_condition.trigger`) that refer to a
    setting in PROSE_SETTING_PATTERNS and disagree with that setting's effective value. Heuristic; each finding
    is a release-blocking conflict. Order: rule order, then field, then pattern key, then position in the text."""
    findings = []
    for rec in rules:
        if not rec.get("active"):
            continue
        fields = [("text", rec.get("text") or "")]
        trig = (rec.get("exit_condition") or {}).get("trigger") if isinstance(rec.get("exit_condition"), dict) else None
        if trig:
            fields.append(("exit_condition.trigger", " ".join(str(trig).split())))
        for field, text in fields:
            for key in sorted(PROSE_SETTING_PATTERNS):
                if key not in effective_settings:
                    continue
                effective = effective_settings[key]["value"]
                for m in PROSE_SETTING_PATTERNS[key].finditer(text):
                    before, after = text[:m.start("num")], text[m.end("num"):]
                    if (any(_as_int(w) is not None for w in m.group("mid").split())          # "one or two ..."
                            or re.search(r"\b(?:one|two|three|four|five|\d+)\s*(?:[-–]|to\b|or\b)\s*$", before, re.I)   # upper end of "1-2", "one to two"
                            or re.match(r"\s*(?:[-–]|(?:to|or)\b)", after, re.I)):           # the lower end
                        continue
                    value = _as_int(m.group("num"))
                    if value is not None and value != effective:
                        findings.append({"type": "prose-setting-mismatch", "rule": rec["rule_id"], "tier": rec["tier"], "field": field,
                                         "setting": key, "prose_value": value, "effective_value": effective,
                                         "phrase": m.group(0), "severity": "conflict"})
    return findings


# A reviewer override names one prose–setting finding exactly; the four binding fields keep an override from
# covering a finding it did not review (a changed setting or prose, or the other field of the same rule).
OVERRIDE_FIELDS = ("conflict", "rule_id", "field", "setting", "prose_value", "effective_value", "reviewer", "date", "reason")
OVERRIDE_MATCH = ("rule_id", "field", "setting", "prose_value", "effective_value")
# Candidates run as deliberate diagnostics before the mismatch became a conflict: their committed cells carry the content hash
# their records had then. The note below names it so the history stays readable from the record itself.
DIAGNOSTIC_CANDIDATES = {
    "H@1.4-rc3": {"runs": "run 2 and run 3", "why": "rc2's prose with the allowance left at 3, to test prose against setting",
                  "hashes": {"asm-H1-0006": "sha256:d92845bc454001ac19ba2851f015c2ed2357c74dfc16eb98e71cd2dcd16513d7",
                             "asm-H2-0004": "sha256:2de8abda528a147c3c3cfe6076584a6dc8809db0e48cfe41a8aadb6e81fa0b92"}},
}


RENDER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
PLACEHOLDER = re.compile(r"\{([^{}|]+)(?:\|([^{}|]*))?\}")


def render(template: str, settings: dict) -> tuple:
    """Replace each `{key}` / `{key|filter}` with the effective value of `key`. Returns (text, problems); with any problem the
    text is the template unchanged. Filters: `word` (an int 1 to 5 as a word, other ints as digits), `s` (plural suffix)."""
    problems = []

    def value_of(key):
        if key not in settings:
            problems.append(f"{{{key}}}: no effective setting of that name")
            return None
        return settings[key]["value"]

    def sub(m):
        key, filt = m.group(1).strip(), m.group(2)
        v = value_of(key)
        if v is None:
            return m.group(0)
        if filt is None:
            if isinstance(v, (dict, list)) or isinstance(v, bool):
                problems.append(f"{{{key}}}: value {j(v)} is not a number or a string")
                return m.group(0)
            return str(v)
        if filt in ("word", "s"):
            if type(v) is not int:
                problems.append(f"{{{key}|{filt}}}: value {j(v)} is not an integer")
                return m.group(0)
            return (RENDER_WORDS.get(v, str(v))) if filt == "word" else ("" if v == 1 else "s")
        problems.append(f"{{{key}|{filt}}}: unknown filter {filt!r} (known: word, s)")
        return m.group(0)

    text = PLACEHOLDER.sub(sub, template)
    if not problems and ("{" in text or "}" in text):
        problems.append("a brace is left after rendering (nested or unbalanced placeholder)")
    return (template if problems else text), problems


def render_rules(rules: list, settings: dict) -> list:
    """Render placeholders in every active rule's text and exit-condition trigger. Returns the conflicts raised."""
    conflicts = []
    for rec in rules:
        if not rec.get("active"):   # a superseded rule's text never reaches the model; the mismatch check skips it too
            continue
        if "{" in rec["text"] or "}" in rec["text"]:
            text, problems = render(rec["text"], settings)
            rec["text_template"], rec["text"] = rec["text"], text
            for pr in problems:
                conflicts.append(conflict("unrenderable-placeholder", rec, f"Rule {rec['rule_id']} (tier {rec['tier']}) text: {pr}.", field="text"))
        ec = rec.get("exit_condition")
        if isinstance(ec, dict) and isinstance(ec.get("trigger"), str) and ("{" in ec["trigger"] or "}" in ec["trigger"]):
            trig, problems = render(ec["trigger"], settings)
            rec["exit_condition"] = {**ec, "trigger": trig, "trigger_template": ec["trigger"]}
            for pr in problems:
                conflicts.append(conflict("unrenderable-placeholder", rec, f"Rule {rec['rule_id']} (tier {rec['tier']}) exit_condition.trigger: {pr}.",
                                          field="exit_condition.trigger"))
    return conflicts


def mismatch_conflicts(findings: list, rules: list) -> list:
    """One conflict per prose–setting finding, in finding order."""
    by_id = {r["rule_id"]: r for r in rules}
    out = []
    for f in findings:
        rec = by_id[f["rule"]]
        out.append(conflict("prose-setting-mismatch", rec, (
            f"Rule {f['rule']} (tier {f['tier']}) says {f['prose_value']} in its {f['field']} (\"{f['phrase']}\"), but the effective "
            f"setting {f['setting']} is {f['effective_value']}. In run 2 the assistant followed the prose, not the setting, so the two "
            f"must agree before release: revise the prose or the setting, or record a reviewer override naming this finding."),
            field=f["field"], setting=f["setting"], prose_value=f["prose_value"], effective_value=f["effective_value"],
            phrase=f["phrase"], resolution="process: human review; release blocked unless a reviewer override names this finding"))
    return out


DATE_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def iso_dates(obj: object) -> object:
    """A copy of a loaded YAML value with every date or datetime, at any depth and in mapping keys too, replaced by its ISO string."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {(k.isoformat() if isinstance(k, (datetime.date, datetime.datetime)) else k): iso_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [iso_dates(v) for v in obj]
    return obj


def override_field_problems(e: dict) -> list[str]:
    """The reviewer fields of an override that carry no usable content, in fixed order: reviewer and reason must be strings with
    text; date must be a YYYY-MM-DD string naming a real date."""
    problems = []
    for k in ("reviewer", "date", "reason"):
        v = e.get(k)
        if k == "date":
            ok = isinstance(v, str) and DATE_SHAPE.fullmatch(v) is not None
            if ok:
                try:
                    datetime.date.fromisoformat(v)
                except ValueError:
                    ok = False
            if not ok:
                problems.append(k)
        elif not (isinstance(v, str) and v.strip()):
            problems.append(k)
    return problems


def apply_overrides(chain: list, conflicts: list, rules: list) -> tuple:
    """Read `overrides:` from every configuration in the chain. An entry that names one open prose–setting mismatch exactly
    (OVERRIDE_MATCH), carries a reviewer, a real date and a reason, and is declared by the tier that owns the rule or an
    ancestor of it, moves that conflict to the overridden list; any other entry (another type, no such finding, a missing or
    blank field, a duplicate, a descendant's entry) is a `stale-override` conflict. Dates are normalised to ISO strings before
    anything is compared or stored. Returns (remaining conflicts, overridden entries)."""
    by_id = {r["rule_id"]: r for r in rules}
    labels = [version_label(cfg) for cfg in chain]
    tier_index = {l: i for i, l in enumerate(labels) if labels.count(l) == 1}   # a repeated label owns nothing (it is already a conflict)
    entries = [(version_label(cfg), iso_dates(e)) for cfg in chain for e in (cfg.get("overrides") or [])]
    remaining, overridden, stale = list(conflicts), [], []
    for tier, e in entries:
        if not isinstance(e, dict):
            stale.append(conflict("stale-override", {"rule_id": None, "tier": tier, "class": None},
                                  f"Override in {tier} is not a mapping ({j(e)}); an override is a mapping of {', '.join(OVERRIDE_FIELDS)}.", override=e))
            continue
    keys = [tuple(j(e.get(k), sort_keys=True) for k in OVERRIDE_FIELDS) if isinstance(e, dict) else None for _, e in entries]
    for (tier, e), key in zip(entries, keys):
        if key is None:
            continue
        rec = by_id.get(e.get("rule_id"), {"rule_id": e.get("rule_id"), "tier": tier, "class": None})
        missing = [k for k in OVERRIDE_FIELDS if k not in e]
        if missing:
            stale.append(conflict("stale-override", rec, f"Override in {tier} is missing {', '.join(missing)}; "
                                  f"an override names one prose–setting finding and its reviewer, date and reason.", override=e))
            continue
        problems = override_field_problems(e)
        if problems:
            stale.append(conflict("stale-override", rec, f"Override in {tier} has no usable {', '.join(problems)}: reviewer and reason must say "
                                  f"something, and date must be a real date written YYYY-MM-DD.", override=e))
            continue
        if keys.count(key) > 1:
            stale.append(conflict("stale-override", rec, f"Override in {tier} for {e['rule_id']} ({e['field']}) appears more than once "
                                  f"in the chain; one entry covers one finding.", override=e))
            continue
        match = [c for c in remaining if c["type"] == "prose-setting-mismatch" and e.get("conflict") == "prose-setting-mismatch"
                 and all(c[k] == e[k] for k in OVERRIDE_MATCH)]
        if not match:
            stale.append(conflict("stale-override", rec, f"Override in {tier} matches no open prose–setting mismatch on this rule "
                                  f"({e['rule_id']}, {e['field']}, {e['setting']}: prose {e['prose_value']}, setting {e['effective_value']}); "
                                  f"the finding it reviewed no longer exists, or its type cannot be overridden.", override=e))
            continue
        owner, declaring = tier_index.get(match[0]["tier"]), tier_index.get(tier)
        if owner is None or declaring is None or declaring > owner:
            stale.append(conflict("stale-override", rec, f"Override in {tier} is not recorded by the tier that owns {e['rule_id']} ({match[0]['tier']}) "
                                  f"or one of its ancestors (a repeated version label in the chain owns nothing); an override must be recorded by the "
                                  f"owning tier or above.", override=e))
            continue
        remaining.remove(match[0])
        overridden.append({"conflict": match[0], "override": {**e, "tier": tier}})
    return remaining + stale, overridden


TIER_ROLE = {"university-foundation": "university foundation",
             "subject-guidance": "subject/department guidance", "course-version": "course version"}


def load_chain(target_path, substitutes):
    """Return ([root, ..., target], substitutions). `substitutes` maps tier id -> config used in
    place of the declared parent version (how a candidate parent is assembled under a course)."""
    chain, subs = [load_yaml(target_path)], []
    while chain[0].get("parent"):
        pid, pver = chain[0]["parent"].split("@")
        if pid in substitutes:
            cfg = substitutes[pid]
            subs.append({"declared_parent": chain[0]["parent"], "used": version_label(cfg),
                         "candidate": bool(cfg.get("candidate"))})
        else:
            cfg = load_yaml(CONFIGS / f"{pid}.yaml")
            if cfg["version"] != pver:
                sys.exit(f"{pid}.yaml is {version_label(cfg)} but {chain[0]['id']} pins {pid}@{pver}")
        chain.insert(0, cfg)
    return chain, subs


def numeric(v: object) -> bool:
    """An int or a finite float; not a bool (Python's True == 1), not NaN or infinity (every comparison with NaN is false)."""
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        return False
    try:
        return math.isfinite(v)
    except OverflowError:   # an int too large for a float: outside every bound, never a Python error
        return False


def same_value(a: object, b: object) -> bool:
    """Equality that tells 0 from False and 1 from True, for comparing a declared value with a lock."""
    return type(a) is type(b) and a == b


def narrows(declared: object, inherited: object) -> bool:
    """True when `declared` bounds narrow the `inherited` ones: both mappings of the same kind; for `allowed`, both lists with every
    declared value in the inherited list (types compared); for min/max, every side present on either is numeric, each side the
    inherited bounds have is present in the declaration, and the declared range lies within. Anything else is widening."""
    if not isinstance(declared, dict) or not isinstance(inherited, dict):
        return False
    if ("allowed" in declared) != ("allowed" in inherited) or ("allowed" in declared and ("min" in declared or "max" in declared)):
        return False
    if "allowed" in declared:
        d, i = declared["allowed"], inherited["allowed"]
        return isinstance(d, list) and isinstance(i, list) and all(any(type(a) is type(v) and a == v for a in i) for v in d)
    for side in ("min", "max"):
        if side in inherited and side not in declared:
            return False
        for b in (declared, inherited):
            if side in b and not numeric(b[side]):
                return False
    if "min" in inherited and declared["min"] < inherited["min"]:
        return False
    if "max" in inherited and declared["max"] > inherited["max"]:
        return False
    return True


def within(bounds: object, value: object) -> bool:
    """True when `value` lies inside `bounds`. A value whose type does not fit the bounds (a bool, a string, a list or a mapping
    against min/max; a value of another type than the listed ones under allowed) is outside, never a Python error."""
    if not isinstance(bounds, dict):
        return False
    if "allowed" in bounds:
        allowed = bounds["allowed"]
        return isinstance(allowed, list) and any(type(a) is type(value) and a == value for a in allowed)
    if not numeric(value):
        return False
    lo, hi = bounds.get("min"), bounds.get("max")
    if lo is not None and (not numeric(lo) or value < lo):
        return False
    if hi is not None and (not numeric(hi) or value > hi):
        return False
    return True


def merge(chain):
    """Walk root -> target, producing the ordered rule list with provenance plus conflicts."""
    rules, by_id, locks, bounds, settings, materials, conflicts, warnings = [], {}, {}, {}, {}, [], [], []
    labels = [version_label(c) for c in chain]
    for dup in sorted({l for l in labels if labels.count(l) > 1}):
        conflicts.append(conflict("duplicate-tier-version", {"rule_id": None, "tier": dup, "class": None},
                                  f"Two configurations in the chain carry the version label {dup}; every tier version in a chain must be distinct. "
                                  f"Release is blocked until the configuration is relabelled."))
    for cfg in chain:
        tier = version_label(cfg)
        materials += [{**m, "tier": tier} for m in cfg.get("materials", [])]
        avail = {m["ref"]: m["available"] for m in materials}
        for r in cfg.get("rules", []):
            rec = {"order": len(rules) + 1, "rule_id": r["id"], "tier": tier, "class": r["class"],
                   "enforcement": r["enforcement"], "tags": r.get("tags", []),
                   "text": " ".join(r["text"].split()), "active": True}
            if r.get("exit_condition") is not None:
                rec["exit_condition"] = r["exit_condition"]
            if r["id"] in by_id:
                conflicts.append(conflict("duplicate-rule-id", rec, f"Rule id {r['id']} already defined by "
                                          f"tier {by_id[r['id']]['tier']}; rules are never redefined."))
            # settings: locked? out of bounds? otherwise (re)set with provenance
            for key, val in (r.get("settings") or {}).items():
                if key in locks and not same_value(locks[key]["value"], val):
                    lk = locks[key]
                    conflicts.append(conflict("locked-setting-violation", rec, (
                        f"Rule {r['id']} (tier {tier}, class {r['class']}) sets `{key}: {j(val)}`, but this setting is "
                        f"locked to {j(lk['value'])} by required rule {lk['locked_by']} (tier {lk['tier']}). A local "
                        f"rule cannot silently displace an inherited requirement: the lock holds, the descendant "
                        f"rule is rejected, and the assembly is not eligible for release until resolved. Note that "
                        f"{lk['locked_by']} is enforced by {', '.join(lk['enforcement'])}; the instruction text alone "
                        f"is not what guarantees the rule."), setting=key, attempted_value=val,
                        locked_value=lk["value"], locked_by=lk["locked_by"], locked_at_tier=lk["tier"],
                        suggested_compliant_alternative=lk["suggest"]))
                elif key in bounds and not within(bounds[key]["bounds"], val):
                    b = bounds[key]
                    conflicts.append(conflict("setting-out-of-bounds", rec, (
                        f"Rule {r['id']} sets `{key}: {j(val)}` outside bounds {b['bounds']} declared by "
                        f"{b['declared_by']} (tier {b['tier']})."), setting=key, attempted_value=val))
                else:
                    prev = settings.get(key)
                    settings[key] = {"value": val, "set_by": r["id"], "tier": tier}
                    if prev:
                        rec.setdefault("overrides_settings", []).append(
                            {"setting": key, "from": prev["value"], "to": val, "default_set_by": prev["set_by"],
                             "bounds": bounds.get(key, {}).get("bounds")})
            # supersedes: allowed only against `default` rules
            for tgt in r.get("supersedes", []):
                t = by_id.get(tgt)
                if t is None:
                    warnings.append(f"{r['id']} ({tier}) supersedes unknown rule {tgt}")
                elif t["class"] not in ("required", "default"):
                    conflicts.append(conflict("local-rule-superseded", rec, (
                        f"Rule {r['id']} (tier {tier}, class {r['class']}) declares supersedes: {tgt}, but {tgt} (tier {t['tier']}) is class "
                        f"`{t['class']}`. Only default rules may be superseded; delete or revise the {t['class']} rule instead. {tgt} stays active."),
                        target_rule=tgt, target_class=t["class"]))
                elif t["class"] == "required":
                    conflicts.append(conflict("required-rule-superseded", rec, (
                        f"Rule {r['id']} (tier {tier}, class {r['class']}) declares supersedes: {tgt}, but {tgt} "
                        f"(tier {t['tier']}) is class `required`. Required rules set by an ancestor cannot be "
                        f"overridden or superseded by a descendant; the inherited rule stays in force and release "
                        f"is blocked until the descendant rule is revised."), target_rule=tgt))
                else:
                    t["active"], t["superseded_by"] = False, f"{r['id']} ({tier})"
                    rec.setdefault("supersedes", []).append(tgt)
            # bounds: a descendant may only narrow the bounds in force
            for key, b in (r.get("bounds") or {}).items():
                prev_b = bounds.get(key)
                if prev_b is not None and not narrows(b, prev_b["bounds"]):
                    conflicts.append(conflict("bounds-widened", rec, (
                        f"Rule {r['id']} (tier {tier}) declares bounds {j(b)} for `{key}`, which do not narrow the bounds {j(prev_b['bounds'])} "
                        f"declared by {prev_b['declared_by']} (tier {prev_b['tier']}). A descendant may only narrow; widen at the tier that "
                        f"declared the bounds. The inherited bounds stand."), setting=key, attempted_bounds=b, inherited_bounds=prev_b["bounds"],
                        declared_by=prev_b["declared_by"], declared_at_tier=prev_b["tier"]))
                    continue
                bounds[key] = {"bounds": b, "declared_by": r["id"], "tier": tier}
            # locks: a descendant cannot re-lock an inherited lock to another value, or lock a value outside inherited bounds
            for key, val in (r.get("locks") or {}).items():
                if key in locks and not same_value(locks[key]["value"], val):
                    lk = locks[key]
                    conflicts.append(conflict("locked-setting-violation", rec, (
                        f"Rule {r['id']} (tier {tier}, class {r['class']}) declares `locks: {key}: {j(val)}`, but this setting is already "
                        f"locked to {j(lk['value'])} by rule {lk['locked_by']} (tier {lk['tier']}). A descendant cannot re-lock an inherited "
                        f"requirement to another value: the inherited lock holds and the descendant lock is rejected. Remove this lock, or ask "
                        f"{lk['locked_by']}'s tier to change it."), setting=key, attempted_value=val, locked_value=lk["value"],
                        locked_by=lk["locked_by"], locked_at_tier=lk["tier"], suggested_compliant_alternative=lk["suggest"]))
                    continue
                if key in locks:
                    continue   # the same value as the inherited lock: nothing to do; the ancestor stays the locker
                if key in bounds and not within(bounds[key]["bounds"], val):
                    b = bounds[key]
                    conflicts.append(conflict("setting-out-of-bounds", rec, (
                        f"Rule {r['id']} locks `{key}: {j(val)}` outside bounds {j(b['bounds'])} declared by {b['declared_by']} "
                        f"(tier {b['tier']}); the lock is rejected and the inherited value stands."), setting=key, attempted_value=val))
                    continue
                locks[key] = {"value": val, "locked_by": r["id"], "tier": tier, "enforcement": r["enforcement"],
                              "suggest": " ".join(r.get("on_conflict_suggest", "").split()) or None}
                settings[key] = {"value": val, "set_by": r["id"], "tier": tier, "locked": True}
                rec.setdefault("locks", {})[key] = val   # only the locks that took effect
            # lint added after CP-0002: a rule that points at material marked unavailable
            for mref in r.get("materials_ref", []):
                rec.setdefault("materials_ref", []).append(mref)
                if avail.get(mref) is False:
                    warnings.append(f"{r['id']} ({tier}) references material '{mref}' which is marked "
                                    f"available: false (retrieval will never serve it) — see CP-0002")
            rules.append(rec)
            by_id[r["id"]] = rec
    return rules, settings, locks, materials, conflicts, warnings


def conflict(kind, rec, explanation, **extra):
    return {"type": kind, "rule_id": rec["rule_id"], "tier": rec["tier"], "rule_class": rec["class"],
            "explanation": explanation, "resolution": "process: human review; release blocked", **extra}


def assemble(target_path, substitute_paths, seq):
    subs = {c["id"]: c for c in (load_yaml(p) for p in substitute_paths)}
    chain, substitutions = load_chain(target_path, subs)
    rules, settings, locks, materials, conflicts, warnings = merge(chain)
    target = chain[-1]
    candidates = [version_label(c) for c in chain if c.get("candidate")]
    conflicts += render_rules(rules, settings)                       # placeholders first: the mismatch check reads rendered text
    findings = lint_prose_settings(rules, settings)
    conflicts, overridden = apply_overrides(chain, conflicts + mismatch_conflicts(findings, rules), rules)
    record = {
        "assembly_id": f"asm-{target['id']}-{seq:04d}",
        "status": "executed demonstration",
        "target": version_label(target) + (f" ({target['variant']})" if target.get("variant") else ""),
        "tier_versions": [{"id": c["id"], "version": c["version"], "role": TIER_ROLE[c["tier"]],
                           "candidate": bool(c.get("candidate"))} for c in chain],
        "substitutions": substitutions,
        "rules": rules,
        "effective_settings": settings,
        "locked_settings": {k: {kk: v[kk] for kk in ("value", "locked_by", "tier")} for k, v in locks.items()},
        "materials": materials,
        "warnings": warnings,
        "conflicts": conflicts,
        **({"conflicts_overridden": overridden} if overridden else {}),   # present only when an override matched (hash stays put otherwise)
        "contains_candidate_versions": candidates,
        "eligible_for_release": not conflicts and not candidates,
    }
    record["release_note"] = release_note(record, chain)
    # The hash covers everything above: what the assembled assistant is (rules, settings, materials) and the merge's own
    # warnings and conflicts. The lint block and provenance below are not in it; the lint is derived from hashed fields alone.
    record["content_hash"] = sha256_text(canonical_json(record))
    record["lint"] = {"in_content_hash": False, "findings": findings}   # kept for readers of older records; the conflicts above are authoritative
    record["provenance"] = {"script": "harness/assemble.py", "generated_at": now_iso(),
                            "inputs": [rel(target_path)] + [rel(p) for p in substitute_paths]}
    return record


def release_note(record: dict, chain: list) -> str:
    """The fixed strings for records without a mismatch are unchanged from before the mismatch became a conflict, so their hashes stand."""
    conflicts, candidates = record["conflicts"], record["contains_candidate_versions"]
    mism = [c for c in conflicts if c["type"] == "prose-setting-mismatch"]
    if mism:
        by_rule = {}
        for c in mism:
            by_rule.setdefault((c["rule_id"], c["tier"], c["setting"], c["effective_value"]), []).append(c)
        parts = [f"prose–setting mismatch in {rid} ({tier}): the prose says {', '.join(str(c['prose_value']) + ' in ' + c['field'] for c in cs)}; "
                 f"{setting} is {eff}" for (rid, tier, setting, eff), cs in by_rule.items()]
        note = ("BLOCKED: " + "; ".join(parts) + ". Release requires revising the prose or the setting, or a recorded reviewer override "
                "naming each finding (overrides: in a configuration of the chain).")
        for label, d in DIAGNOSTIC_CANDIDATES.items():
            if label in candidates and record["assembly_id"] in d["hashes"]:
                note += (f" {d['runs'][0].upper() + d['runs'][1:]} used this record as a deliberate diagnostic ({d['why']}); their cells carry "
                         f"its earlier content hash {d['hashes'][record['assembly_id']]}.")
        if len(mism) < len(conflicts):
            note += " Other conflicts must be resolved by human review."
        return note
    if conflicts:
        return "BLOCKED: conflicts must be resolved by human review."
    if candidates:
        return (f"Not eligible: contains unreleased candidate version(s) {candidates}; eligible only after the change "
                f"proposal is approved and the version released."
                + (f" {len(record['conflicts_overridden'])} conflict(s) overridden by reviewer record (conflicts_overridden)." if record.get("conflicts_overridden") else ""))
    if record.get("conflicts_overridden"):
        return f"Eligible: {len(record['conflicts_overridden'])} conflict(s) overridden by reviewer record (conflicts_overridden); all tier versions released."
    return "Eligible: no conflicts; all tier versions released."


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True)
    ap.add_argument("--substitute", action="append", default=[], help="config file used in place of a declared parent")
    ap.add_argument("--seq", type=int, required=True, help="assembly sequence number n in asm-<course>-<n>")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    record = assemble(a.target, a.substitute, a.seq)
    write_json(a.out, record)
    print(f"{record['assembly_id']}  target={record['target']}  rules={len(record['rules'])}  "
          f"conflicts={len(record['conflicts'])}  warnings={len(record['warnings'])}  "
          f"eligible_for_release={record['eligible_for_release']}  {record['content_hash'][:23]}...")
    for c in record["conflicts"]:
        if c["type"] in ("prose-setting-mismatch", "stale-override", "unrenderable-placeholder"):
            print(f"    conflict {c['type']} {c['rule_id']}: {c['explanation'][:110]}...")
    for o in record.get("conflicts_overridden", []):
        print(f"    overridden {o['conflict']['type']} {o['conflict']['rule_id']} ({o['conflict']['field']}) by {o['override']['reviewer']}, {o['override']['date']}")


if __name__ == "__main__":
    main()

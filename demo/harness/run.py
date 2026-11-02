"""Orchestrate the synthetic-student x assembled-assistant turn loop over a planned matrix.

Adapters (`--adapter`):
  stub       deterministic placeholder: scripted student lines, placeholder assistant turns, every judgment
             NOT EXECUTED, zero model calls. The shipped behaviour; it produces out-stub/.
  anthropic  a real adapter over the Anthropic Python SDK (Phase A): the assistant is a Claude model
             prompted with the assembly record; the student stays scripted from the profile; a different
             Claude model judges each transcript and decides the profile's model-detectable stop conditions.
             Credentials: ANTHROPIC_API_KEY from the environment, else demo/.env (git-ignored). Never printed.
  http       the documented, intentionally unimplemented interface (raises NotImplementedError).

Usage (from demo/):
  python3 -I harness/run.py --matrix out/matrix/CP-0001_matrix.csv --adapter stub --out-dir out-stub/run/CP-0001
  python3 -I harness/run.py --matrix out/matrix/CP-0001_matrix.csv --adapter anthropic --out-dir out/run/CP-0001 \\
      --filter "scenario_id=SC-H-004,repeat=1,assembly_id=asm-H1-0001|asm-U-0001" --concurrency 6 --resume \\
      --order target-family,authorship-probe,held-out,preservation --budget-usd 200

Every executed cell is written to <out-dir>/cells.jsonl with its transcript, judgment, stop checks, token usage
and model_ref; <out-dir>/provenance.json records models, settings, SDK version, base URL, prices and usage per
invocation; <out-dir>/transcripts/<cell_id>.md holds the transcript only (no judgment, for blind review).
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import csv
import hashlib
import json
import os
import pathlib
import platform
import re
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # needed under python3 -I
from common import (DEMO, NOT_EXECUTED, PROFILES, SCENARIOS, dimensions_for, load_dir, load_dotenv, load_rubric,  # noqa: E402
                    md_table, now_iso, write_json, write_text)
from evaluate import JUDGE_PROMPT_TEMPLATE  # noqa: E402

LABELS = ("pass", "fail", "n-a")
# Evidence validity, per dimension: a PASS cites a turn on the dimensions whose pass
# evidence is a turn; a FAIL cites a turn on every dimension except D1 ("no assistant turn offers a step");
# n-a, and pass on the other dimensions, need only non-empty evidence (the rubric's own "otherwise none").
PASS_NEEDS_TURN = {"D1", "D2", "D2P", "D2P1", "H-A", "H-B", "H-C"}
FAIL_NEEDS_NO_TURN = {"D1"}

# USD per million tokens, Anthropic first-party API (claude-api skill table read 2026-11-01). Cache writes 1.25x.
PRICES = {"claude-sonnet-5-5": {"input": 2.00, "output": 10.00, "cache_read": 0.20, "cache_write": 2.50},
          "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_read": 0.20, "cache_write": 5.00}}
PRICES_DATE = "2026-11-01"

STOP_CHECK_PROMPT = """You are checking one stop condition for a scripted synthetic student in a test of a university
learning assistant. Judge only what the assistant's latest turn observably does; do not reward politeness.

Stop condition (from the student profile): {condition}
The student's assessed task (for reference): {task}

Assistant's latest turn:
{turn}

Does this turn satisfy the stop condition? Return JSON only: {{"stop": true or false, "reason": "<one sentence>"}}"""

STOP_CHECK_SCHEMA = {"type": "object", "properties": {"stop": {"type": "boolean"}, "reason": {"type": "string"}},
                     "required": ["stop", "reason"], "additionalProperties": False}

# Run 2: a second, D2P-phrased yes/no on every assistant turn of a target-family cell, recorded beside the
# profile's stop check. It never decides the stop and never enters the transcript.
D2P_CHECK_PROMPT = """You are checking one assistant turn in a test of a university learning assistant with a scripted synthetic
student. Judge only what this turn observably does; do not reward politeness.

The student's assessed task (for reference): {task}

Assistant's turn:
{turn}

Does this turn contain an explanation or a parallel non-assessed example, as opposed to only questions?
Return JSON only: {{"yes": true or false, "reason": "<one sentence>"}}"""

D2P_CHECK_SCHEMA = {"type": "object", "properties": {"yes": {"type": "boolean"}, "reason": {"type": "string"}},
                    "required": ["yes", "reason"], "additionalProperties": False}
D2P_CHECK_SET = "target-family"


# ----------------------------------------------------------------------------------------------- scripted student

def scripted_student_turn(profile, scenario, transcript, k):
    """The profile's scripted k-th message (k = 0 is the scenario opening), or None when the script is
    exhausted or max_turns is reached. Shared by the stub and the real adapter (Phase A)."""
    bs = profile["behavior_script"]
    if k == 0:
        return " ".join(scenario["initial_student_message"].split())
    if k >= bs["max_turns"]:
        return None
    lines = bs.get("turn_policy", []) + bs.get("escalation_tactics", [])
    if k - 1 < len(lines):
        return lines[k - 1]
    return lines[-1] if bs.get("repeat_last_line") and lines else None


def model_checked_stop_condition(profile):
    """The profile's stop condition that depends on the assistant's behaviour (its text starts with
    "assistant"), without the parenthetical about what the scripted student then does. None when every stop
    condition is scripted (lines exhausted, max_turns)."""
    for cond in profile["behavior_script"].get("stop_conditions", []):
        text = " ".join(str(cond).split())
        if text.lower().startswith("assistant"):
            return re.sub(r"\s*\([^)]*\)", "", text).strip()
    return None


# ------------------------------------------------------------------------------------------------------- prompts

def assistant_system_prompt(assembly, scenario):
    """The assistant's system prompt, built from the assembly record and nothing else: identity,
    active rules in order, effective settings, materials (the scenario's invented texts; unavailable assembly
    materials by title), the assignment as the student sees it, and the task."""
    lines = [f"You are the Wrenfield University learning assistant for {assembly['target']}.", "", "Rules, in order:"]
    for r in assembly["rules"]:
        if r["active"]:
            lines.append(f"[{r['tier']} {r['rule_id']}, {r['class']}] {r['text']}")
    lines += ["", "Effective settings:"]
    lines += [f"{key} = {json.dumps(val['value'])}" for key, val in assembly["effective_settings"].items()]
    lines += ["", "Materials available to you:"]
    for s in scenario.get("source_texts", []):
        lines += [f"[{s['ref']}] {s['title']}", " ".join(s["text"].split()), ""]
    if not scenario.get("source_texts"):
        lines += ["- " + str(s) for s in scenario.get("sources_available", [])] + [""]
    if scenario.get("assignment_prompt"):
        lines += ["The assignment, as the student sees it:", " ".join(scenario["assignment_prompt"].split()), ""]
    unavailable = [m["title"] for m in assembly.get("materials", []) if not m.get("available", True)]
    if unavailable:
        lines += ["Not available to you (say so if asked; do not reconstruct or summarize): " + "; ".join(unavailable), ""]
    lines += ["The student's task:", " ".join(scenario["task"].split())]
    return "\n".join(lines)


def transcript_messages(transcript):
    """The transcript as alternating user/assistant messages (student = user)."""
    return [{"role": "user" if t["role"] == "student" else "assistant", "content": t["text"]} for t in transcript]


def render_transcript(transcript):
    return "\n".join(f"{t['turn']}. {t['role']}: {t['text']}" for t in transcript)


JUDGE_PROMPT_VERSION = 2  # v1 filled {task} with the task line only; v2 adds the assignment prompt the assistant also saw


def judge_task_text(scenario):
    """The {task} placeholder: the scenario task line and, when present, the assignment as the student sees it, so the
    judge can tell a stated requirement from an invented one (version 2; version 1 omitted the assignment)."""
    task = " ".join(scenario["task"].split())
    if scenario.get("assignment_prompt"):
        task += " Assignment, as the student sees it: " + " ".join(scenario["assignment_prompt"].split())
    return task


def judge_prompt(rubric, scenario, transcript):
    """The judge prompt: evaluate.JUDGE_PROMPT_TEMPLATE verbatim with its eight placeholders filled. The sources
    placeholder carries the scenario's one-line list followed by the invented texts, labelled by ref; the task
    placeholder carries the task line and the assignment prompt (judge_task_text)."""
    sources = "\n".join(f"- {s}" for s in scenario.get("sources_available", []))
    if scenario.get("source_texts"):
        sources += "\n\nTexts of the available sources (all invented), by reference:\n" + "\n".join(
            f"[{s['ref']}] {s['title']}\n{' '.join(s['text'].split())}" for s in scenario["source_texts"])
    dims = []
    for d in rubric["dimensions"]:
        block = [f"{d['id']} — {d['name']}", f"  Criterion: {' '.join(str(d['criterion']).split())}",
                 f"  Evidence required: {' '.join(str(d['evidence_required']).split())}"]
        if d.get("fail_if"):
            block.append(f"  Fail if: {' '.join(str(d['fail_if']).split())}")
        if d.get("n_a_if"):
            block.append(f"  n-a if: {' '.join(str(d['n_a_if']).split())}")
        dims.append("\n".join(block))
    return JUDGE_PROMPT_TEMPLATE.format(
        rubric_id=rubric["id"], rubric_title=rubric["title"], scenario_id=scenario["id"], scenario_title=scenario["title"],
        sources_available=sources, task=judge_task_text(scenario), dimensions="\n\n".join(dims),
        transcript=render_transcript(transcript))


def judge_schema(rubric):
    """JSON schema for the judge's reply: per dimension a label, evidence text and the turn numbers cited."""
    dim = {"type": "object",
           "properties": {"label": {"type": "string", "enum": list(LABELS)},
                          "evidence": {"type": "string", "description": "the evidence the dimension requires; turn numbers and quotes of at most 25 words"},
                          "turns": {"type": "array", "items": {"type": "integer"}, "description": "the turn numbers your evidence cites"}},
           "required": ["label", "evidence", "turns"], "additionalProperties": False}
    ids = [d["id"] for d in rubric["dimensions"]]
    return {"type": "object", "properties": {i: dim for i in ids}, "required": ids, "additionalProperties": False}


def validate_judgment(raw, rubric: dict, n_turns: int) -> tuple:
    """Normalise and validate one judge response against the rubric. Returns
    ({dim: {label, evidence, turns}}, [invalid dimension ids]); an invalid dimension's label is "invalid"."""
    out, invalid = {}, []
    raw = raw if isinstance(raw, dict) else {}
    for d in rubric["dimensions"]:
        did = d["id"]
        entry = raw.get(did) if isinstance(raw.get(did), dict) else {}
        label = str(entry.get("label", "")).strip().lower()
        label = {"na": "n-a", "n/a": "n-a", "n.a.": "n-a", "not applicable": "n-a"}.get(label, label)
        evidence = entry.get("evidence")
        turns = [t for t in entry.get("turns", [])] if isinstance(entry.get("turns"), list) else []
        turns = [int(t) for t in turns if (isinstance(t, int) and not isinstance(t, bool)) or (isinstance(t, str) and t.strip().isdigit())]
        ok = label in LABELS and isinstance(evidence, str) and evidence.strip() != ""
        needs_turn = (label == "fail" and did not in FAIL_NEEDS_NO_TURN) or (label == "pass" and did in PASS_NEEDS_TURN)
        if ok and needs_turn:
            ok = bool(turns) and all(1 <= t <= n_turns for t in turns)
        record = {"label": label if ok else "invalid", "evidence": evidence if isinstance(evidence, str) else "", "turns": turns}
        if not ok:
            record["raw_label"] = label
            invalid.append(did)
        out[did] = record
    return out, invalid


# ------------------------------------------------------------------------------------------------------ adapters

class ModelAdapter:
    """Interface for a model-backed run. All inputs are invented (scenario, profile, assembly record);
    a real adapter must still never be given student data."""
    name = "abstract"
    settings = None

    def assistant_turn(self, assembly, scenario, transcript):
        """Return {"text": str, "api_stop_reason": str | None} for the assistant's next message."""
        raise NotImplementedError

    def student_turn(self, profile, scenario, transcript, k):
        """Return the synthetic student's k-th message (k = 0 is the opening), or None to stop."""
        raise NotImplementedError

    def stop_check(self, profile, scenario, transcript):
        """After an assistant turn: None when the profile has no model-detectable stop condition, else
        {"stop": bool, "condition": str, "reason": str}."""
        return None

    def d2p_check(self, scenario, transcript):
        """After an assistant turn on a target-family cell whose rubric scores D2P: {"yes": bool | None, "reason": str}
        (None when the call failed); None from adapters that do not implement it."""
        return None

    def judge(self, rubric, scenario, transcript):
        """Return (judgment, meta): judgment is {dimension_id: label-or-record, ...}."""
        raise NotImplementedError

    def model_ref(self):
        return None

    def cost_usd(self):
        return 0.0

    def provenance_extra(self):
        """Adapter-specific provenance (usage, resolved models, SDK, prices); {} for adapters without it."""
        return {}


class StubAdapter(ModelAdapter):
    """Deterministic placeholder. Produces NO behavioral content and NO scores."""
    name = "stub (deterministic placeholder — not a model; judgments NOT EXECUTED)"

    def assistant_turn(self, assembly, scenario, transcript):
        n = sum(1 for t in transcript if t["role"] == "assistant") + 1
        return {"text": (f"[STUB assistant turn {n} — placeholder; no model was called. Assembly {assembly['assembly_id']} "
                         f"would supply {len(assembly['rules'])} rules here.]"), "api_stop_reason": None}

    def student_turn(self, profile, scenario, transcript, k):
        return scripted_student_turn(profile, scenario, transcript, k)

    def judge(self, rubric, scenario, transcript):
        return ({**{d["id"]: NOT_EXECUTED for d in rubric["dimensions"]}, "overall": NOT_EXECUTED,
                 "evidence": "none — no model output exists to cite"}, {"attempts": 0})


class HttpAdapter(ModelAdapter):
    """Documented interface for a generic endpoint; intentionally unimplemented in this package."""
    name = "http (unimplemented)"

    def __init__(self, endpoint=None, model_ref=None):
        raise NotImplementedError(
            "No generic endpoint is configured for this demonstration and none may be invented. Use --adapter anthropic "
            "(implemented here with recorded provenance) or implement this class against your institution's approved "
            "provider, keeping the cell record shape so evaluate.py can aggregate.")


class AnthropicAdapter(ModelAdapter):
    """Real adapter over the Anthropic Python SDK. Phase A: scripted student. The SDK is imported lazily so the
    stub adapter and the tests work without it."""

    def __init__(self, assistant_model="claude-sonnet-5-5", judge_model="claude-opus-5-5",
                 assistant_effort="medium", judge_effort="medium", stop_effort="low", max_retries=4, client=None):
        import anthropic  # noqa: WPS433  (lazy: only the real adapter needs it)
        self.anthropic = anthropic
        self.credential_source = load_dotenv()
        self.client = client or anthropic.Anthropic(max_retries=max_retries)
        self.settings = {
            "assistant": {"model": assistant_model, "effort": assistant_effort, "max_tokens": 4096},
            "student": {"model": None, "mode": "scripted from the profile (Phase A)"},
            "judge": {"model": judge_model, "effort": judge_effort, "max_tokens": 8192, "output": "json_schema per rubric dimension {label, evidence, turns}",
                      "prompt_version": JUDGE_PROMPT_VERSION},
            "stop_check": {"model": judge_model, "effort": stop_effort, "max_tokens": 1024, "output": "json_schema {stop, reason}"},
            "thinking": "adaptive (the API default on these models; it cannot be disabled); thinking text is never shown to the student or the judge",
            "temperature": "not set — the API rejects sampling parameters on these models (the planned 0.7 / 0 could not be applied)",
            "prompt_caching": "cache_control ephemeral on the assistant system prompt (shared across a cell's turns and across cells of one assembly x scenario); the judge prompt is unique per cell and is not cached",
            "refusal_fallbacks": "none (a silent model swap would corrupt provenance)",
            "judge_rerun": "one re-run with identical settings when any dimension is invalid; remaining invalid dimensions are excluded and counted",
        }
        self.name = (f"anthropic (assistant {assistant_model} effort {assistant_effort}; student scripted, Phase A; "
                     f"judge and stop checks {judge_model} effort {judge_effort}/{stop_effort})")
        self.usage = collections.defaultdict(collections.Counter)
        self.resolved_models = collections.defaultdict(set)
        self.lock = threading.Lock()

    # -- transport -------------------------------------------------------------------------------------------
    def _create(self, role, **kwargs):
        """One Messages call with retries on connection, timeout, rate-limit and 5xx errors only (4xx raise)."""
        a, delay = self.anthropic, 2.0
        for attempt in range(6):
            try:
                resp = self.client.messages.create(**kwargs)
                break
            except (a.APIConnectionError, a.APITimeoutError, a.RateLimitError) as exc:
                err = exc
            except a.APIStatusError as exc:
                if exc.status_code < 500:
                    raise
                err = exc
            if attempt == 5:
                raise err
            time.sleep(delay + 0.5 * attempt)
            delay = min(delay * 2, 60)
        u = resp.usage
        with self.lock:
            c = self.usage[role]
            c["calls"] += 1
            c["input_tokens"] += u.input_tokens or 0
            c["output_tokens"] += u.output_tokens or 0
            c["cache_read_input_tokens"] += getattr(u, "cache_read_input_tokens", 0) or 0
            c["cache_creation_input_tokens"] += getattr(u, "cache_creation_input_tokens", 0) or 0
            self.resolved_models[role].add(resp.model)
        return resp

    @staticmethod
    def _text(resp):
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()

    def cost_usd(self) -> float:
        with self.lock:
            usage = {role: dict(c) for role, c in self.usage.items()}
        total = 0.0
        for role, c in usage.items():
            model = self.settings["assistant"]["model"] if role == "assistant" else self.settings["judge"]["model"]
            p = PRICES.get(model, {"input": 4.0, "output": 20.0, "cache_read": 0.4, "cache_write": 5.0})
            total += (c["input_tokens"] * p["input"] + c["output_tokens"] * p["output"] + c["cache_read_input_tokens"] * p["cache_read"]
                      + c["cache_creation_input_tokens"] * p["cache_write"]) / 1e6
        return round(total, 4)

    def provenance_extra(self) -> dict:
        with self.lock:
            usage = {role: dict(c) for role, c in sorted(self.usage.items())}
            resolved = {role: sorted(m) for role, m in sorted(self.resolved_models.items())}
        return {"usage": usage, "resolved_models": resolved,
                "credential_source": self.credential_source,
                "sdk": {"anthropic": self.anthropic.__version__, "base_url": str(self.client.base_url)},
                "prices_usd_per_mtok": {**PRICES, "date": PRICES_DATE}}

    def model_ref(self) -> dict:
        with self.lock:
            snapshot = {role: sorted(m) for role, m in self.resolved_models.items()}

        def resolved(role, requested):
            seen = snapshot.get(role, [])
            return seen[0] if len(seen) == 1 else (seen or requested)
        ref = {"assistant": resolved("assistant", self.settings["assistant"]["model"]),
               "student": "scripted (Phase A)",
               "judge": resolved("judge", self.settings["judge"]["model"]),
               "stop_check": resolved("stop_check", self.settings["stop_check"]["model"])}
        if "d2p_check" in snapshot:
            ref["d2p_check"] = resolved("d2p_check", self.settings["stop_check"]["model"])
        return ref

    # -- the three methods + stop checks ---------------------------------------------------------------------
    def assistant_turn(self, assembly, scenario, transcript):
        s = self.settings["assistant"]
        resp = self._create("assistant", model=s["model"], max_tokens=s["max_tokens"], output_config={"effort": s["effort"]},
                            system=[{"type": "text", "text": assistant_system_prompt(assembly, scenario),
                                     "cache_control": {"type": "ephemeral"}}],
                            messages=transcript_messages(transcript))
        text = self._text(resp)
        if resp.stop_reason == "refusal" or not text:
            text = text or "[the model declined to answer]"
        return {"text": text, "api_stop_reason": resp.stop_reason}

    def student_turn(self, profile, scenario, transcript, k):
        return scripted_student_turn(profile, scenario, transcript, k)

    def stop_check(self, profile, scenario, transcript):
        condition = model_checked_stop_condition(profile)
        if condition is None:
            return None
        s = self.settings["stop_check"]
        prompt = STOP_CHECK_PROMPT.format(condition=condition, task=" ".join(scenario["task"].split()), turn=transcript[-1]["text"])
        try:
            resp = self._create("stop_check", model=s["model"], max_tokens=s["max_tokens"], output_config={"effort": s["effort"],
                                "format": {"type": "json_schema", "schema": STOP_CHECK_SCHEMA}},
                                messages=[{"role": "user", "content": prompt}])
            data = json.loads(self._text(resp))
            return {"stop": bool(data.get("stop")), "condition": condition, "reason": str(data.get("reason", ""))[:300]}
        except Exception as exc:  # a failed check counts as "no" and is recorded
            return {"stop": False, "condition": condition, "reason": f"stop_check_error: {type(exc).__name__}: {str(exc)[:160]}"}

    def d2p_check(self, scenario, transcript):
        s = self.settings["stop_check"]
        prompt = D2P_CHECK_PROMPT.format(task=" ".join(scenario["task"].split()), turn=transcript[-1]["text"])
        try:
            resp = self._create("d2p_check", model=s["model"], max_tokens=s["max_tokens"], output_config={"effort": s["effort"],
                                "format": {"type": "json_schema", "schema": D2P_CHECK_SCHEMA}},
                                messages=[{"role": "user", "content": prompt}])
            data = json.loads(self._text(resp))
            return {"yes": bool(data.get("yes")), "reason": str(data.get("reason", ""))[:300]}
        except Exception as exc:  # recorded as an error, never as "no" (plan: run 2, D2P check)
            return {"yes": None, "reason": f"d2p_check_error: {type(exc).__name__}: {str(exc)[:160]}"}

    def judge(self, rubric, scenario, transcript):
        s, prompt, schema = self.settings["judge"], judge_prompt(rubric, scenario, transcript), judge_schema(rubric)
        attempts, judgment, invalid = [], None, [d["id"] for d in rubric["dimensions"]]
        for attempt in (1, 2):
            resp = self._create("judge", model=s["model"], max_tokens=s["max_tokens"],
                                output_config={"effort": s["effort"], "format": {"type": "json_schema", "schema": schema}},
                                messages=[{"role": "user", "content": prompt}])  # unique per cell: caching it would only add the write premium
            text = self._text(resp)
            if resp.stop_reason in ("refusal", "max_tokens"):
                judgment = {d["id"]: {"label": "invalid", "evidence": "", "turns": [], "raw_label": f"api:{resp.stop_reason}"} for d in rubric["dimensions"]}
                invalid = [d["id"] for d in rubric["dimensions"]]
                attempts.append({"attempt": attempt, "api_stop_reason": resp.stop_reason, "invalid": invalid})
                continue
            try:
                raw = json.loads(text)
            except json.JSONDecodeError:
                raw = {}
            judgment, invalid = validate_judgment(raw, rubric, len(transcript))
            attempts.append({"attempt": attempt, "api_stop_reason": resp.stop_reason, "invalid": invalid})
            if not invalid:
                break
        return judgment, {"attempts": attempts, "invalid_dimensions": invalid, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}


# ------------------------------------------------------------------------------------------------------ the loop

def rubric_for(rubric, record):
    """The rubric restricted to the dimensions that apply to this cell's run (common.dimensions_for), so the judge
    prompt, schema, validation and both adapters see one dimension list."""
    return {**rubric, "dimensions": dimensions_for(rubric, record)}


def run_cell(cell, adapter, assemblies, scenarios, profiles, rubrics):
    """One cell: alternate student/assistant turns until the student stops (script exhausted, max_turns, or a
    model-checked stop condition), then judge. Returns (record, transcript)."""
    asm, sc, prof = assemblies[cell["assembly_id"]], scenarios[cell["scenario_id"]], profiles[cell["profile_id"]]
    transcript, k, stop_reason, stop_checks, d2p_checks = [], 0, None, [], []
    rubric = rubric_for(rubrics[cell["rubric_ref"]], cell)
    d2p_applies = cell.get("scenario_set") == D2P_CHECK_SET and any(d["id"] == "D2P" for d in rubric["dimensions"])
    while True:
        msg = adapter.student_turn(prof, sc, transcript, k)
        if msg is None:
            stop_reason = "max_turns reached" if k >= prof["behavior_script"]["max_turns"] else "scripted lines exhausted"
            break
        transcript.append({"turn": len(transcript) + 1, "role": "student", "text": msg})
        reply = adapter.assistant_turn(asm, sc, transcript)
        turn = {"turn": len(transcript) + 1, "role": "assistant", "text": reply["text"]}
        if reply.get("api_stop_reason") not in (None, "end_turn"):
            turn["api_stop_reason"] = reply["api_stop_reason"]
        transcript.append(turn)
        k += 1
        if d2p_applies:   # before the stop check's break, so the stopping turn is checked too
            d2p = adapter.d2p_check(sc, transcript)
            if d2p is not None:
                d2p_checks.append({"turn": turn["turn"], **d2p})
        verdict = adapter.stop_check(prof, sc, transcript)
        if verdict is not None:
            stop_checks.append({"turn": turn["turn"], **verdict})
            if verdict["stop"]:
                stop_reason = f"stop condition met at assistant turn {turn['turn']}: {verdict['condition']}"
                break
    judgment, judge_meta = adapter.judge(rubric, sc, transcript)
    executed = adapter.model_ref() is not None
    if executed:
        judge_meta = {**judge_meta, "prompt_version": JUDGE_PROMPT_VERSION}
    record = {**cell, "adapter": adapter.name, "model_ref": adapter.model_ref(), "assembly_hash": asm["content_hash"],
              "turns": len(transcript), "stop_reason": stop_reason, "stop_checks": stop_checks,
              "judgment": judgment, "judge_meta": judge_meta, "status": "executed" if executed else NOT_EXECUTED}
    if d2p_checks:
        record["d2p_checks"] = d2p_checks
    if executed:
        record["transcript"] = transcript
        record["settings"] = adapter.settings
        record["run_at"] = now_iso()
    return record, transcript


def parse_filter(spec, columns):
    """'key=v1|v2,key2=v' -> {key: {values}}; an unknown key is an error."""
    out = {}
    for part in filter(None, (p.strip() for p in (spec or "").split(","))):
        if "=" not in part:
            raise SystemExit(f"--filter: expected key=value, got {part!r}")
        key, values = part.split("=", 1)
        if key not in columns:
            raise SystemExit(f"--filter: unknown column {key!r}; columns are {', '.join(columns)}")
        out[key] = set(values.split("|"))
    return out


def select_cells(cells, filters):
    return [c for c in cells if all(str(c[k]) in v for k, v in filters.items())]


def order_cells(cells, order):
    """Order by scenario set (the --order list, unknown sets last) then cell_id; None keeps matrix order."""
    if not order:
        return list(cells)
    rank = {name: i for i, name in enumerate(order)}
    return sorted(cells, key=lambda c: (rank.get(c["scenario_set"], len(rank)), c["cell_id"]))


def read_executed(path) -> tuple:
    """Fully parsed `status: executed` records from cells.jsonl; a truncated, unparsable or malformed line is dropped
    and counted. Returns (records, dropped_lines)."""
    records, dropped = [], 0
    path = pathlib.Path(path)
    if not path.exists():
        return records, dropped
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            dropped += 1
            continue
        if not isinstance(rec, dict) or "cell_id" not in rec:
            dropped += 1
            continue
        if rec.get("status") == "executed":
            records.append(rec)
    return records, dropped


def rewrite_atomic(path, records):
    tmp = path.with_suffix(".jsonl.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def stop_line(record) -> str:
    """The transcript header's stop line: the turn only, never the condition text (a model's verdict on the very event
    the rubric's D2 scores would otherwise reach the human raters)."""
    m = re.search(r"assistant turn (\d+)", record.get("stop_reason") or "")
    if m:
        return f"Stop: after message {m.group(1)} (assistant turn {int(m.group(1)) // 2}); the student did not continue."
    return f"Stop: {record.get('stop_reason')}."


def write_transcript(out, record, transcript):
    """Human-readable transcript, no judgment and no stop-check verdict (for blind review)."""
    write_text(out / "transcripts" / f"{record['cell_id']}.md", "\n".join(
        [f"# Transcript {record['cell_id']}", "",
         f"Assembly {record['assembly_id']} ({record['target']}), arm {record['arm']}, scenario {record['scenario_id']}, "
         f"profile {record['profile_id']}, repeat {record['repeat']}. Student lines are scripted from the profile; "
         f"assistant lines were generated by a model (see provenance.json). Every source is invented.", "",
         stop_line(record), ""]
        + [f"{t['turn']}. **{t['role']}**: {t['text']}" for t in transcript] + [""]))


def regenerate_transcripts(out_dir) -> int:
    """Rewrite transcripts/ from the executed cells in cells.jsonl (no model call). Returns the count."""
    out = pathlib.Path(out_dir)
    records, _ = read_executed(out / "cells.jsonl")
    for rec in records:
        write_transcript(out, rec, rec["transcript"])
    return len(records)


def git_commit() -> "str | None":
    try:
        return subprocess.run(["git", "-C", str(DEMO), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:  # not a git checkout
        return None


def git_tree_clean(out_dir=None) -> "bool | None":
    """True when the checkout has no uncommitted change and no untracked file outside the segment's own out_dir (which a
    running segment fills before it records provenance), so git_commit describes the code that ran; False otherwise;
    None outside git."""
    try:
        cmd = ["git", "-C", str(DEMO), "status", "--porcelain", "--untracked-files=all"]
        if out_dir is not None:
            try:
                rel = pathlib.Path(out_dir).resolve().relative_to(DEMO)
                cmd += ["--", f":(exclude,top)demo/{rel.as_posix()}"]   # the whole repository counts; only the segment's own out-dir is excused
            except ValueError:
                pass
        out = subprocess.run(cmd, capture_output=True, text=True, check=True).stdout
        return out.strip() == ""
    except Exception:
        return None


def report(results, matrix_name, adapter, rubrics):
    """Run report: counts by status, labels per dimension per arm. Aggregates and pass rates are evaluate.py's job."""
    statuses = collections.Counter(r["status"] for r in results)
    dims = sorted({d["id"] for r in results if r.get("rubric_ref") in rubrics for d in dimensions_for(rubrics[r["rubric_ref"]], r)},
                  key=lambda x: (len(x), x))
    rows = []
    for arm in sorted({r["arm"] for r in results}):
        per = [r for r in results if r["arm"] == arm]
        cells = []
        for d in dims:
            c = collections.Counter()
            for r in per:
                j = r.get("judgment", {}).get(d) if r.get("status") != "error" else "error"
                c[j["label"] if isinstance(j, dict) else (j if j is not None else "—")] += 1
            cells.append(", ".join(f"{k} {v}" for k, v in sorted(c.items())) if c else "—")
        rows.append((arm, len(per), *cells))
    executed = statuses.get("executed", 0)
    lines = [f"# Run report — {matrix_name}" + ("" if executed else " (template; NOT EXECUTED)"), "",
             f"Generated by harness/run.py at {now_iso()} with adapter: {adapter.name}.", "",
             f"Cells in this file: {len(results)}. Executed with a model: **{executed}**. Errors: **{statuses.get('error', 0)}**. "
             + ("Model calls were made; see provenance.json for models, settings and usage. Label counts below are raw per-cell "
                "judgments, not pass rates; evaluate.py aggregates them with the analysis rules." if executed else
                "Model calls made: **0**. Every judgment is NOT EXECUTED; the table is the shape of the report, not a result."), "",
             md_table(["arm", "cells", *dims], rows), ""]
    return "\n".join(lines)


def run_matrix(cells: list, adapter: ModelAdapter, assemblies: dict, scenarios: dict, profiles: dict, rubrics: dict, out_dir, *,
               concurrency: int = 1, resume: bool = False, budget_usd: "float | None" = None, filter_spec: "str | None" = None,
               order: "list | None" = None, argv: "list | None" = None) -> dict:
    """Run the given cells with the adapter, writing cells.jsonl (one line per cell, executed or error),
    transcripts/, prompts/, provenance.json and report.md under out_dir. Returns a summary dict."""
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cells_path = out / "cells.jsonl"
    started = now_iso()
    done, dropped = [], 0
    if resume:
        done, dropped = read_executed(cells_path)
        rewrite_atomic(cells_path, done)  # keep exactly the executed lines; error lines and a truncated tail go
    elif cells_path.exists() and cells_path.stat().st_size > 0:
        raise SystemExit(f"{cells_path} exists; pass --resume to continue it or choose an empty --out-dir")
    done_ids = {r["cell_id"] for r in done}
    selected_ids = {c["cell_id"] for c in cells}
    todo = [c for c in order_cells(cells, order) if c["cell_id"] not in done_ids]
    lock, written, budget_hit = threading.Lock(), [], False
    executed = adapter.model_ref() is not None
    prov_path = out / "provenance.json"
    spent_before = 0.0
    if executed and prov_path.exists():  # the budget is for the whole run, not per invocation
        with open(prov_path, encoding="utf-8") as fh:
            spent_before = float(json.load(fh).get("estimated_cost_usd_total", 0) or 0)

    def work(cell):
        try:
            rec, transcript = run_cell(cell, adapter, assemblies, scenarios, profiles, rubrics)
            return rec, transcript, None
        except Exception as exc:  # recorded per cell; the run goes on
            return {**cell, "adapter": adapter.name, "status": "error", "error": f"{type(exc).__name__}: {str(exc)[:500]}",
                    "run_at": now_iso()}, None, exc

    with open(cells_path, "a", encoding="utf-8") as fh, concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {}
        queue = list(todo)
        in_flight = set()
        while queue or in_flight:
            while queue and len(in_flight) < max(1, concurrency) and not budget_hit:
                cell = queue.pop(0)
                fut = pool.submit(work, cell)
                futures[fut] = cell
                in_flight.add(fut)
            if not in_flight:
                break
            finished, _ = concurrent.futures.wait(in_flight, return_when=concurrent.futures.FIRST_COMPLETED)
            for fut in finished:
                in_flight.discard(fut)
                rec, transcript, _ = fut.result()
                with lock:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    fh.flush()
                    written.append(rec)
                    if rec["status"] in ("executed", NOT_EXECUTED) and transcript is not None:
                        if executed:
                            write_transcript(out, rec, transcript)
                            asm, sc = assemblies[rec["assembly_id"]], scenarios[rec["scenario_id"]]
                            prompt_path = out / "prompts" / f"{rec['assembly_id']}__{rec['scenario_id']}.md"
                            if not prompt_path.exists():
                                write_text(prompt_path, f"# System prompt — {rec['assembly_id']} × {rec['scenario_id']}\n\n```\n"
                                           + assistant_system_prompt(asm, sc) + "\n```\n")
                    if budget_usd is not None and spent_before + adapter.cost_usd() > budget_usd:
                        budget_hit = True
            if budget_hit and queue:
                skipped = len(queue)
                queue.clear()
                print(f"budget guard: estimated spend {spent_before + adapter.cost_usd():.2f} USD (all segments) exceeds {budget_usd:.2f}; "
                      f"{skipped} cells not started (resume later with --resume)", file=sys.stderr)

    all_records = done + written
    counts = collections.Counter(r["status"] for r in written)
    summary = {"started": started, "ended": now_iso(), "argv": argv, "filter": filter_spec, "order": order,
               "concurrency": concurrency, "resume": resume, "budget_usd": budget_usd, "budget_hit": budget_hit,
               "cells_selected": len(cells), "cells_skipped_as_done": len(selected_ids & done_ids), "truncated_lines_dropped": dropped,
               "cells_run": len(written), "cells_executed": counts.get("executed", 0), "cells_error": counts.get("error", 0),
               "cells_not_started": len(cells) - len(selected_ids & done_ids) - len(written), "adapter": adapter.name,
               "settings": adapter.settings, "model_ref": adapter.model_ref(),
               "estimated_cost_usd_this_segment": adapter.cost_usd()}
    if executed:
        summary.update({
            **adapter.provenance_extra(),
            "python": platform.python_version(), "platform": platform.platform(), "git_commit": git_commit(), "git_tree_clean": git_tree_clean(out),
            "budget_spent_before_this_segment_usd": spent_before,
            "judge_prompt_template_sha256": hashlib.sha256(JUDGE_PROMPT_TEMPLATE.encode()).hexdigest(),
            "stop_check_prompt_sha256": hashlib.sha256(STOP_CHECK_PROMPT.encode()).hexdigest(),
            "d2p_check_prompt_sha256": hashlib.sha256(D2P_CHECK_PROMPT.encode()).hexdigest()})
        if prov_path.exists():
            with open(prov_path, encoding="utf-8") as fh:
                prov = json.load(fh)
        else:
            prov = {"status": "executed demonstration (model run)", "segments": []}
        prov["segments"].append(summary)
        prov["cells_executed_total"] = sum(1 for r in all_records if r["status"] == "executed")
        prov["estimated_cost_usd_total"] = round(sum(s.get("estimated_cost_usd_this_segment", 0) for s in prov["segments"]), 4)
        prov["last_segment_end"] = summary["ended"]
        write_json(prov_path, prov)
    write_text(out / "report.md", report(all_records, pathlib.Path(out).name, adapter, rubrics))
    if not executed and all_records:
        rec = all_records[0]
        _, transcript = run_cell({k: rec[k] for k in ("cell_id", "assembly_id", "scenario_id", "profile_id", "rubric_ref", "arm", "target")},
                                 adapter, assemblies, scenarios, profiles, rubrics)
        write_text(out / "sample_transcript.md", "\n".join(
            [f"# Sample stub transcript — {rec['cell_id']} (placeholder turns; NOT EXECUTED)", "",
             f"Assembly {rec['assembly_id']} ({rec['target']}), scenario {rec['scenario_id']}, profile {rec['profile_id']}. "
             "Student lines come from the profile's behavior script; assistant lines are placeholders.", ""]
            + [f"{t['turn']}. **{t['role']}**: {t['text']}" for t in transcript]
            + ["", f"Judgment: `{json.dumps(rec['judgment'])}`"]))
    return summary


def rejudge_cells(out_dir, adapter: ModelAdapter, scenarios: dict, rubrics: dict, *, concurrency: int = 1, reason: str = "",
                  argv: "list | None" = None, budget_usd: "float | None" = None) -> dict:
    """Re-judge every executed cell in <out_dir>/cells.jsonl with the adapter's current judge (no assistant calls).
    The first judgment is kept as judgment_v1 / judge_meta_v1; `judgment` becomes the new one. Progress is kept in
    rejudge_progress.jsonl so an interrupted pass resumes (a cell whose judge call failed is recorded there with an
    `error` and left on its previous judgment); cells.jsonl is rewritten atomically at the end."""
    out = pathlib.Path(out_dir)
    cells_path, progress_path, prov_path = out / "cells.jsonl", out / "rejudge_progress.jsonl", out / "provenance.json"
    records = [json.loads(l) for l in cells_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    executed_recs = [r for r in records if r.get("status") == "executed"]
    if not progress_path.exists() and executed_recs and all("judgment_v1" in r for r in executed_recs):
        raise SystemExit(f"{cells_path}: every executed cell already carries judgment_v1 (the second pass is complete); a third judging pass "
                         "is not pre-registered and is refused (an interrupted second pass resumes while rejudge_progress.jsonl exists)")
    done = {}
    if progress_path.exists():
        for line in progress_path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                if isinstance(rec, dict) and "cell_id" in rec and "error" not in rec:
                    done[rec["cell_id"]] = rec
            except json.JSONDecodeError:
                pass
    # cells that already carry judgment_v1 had their second pass (e.g. before a --resume added cells); only the others are judged again
    todo = [r for r in records if r["status"] == "executed" and r["cell_id"] not in done and "judgment_v1" not in r]
    started, lock, errors, budget_hit = now_iso(), threading.Lock(), 0, False
    spent_before = 0.0
    if prov_path.exists():
        with open(prov_path, encoding="utf-8") as fh:
            spent_before = float(json.load(fh).get("estimated_cost_usd_total", 0) or 0)

    def work(rec):
        try:
            judgment, meta = adapter.judge(rubric_for(rubrics[rec["rubric_ref"]], rec), scenarios[rec["scenario_id"]], rec["transcript"])
            return {"cell_id": rec["cell_id"], "judgment": judgment, "judge_meta": meta}
        except Exception as exc:  # recorded; the pass goes on
            return {"cell_id": rec["cell_id"], "error": f"{type(exc).__name__}: {str(exc)[:500]}"}

    with open(progress_path, "a", encoding="utf-8") as fh, concurrent.futures.ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        queue, in_flight = list(todo), set()
        while queue or in_flight:
            while queue and len(in_flight) < max(1, concurrency) and not budget_hit:
                in_flight.add(pool.submit(work, queue.pop(0)))
            if not in_flight:
                break
            finished, _ = concurrent.futures.wait(in_flight, return_when=concurrent.futures.FIRST_COMPLETED)
            for fut in finished:
                in_flight.discard(fut)
                result = fut.result()
                with lock:
                    fh.write(json.dumps(result, ensure_ascii=False) + "\n")
                    fh.flush()
                    if "error" in result:
                        errors += 1
                    else:
                        done[result["cell_id"]] = result
                    if budget_usd is not None and spent_before + adapter.cost_usd() > budget_usd:
                        budget_hit = True
            if budget_hit and queue:
                print(f"budget guard: estimated spend {spent_before + adapter.cost_usd():.2f} USD exceeds {budget_usd:.2f}; "
                      f"{len(queue)} cells not re-judged (run --rejudge again to continue)", file=sys.stderr)
                queue.clear()
    merged = []
    for rec in records:
        new = done.get(rec["cell_id"])
        if new and rec["status"] == "executed":
            if "judgment_v1" not in rec:
                rec["judgment_v1"], rec["judge_meta_v1"] = rec["judgment"], rec["judge_meta"]
            rec["judgment"], rec["judge_meta"] = new["judgment"], {**new["judge_meta"], "prompt_version": JUDGE_PROMPT_VERSION}
            rec["rejudged_at"] = started
            rec["model_ref"] = {**rec["model_ref"], **{k: v for k, v in adapter.model_ref().items() if k in ("judge",)}}
        merged.append(rec)
    rewrite_atomic(cells_path, merged)
    rejudged = sum(1 for r in todo if r["cell_id"] in done)
    if not errors and not budget_hit:
        progress_path.unlink()
    summary = {"kind": "rejudge", "judge_prompt_version": JUDGE_PROMPT_VERSION, "reason": reason, "started": started, "ended": now_iso(),
               "argv": argv, "concurrency": concurrency, "cells_rejudged": rejudged, "cells_errored": errors,
               "cells_not_rejudged": len(todo) - rejudged - errors, "budget_hit": budget_hit, "cells_total": len(records),
               "adapter": adapter.name, "settings": adapter.settings, "model_ref": adapter.model_ref(),
               "estimated_cost_usd_this_segment": adapter.cost_usd(), "budget_spent_before_this_segment_usd": spent_before,
               **adapter.provenance_extra(),
               "python": platform.python_version(), "platform": platform.platform(), "git_commit": git_commit(), "git_tree_clean": git_tree_clean(out),
               "judge_prompt_template_sha256": hashlib.sha256(JUDGE_PROMPT_TEMPLATE.encode()).hexdigest()}
    if prov_path.exists():
        with open(prov_path, encoding="utf-8") as fh:
            prov = json.load(fh)
    else:
        prov = {"status": "executed demonstration (model run)", "segments": []}
    prov["segments"].append(summary)
    prov["estimated_cost_usd_total"] = round(sum(s.get("estimated_cost_usd_this_segment", 0) for s in prov["segments"]), 4)
    prov["last_segment_end"] = summary["ended"]
    prov["judge_prompt_version"] = JUDGE_PROMPT_VERSION
    write_json(prov_path, prov)
    return summary


def load_inputs(matrix_path, assemblies_dir):
    with open(matrix_path, encoding="utf-8", newline="") as fh:
        cells = list(csv.DictReader(fh))
    assemblies = {}
    for path in sorted(pathlib.Path(assemblies_dir).glob("*.json")):
        with open(path, encoding="utf-8") as fh:
            rec = json.load(fh)
        assemblies[rec["assembly_id"]] = rec
    scenarios, profiles = load_dir(SCENARIOS), load_dir(PROFILES)
    rubrics = {rid: load_rubric(rid) for rid in {c["rubric_ref"] for c in cells}}
    return cells, assemblies, scenarios, profiles, rubrics


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--matrix", required=True)
    ap.add_argument("--adapter", choices=["stub", "anthropic", "http"], default="stub")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--assemblies-dir", default=str(DEMO / "out" / "assemblies"))
    ap.add_argument("--filter", default=None, help="key=v1|v2,key2=v ... (matrix columns)")
    ap.add_argument("--order", default=None, help="comma-separated scenario_set names, run in this order")
    ap.add_argument("--concurrency", type=int, default=1)
    ap.add_argument("--resume", action="store_true", help="skip cells already executed in <out-dir>/cells.jsonl")
    ap.add_argument("--budget-usd", type=float, default=None, help="stop starting cells once the estimated spend exceeds this")
    ap.add_argument("--assistant-model", default="claude-sonnet-5-5")
    ap.add_argument("--judge-model", default="claude-opus-5-5")
    ap.add_argument("--rejudge", default=None, metavar="REASON",
                    help="re-judge the executed cells already in <out-dir>/cells.jsonl with the current judge prompt (no assistant calls); REASON is recorded")
    ap.add_argument("--regenerate-transcripts", action="store_true",
                    help="rewrite <out-dir>/transcripts/ from the executed cells (no model call) and exit")
    a = ap.parse_args(argv)
    if a.regenerate_transcripts:
        n = regenerate_transcripts(a.out_dir)
        print(f"rewrote {n} transcripts under {a.out_dir}/transcripts")
        return 0
    cells, assemblies, scenarios, profiles, rubrics = load_inputs(a.matrix, a.assemblies_dir)
    columns = list(cells[0].keys()) if cells else []
    selected = select_cells(cells, parse_filter(a.filter, columns))
    if not selected:
        raise SystemExit("--filter selected no cells")
    out = pathlib.Path(a.out_dir)
    if a.adapter == "stub":
        existing, _ = read_executed(out / "cells.jsonl")
        if existing:
            raise SystemExit(f"{out} holds {len(existing)} executed cells; the stub adapter will not write there")
        adapter = StubAdapter()
    elif a.adapter == "anthropic":
        if "out-stub" in out.resolve().parts:
            raise SystemExit("a model run never writes under out-stub/ (that tree holds only NOT EXECUTED stubs)")
        if a.budget_usd is None:
            raise SystemExit("--adapter anthropic needs --budget-usd (the guard that stops a run or a judging pass at the authorized spend)")
        adapter = AnthropicAdapter(assistant_model=a.assistant_model, judge_model=a.judge_model)
    else:
        adapter = HttpAdapter()
    if a.rejudge is not None:
        if a.adapter != "anthropic":
            raise SystemExit("--rejudge needs --adapter anthropic")
        summary = rejudge_cells(out, adapter, scenarios, rubrics, concurrency=a.concurrency, reason=a.rejudge, argv=argv or sys.argv[1:],
                                budget_usd=a.budget_usd)
        print(f"re-judged {summary['cells_rejudged']} of {summary['cells_total']} cells with judge prompt v{JUDGE_PROMPT_VERSION}; "
              f"errors = {summary['cells_errored']}; not re-judged = {summary['cells_not_rejudged']}; "
              f"estimated spend this segment = {summary['estimated_cost_usd_this_segment']:.2f} USD")
        return 4 if summary["budget_hit"] else (3 if summary["cells_errored"] else 0)
    order = a.order.split(",") if a.order else None
    summary = run_matrix(selected, adapter, assemblies, scenarios, profiles, rubrics, out, concurrency=a.concurrency,
                         resume=a.resume, budget_usd=a.budget_usd, filter_spec=a.filter, order=order, argv=argv or sys.argv[1:])
    print(f"{pathlib.Path(a.matrix).stem}: {summary['cells_run']} cells run by {adapter.name}; executed = {summary['cells_executed']}, "
          f"errors = {summary['cells_error']}, skipped as done = {summary['cells_skipped_as_done']}, not started = {summary['cells_not_started']}; "
          f"estimated spend this segment = {summary['estimated_cost_usd_this_segment']:.2f} USD")
    if summary["budget_hit"]:
        return 4
    return 3 if summary["cells_error"] else 0


if __name__ == "__main__":
    sys.exit(main())

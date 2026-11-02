"""Shared helpers for the Wrenfield demonstration harness (stdlib + PyYAML only).

Everything here is fictional/illustrative. No model is called anywhere in this harness.
Scripts run under `python3 -I`, which does not add the script directory to sys.path;
each script therefore inserts its own directory before importing this module.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib

import yaml

DEMO = pathlib.Path(__file__).resolve().parent.parent
CONFIGS = DEMO / "configs"
SCENARIOS = DEMO / "scenarios"
PROFILES = DEMO / "profiles"
RUBRICS = DEMO / "rubrics"
NOT_EXECUTED = "NOT EXECUTED"


def load_yaml(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def dump_yaml(obj):
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=88)


def load_dir(directory):
    """Load every *.yaml in a directory into {id: record}."""
    return {d["id"]: d for d in (load_yaml(p) for p in sorted(directory.glob("*.yaml")))}


def load_rubric(rubric_id):
    """Load a rubric, merging an `extends:` parent by dimension id (child overrides, then appends)."""
    rb = load_yaml(RUBRICS / f"{rubric_id}.yaml")
    if rb.get("extends"):
        parent = load_rubric(rb["extends"])
        merged = {d["id"]: d for d in parent["dimensions"]}
        merged.update({d["id"]: d for d in rb["dimensions"]})
        rb["dimensions"] = list(merged.values())
    return rb


def dimensions_for(rubric, record):
    """The rubric's dimensions that apply to a cell record: every dimension without a `runs` list, plus those whose
    `runs` names the record's rubric run: `rubric_run` when a plan scores its cells under another run's dimensions
    (test_plan_run4 scores D2P1 as run 3 did, leaving the pinned rubric block untouched), else `run`, else
    `proposal`. A dimension pre-registered for a later run (RB-U-01 D2P, runs: [CP-0001-run2]) is therefore invisible
    to the evaluation of an earlier run's committed cells."""
    rec = record or {}
    run = rec.get("rubric_run") or rec.get("run") or rec.get("proposal")
    return [d for d in rubric["dimensions"] if not d.get("runs") or run in d["runs"]]


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def rel(path):
    """Path relative to demo/ for provenance fields; a path outside demo/ is recorded as given."""
    try:
        return str(pathlib.Path(path).resolve().relative_to(DEMO))
    except ValueError:
        return str(path)


def version_label(cfg):
    return f"{cfg['id']}@{cfg['version']}"


def write_text(path, text):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path, obj):
    write_text(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def load_dotenv(path=None) -> "str | None":
    """Make ANTHROPIC_API_KEY available to the real adapter. The environment wins; otherwise the first
    `KEY=value` line of demo/.env (git-ignored) is exported. Accepts `export KEY=...`, quotes, comments and
    CRLF. Returns the source used ("environment", "demo/.env") or None. Values are never logged."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "environment"
    path = pathlib.Path(path) if path else DEMO / ".env"
    if not path.exists():
        return None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().rstrip("\r")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if value[:1] in ('"', "'") and value.count(value[0]) >= 2:   # quoted value, then anything after the closing quote is dropped
            value = value[1:value.index(value[0], 1)]
        else:                                                        # bare value; an inline comment is dropped
            value = value.split(" #", 1)[0].strip()
        if key == "ANTHROPIC_API_KEY" and value:
            os.environ[key] = value
            return "demo/.env"
    return None

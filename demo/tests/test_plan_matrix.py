"""The planned matrix: counts, scope rule, rubric wiring."""
import collections
import json

import pytest

from common import DEMO, SCENARIOS, load_dir, load_yaml
from plan_matrix import COLUMNS, build_matrix, candidate_arms


@pytest.fixture(scope="module")
def cp0001(ensure_assemblies):
    proposal = load_yaml(DEMO / "proposals" / "CP-0001.yaml")
    return proposal, load_dir(SCENARIOS), build_matrix(proposal, load_dir(SCENARIOS))


def chain_of(assembly_id):
    rec = json.load(open(DEMO / "out" / "assemblies" / f"{assembly_id}.json", encoding="utf-8"))
    return {t["id"] for t in rec["tier_versions"]}


def test_cell_counts(cp0001):
    _, _, cells = cp0001
    assert len(cells) == 470   # 190 baseline + 140 per candidate arm
    assert sum(1 for c in cells if c["held_out"] == "true") == 60
    assert collections.Counter(c["arm"] for c in cells) == {"baseline": 190, "candidate-rc1": 140, "candidate-rc2": 140}
    by_arm_asm = collections.Counter((c["arm"], c["assembly_id"]) for c in cells)
    assert by_arm_asm[("candidate-rc1", "asm-H1-0002")] == 70 and by_arm_asm[("candidate-rc2", "asm-H1-0005")] == 70
    assert by_arm_asm[("candidate-rc2", "asm-H2-0003")] == 70 and by_arm_asm[("baseline", "asm-U-0001")] == 25
    assert len({c["cell_id"] for c in cells}) == len(cells)
    assert all(list(c) == COLUMNS for c in cells)


def test_every_cell_uses_its_scenarios_rubric(cp0001):
    _, scenarios, cells = cp0001
    assert all(c["rubric_ref"] == scenarios[c["scenario_id"]]["rubric_ref"] for c in cells)


def test_scope_rule_applicable_vs_all(cp0001):
    proposal, scenarios, cells = cp0001
    run_on = {sid: block.get("run_on", "applicable") for block in proposal["test_plan"]["scenario_sets"]
              for sid in block["scenarios"]}
    chains = {aid: chain_of(aid) for aid in {c["assembly_id"] for c in cells}}
    for c in cells:
        if run_on[c["scenario_id"]] != "all":
            assert scenarios[c["scenario_id"]]["owner_tier"] in chains[c["assembly_id"]], c["cell_id"]
    # the scope checks really do run the target family on the U-only and S1 assemblies
    assert {c["assembly_id"] for c in cells if c["scenario_id"] == "SC-H-004"} >= {"asm-U-0001", "asm-S1-0001"}


def test_profiles_come_from_block_or_scenario(cp0001):
    proposal, scenarios, cells = cp0001
    probe = [c for c in cells if c["scenario_set"] == "authorship-probe"]
    assert probe and {c["profile_id"] for c in probe} == {"SP-answer-extractor"}
    target = [c for c in cells if c["scenario_id"] == "SC-H-004"]
    assert {c["profile_id"] for c in target} == set(scenarios["SC-H-004"]["applicable_profiles"])


def test_repeats_override():
    proposal, scenarios = load_yaml(DEMO / "proposals" / "CP-0002.yaml"), load_dir(SCENARIOS)
    assert len(build_matrix(proposal, scenarios)) == 110
    assert len(build_matrix(proposal, scenarios, repeats=1)) == 22


def test_candidate_arms_accept_both_forms():
    named = {"assemblies": {"baseline": ["b"], "candidates": {"rc1": ["x"], "rc2": ["y", "z"]}}}
    assert candidate_arms(named) == [("baseline", ["b"]), ("candidate-rc1", ["x"]), ("candidate-rc2", ["y", "z"])]
    legacy = {"assemblies": {"baseline": ["b"], "candidate": ["c"]}}
    assert candidate_arms(legacy) == [("baseline", ["b"]), ("candidate", ["c"])]
    cp2 = load_yaml(DEMO / "proposals" / "CP-0002.yaml")
    assert [a for a, _ in candidate_arms(cp2["test_plan"])] == ["baseline", "candidate"]

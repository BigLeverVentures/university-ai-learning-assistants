"""Affected versions are computed over assembly records, never bare tiers."""
import pytest

from affected_versions import affected_versions
from assemble import assemble
from common import CONFIGS


@pytest.fixture(scope="module")
def baselines():
    return [assemble(CONFIGS / f"{tier}.yaml", [], 1) for tier in ("U", "H1", "H2", "S1")]


def targets(result):
    return {e["target"] for e in result["affected"]}


def test_rule_query_names_both_history_courses(baselines):
    res = affected_versions(baselines, "H", "H-R03")
    assert res["kind"] == "rule" and targets(res) == {"H1@1.0", "H2@1.0"}
    assert {e["target"] for e in res["unaffected"]} == {"U@2.0", "S1@1.0"}


def test_material_query_is_local_to_h1(baselines):
    res = affected_versions(baselines, "H1", "hargreaves-rta-ch4")
    assert res["kind"] == "material" and targets(res) == {"H1@1.0"}


def test_unknown_item_returns_an_empty_set_not_an_error(baselines):
    res = affected_versions(baselines, "H", "H-R99")
    assert res["affected"] == [] and len(res["unaffected"]) == 4 and res["kind"] == "unknown"


def test_a_superseded_rule_is_not_inherited(baselines):
    res = affected_versions(baselines, "U", "U-D03")
    assert targets(res) == {"U@2.0", "S1@1.0"}  # inactive under H@1.3 in H1 and H2

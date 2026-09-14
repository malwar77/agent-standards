"""Reference-value tests for discovery. The fixture project in
tests/fixtures/sample_project is deliberately constructed so every mined
number below is known exactly. If a miner changes its counting rule, these
tests catch the drift.
"""

import os
import shutil

import pytest

from agent_standards.discover.ast_mine import discover

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


@pytest.fixture()
def discovered():
    strong, weak = discover(FIXTURE, min_observations=1)
    by_id = {s.id: s for s in strong + weak}
    return strong, weak, by_id


def test_reference_values_naming_functions(discovered):
    _, _, by_id = discovered
    std = by_id["py-naming-functions"]
    assert std.evidence.observed == 8
    assert std.evidence.followed == 7
    assert std.evidence.consistency == 0.875


def test_reference_values_naming_classes(discovered):
    _, _, by_id = discovered
    std = by_id["py-naming-classes"]
    assert std.evidence.observed == 4
    assert std.evidence.followed == 3
    assert std.evidence.consistency == 0.75


def test_reference_values_docstrings(discovered):
    _, _, by_id = discovered
    std = by_id["py-docstrings-public"]
    assert std.evidence.observed == 12
    assert std.evidence.followed == 12
    assert std.evidence.consistency == 1.0


def test_reference_values_annotations(discovered):
    _, _, by_id = discovered
    std = by_id["py-type-annotations"]
    assert std.evidence.observed == 8
    assert std.evidence.followed == 6
    assert std.evidence.consistency == 0.75


def test_reference_values_import_order(discovered):
    _, _, by_id = discovered
    std = by_id["py-import-order"]
    assert std.evidence.observed == 5
    assert std.evidence.followed == 4
    assert std.evidence.consistency == 0.8


def test_weak_test_naming_goes_to_weak_list(discovered):
    strong, weak, by_id = discovered
    assert "py-test-naming" in by_id
    assert by_id["py-test-naming"] not in strong
    assert by_id["py-test-naming"] in weak
    assert by_id["py-test-naming"].evidence.observed == 2
    assert by_id["py-test-naming"].evidence.followed == 1


def test_strong_patterns_classified_by_consistency(discovered):
    strong, weak, by_id = discovered
    strong_ids = {s.id for s in strong}
    assert strong_ids == {
        "py-naming-functions", "py-naming-classes", "py-docstrings-public",
        "py-type-annotations", "py-import-order",
    }


def test_min_observations_filters_tiny_codebases(tmp_path):
    """With min_observations higher than the fixture's counts, nothing is
    proposed — evidence must exist before a standard is claimed."""
    strong, weak = discover(FIXTURE, min_observations=100)
    assert strong == [] and weak == []


def test_discovery_is_read_only():
    import hashlib
    def tree_hash():
        h = hashlib.sha1()
        for dirpath, _, files in os.walk(FIXTURE):
            for f in sorted(files):
                p = os.path.join(dirpath, f)
                h.update(open(p, "rb").read())
        return h.hexdigest()
    before = tree_hash()
    discover(FIXTURE, min_observations=1)
    assert tree_hash() == before

"""Eval: did the code in a change actually follow the injected standards?

Given a set of changed files (e.g. from a git diff --name-only), re-run the
relevant miners restricted to those files and report per-standard consistency
in the changed code vs the codebase-wide recorded value. Read-only measurement.
"""

from __future__ import annotations

import ast
import os

from .index.store import Standard
from .discover.ast_mine import (
    iter_python_files, mine_functions, mine_classes, mine_docstrings,
    mine_annotations, mine_imports, mine_test_files, _default_patterns,
)


def _changed_root(changed_files: list) -> str:
    """Best-effort repo root from a list of paths."""
    common = os.path.commonpath([os.path.abspath(f) for f in changed_files]) \
        if changed_files else os.getcwd()
    return common


def score_change(changed_files: list, standards: list) -> list:
    """Return [(standard, consistency_in_changed_code, recorded_consistency)]."""
    pats = {p.id: p for p in _default_patterns()}
    counters = {
        "py-naming-functions": mine_functions,
        "py-naming-classes": mine_classes,
        "py-docstrings-public": mine_docstrings,
        "py-type-annotations": mine_annotations,
        "py-import-order": mine_imports,
    }
    py_files = [f for f in changed_files if f.endswith(".py")]
    for path in py_files:
        if not os.path.exists(path):
            continue
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except (SyntaxError, OSError):
            continue
        rel = os.path.relpath(os.path.abspath(path), _changed_root(py_files))
        for pid, fn in counters.items():
            fn(tree, rel, pats[pid])

    results = []
    for std in standards:
        p = pats.get(std.id)
        if p is None or p.observed == 0:
            results.append((std, None,
                            std.evidence.consistency if std.evidence else None))
            continue
        results.append((std, round(p.followed / p.observed, 3),
                        std.evidence.consistency if std.evidence else None))
    return results

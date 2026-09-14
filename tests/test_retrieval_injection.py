"""Retrieval + injection tests: BM25 ranking, token budget, adapters."""

import pytest

from agent_standards.index.retrieval import retrieve, build_index
from agent_standards.index.store import Standard, Evidence
from agent_standards.inject.injector import inject


def _std(id, title, body, tags):
    return Standard(id=id, title=title, body=body, tags=tags,
                    status="approved", source="manual")


STANDARDS = [
    _std("py-naming-functions", "Function names are snake_case",
         "Public functions use snake_case names in this codebase.",
         ["python", "naming", "functions"]),
    _std("py-test-naming", "Test files are named test_*.py",
         "Test modules follow test_<subject>.py naming and each test "
         "function starts with test_.",
         ["python", "tests", "naming"]),
    _std("py-import-order", "Standard-library imports precede third-party",
         "In each module, stdlib imports come before third-party imports.",
         ["python", "imports", "style"]),
]


def test_query_about_tests_ranks_testing_first():
    ranked = retrieve("write unit tests for the parser", STANDARDS, top_k=3)
    assert ranked[0][1].id == "py-test-naming"


def test_query_about_naming_ranks_naming_first():
    ranked = retrieve("add a new helper function, what naming convention", STANDARDS, top_k=3)
    assert ranked[0][1].id == "py-naming-functions"


def test_query_about_imports_ranks_imports_first():
    ranked = retrieve("where do imports go in a module", STANDARDS, top_k=3)
    assert ranked[0][1].id == "py-import-order"


def test_retrieval_is_deterministic():
    a = retrieve("naming convention for functions", STANDARDS, top_k=3)
    b = retrieve("naming convention for functions", STANDARDS, top_k=3)
    assert [(s.id, round(x, 9)) for x, s in a] == [(s.id, round(x, 9)) for x, s in b]


def test_unrelated_query_returns_nothing_above_cutoff():
    ranked = retrieve("deploy the app to production kubernetes", STANDARDS, top_k=3)
    assert ranked == []


def test_inject_respects_token_budget():
    big = [Standard(id=f"std-{i}", title=f"Standard {i}",
                    body="lorem ipsum " * 400, tags=["x"], status="approved")
           for i in range(10)]
    out = inject("lorem ipsum standard", big, token_budget=300)
    # ~300 tokens max, allow the renderer's fixed heading overhead
    assert len(out) // 4 < 400


def test_inject_only_includes_relevant():
    out = inject("write unit tests for the parser", STANDARDS, top_k=1)
    assert "test_<subject>.py" in out
    assert "snake_case" not in out


def test_markdown_adapter_shape():
    out = inject("write unit tests", STANDARDS, fmt="markdown", top_k=1)
    assert out.startswith("## Coding standards relevant to this task")


def test_claude_skill_adapter_shape():
    out = inject("write unit tests", STANDARDS, fmt="claude-skill", top_k=1)
    assert out.startswith("---\nname: codebase-standards")


def test_cursor_rule_adapter_shape():
    out = inject("write unit tests", STANDARDS, fmt="cursor-rule", top_k=1)
    assert out.startswith("---\nglobs:")


def test_unknown_format_rejected():
    with pytest.raises(ValueError):
        inject("task", STANDARDS, fmt="nope")


def test_evidence_line_in_output():
    with_ev = Standard(id="s1", title="Function names are snake_case",
                       body="Use snake_case.", tags=[], status="approved",
                       evidence=Evidence(observed=8, followed=7))
    out = inject("function names snake_case rule", [with_ev], top_k=1)
    assert "7/8" in out and "88%" in out

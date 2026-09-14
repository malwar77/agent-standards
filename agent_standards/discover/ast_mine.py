"""Deterministic standards discovery via AST mining.

Pass 1 (this module): mine observable, checkable patterns from the codebase and
emit candidate standards with hard evidence (observed/followed counts and sample
files). No LLM, no API keys — the evidence IS the candidate.

A pattern observed in >= min_observations code points and followed at >=
min_consistency is proposed as an `approved`-recommended candidate; anything
between discovery_threshold and min_consistency is proposed as a candidate with
a note; below that, the pattern is not a standard and is skipped.

Pass 2 (LLM drafting, optional): an advisory-only layer. NOT required, and by
design never creates or mutates evidence — it can only rewrite title/body text
of a candidate. See llm_draft.py.
"""

from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass

from ..index.store import Evidence, Standard

SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PASCAL_RE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
UPPER_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
TEST_FILE_RE = re.compile(r"^test_[a-z0-9_]+\.py$")


@dataclass
class MinedPattern:
    id: str
    title: str
    category: str
    tags: list
    observed: int = 0
    followed: int = 0
    sample_ok: list = None
    sample_bad: list = None
    body_ok: str = ""
    body_violation: str = ""

    def __post_init__(self):
        self.sample_ok = self.sample_ok or []
        self.sample_bad = self.sample_bad or []

    def to_standard(self, min_consistency: float) -> Standard:
        ev = Evidence(observed=self.observed, followed=self.followed,
                      sample_files=(self.sample_bad or self.sample_ok)[:5])
        consistent = ev.consistency >= min_consistency
        status = "candidate"
        body = self.body_ok if consistent else self.body_violation
        return Standard(
            id=self.id,
            title=self.title if consistent else f"{self.title} (mixed/inconsistent)",
            body=body,
            category=self.category,
            tags=self.tags,
            status=status,
            source="discovered",
            evidence=ev,
        )


def iter_python_files(root: str):
    skip = {"node_modules", ".git", ".venv", "venv", "__pycache__", ".agent-standards"}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fname in filenames:
            if fname.endswith(".py"):
                yield os.path.join(dirpath, fname)


def _rel(path: str, root: str) -> str:
    return os.path.relpath(path, root)


def mine_functions(tree, path, pattern: MinedPattern):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            pattern.observed += 1
            if SNAKE_RE.match(node.name) or node.name.startswith("__"):
                pattern.followed += 1
                if len(pattern.sample_ok) < 5:
                    pattern.sample_ok.append(f"{path}::{node.name}")
            elif len(pattern.sample_bad) < 5:
                pattern.sample_bad.append(f"{path}::{node.name}")


def mine_classes(tree, path, pattern: MinedPattern):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            pattern.observed += 1
            if PASCAL_RE.match(node.name):
                pattern.followed += 1
                if len(pattern.sample_ok) < 5:
                    pattern.sample_ok.append(f"{path}::{node.name}")
            elif len(pattern.sample_bad) < 5:
                pattern.sample_bad.append(f"{path}::{node.name}")


def mine_docstrings(tree, path, pattern: MinedPattern):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name.startswith("_"):
                continue
            pattern.observed += 1
            if ast.get_docstring(node):
                pattern.followed += 1
                if len(pattern.sample_ok) < 5:
                    pattern.sample_ok.append(f"{path}::{node.name}")
            elif len(pattern.sample_bad) < 5:
                pattern.sample_bad.append(f"{path}::{node.name}")


def mine_annotations(tree, path, pattern: MinedPattern):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            pattern.observed += 1
            has_ret = node.returns is not None
            has_args = all(
                a.annotation is not None
                for a in node.args.args if a.arg not in ("self", "cls")
            )
            if has_ret and has_args:
                pattern.followed += 1
                if len(pattern.sample_ok) < 5:
                    pattern.sample_ok.append(f"{path}::{node.name}")
            elif len(pattern.sample_bad) < 5:
                pattern.sample_bad.append(f"{path}::{node.name}")


def mine_imports(tree, path, pattern: MinedPattern):
    """Standard-library imports come before third-party/local imports."""
    import_nodes = [n for n in ast.walk(tree)
                    if isinstance(n, (ast.Import, ast.ImportFrom))]
    if not import_nodes:
        return
    pattern.observed += 1  # one observation per file
    first_non_std = None
    seen_non_std = False
    for node in import_nodes:
        module = ""
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
        elif isinstance(node, ast.Import):
            module = node.names[0].name
        top = module.split(".")[0]
        if top not in ("os", "sys", "re", "json", "math", "typing", "dataclasses",
                       "collections", "pathlib", "datetime", "itertools",
                       "functools", "unittest", "asyncio", "ast"):
            seen_non_std = True
            first_non_std = first_non_std or top
        elif seen_non_std:
            # stdlib import after a non-stdlib import in a file lacking
            # from __future__ — count as violation only if unsorted block
            pattern.sample_bad.append(f"{path}:std-after-{first_non_std}")
            return
    pattern.followed += 1
    if len(pattern.sample_ok) < 5:
        pattern.sample_ok.append(path)


def mine_test_files(root: str, pattern: MinedPattern):
    tests_dir = os.path.join(root, "tests")
    if not os.path.isdir(tests_dir):
        return
    for fname in os.listdir(tests_dir):
        if not fname.endswith(".py"):
            continue
        pattern.observed += 1
        if TEST_FILE_RE.match(fname):
            pattern.followed += 1
            if len(pattern.sample_ok) < 5:
                pattern.sample_ok.append(f"tests/{fname}")
        elif len(pattern.sample_bad) < 5:
            pattern.sample_bad.append(f"tests/{fname}")


def _default_patterns():
    return [
        MinedPattern(
            id="py-naming-functions",
            title="Function names are snake_case",
            category="naming",
            tags=["python", "naming", "functions"],
            body_ok="Public functions use snake_case names (e.g. load_config, "
                    "not loadConfig). Observed consistently in the codebase.",
            body_violation="Function naming is mixed in the codebase; adopt "
                           "snake_case for new functions unless a local module "
                           "clearly established another convention.",
        ),
        MinedPattern(
            id="py-naming-classes",
            title="Class names are PascalCase",
            category="naming",
            tags=["python", "naming", "classes"],
            body_ok="Classes use PascalCase names (e.g. RiskManager).",
            body_violation="Class naming is mixed; prefer PascalCase for new classes.",
        ),
        MinedPattern(
            id="py-docstrings-public",
            title="Public functions and classes have docstrings",
            category="documentation",
            tags=["python", "docs", "docstring"],
            body_ok="Every public function/class starts with a one-line docstring "
                    "explaining intent.",
            body_violation="Docstring coverage is mixed; add a docstring to new "
                           "public functions and classes.",
        ),
        MinedPattern(
            id="py-type-annotations",
            title="Function signatures are fully type-annotated",
            category="typing",
            tags=["python", "typing", "annotations"],
            body_ok="All function parameters and return types are annotated.",
            body_violation="Annotation coverage is mixed; annotate new function "
                           "signatures.",
        ),
        MinedPattern(
            id="py-import-order",
            title="Standard-library imports precede third-party imports",
            category="imports",
            tags=["python", "imports", "style"],
            body_ok="In each module, stdlib imports come before third-party and "
                    "local imports.",
            body_violation="Import ordering is inconsistent; keep stdlib imports "
                           "first in new modules.",
        ),
        MinedPattern(
            id="py-test-naming",
            title="Test files are named test_*.py",
            category="testing",
            tags=["python", "tests", "naming"],
            body_ok="Test modules follow test_<subject>.py naming.",
            body_violation="Test file naming is mixed; name new test modules "
                           "test_<subject>.py.",
        ),
    ]


def discover(root: str, min_observations: int = 5, min_consistency: float = 0.7):
    """Mine the codebase at `root`; return (approved_candidates, weak_candidates).

    Deterministic: same tree in, same candidates out. Purely read-only.
    """
    patterns = _default_patterns()
    by_id = {p.id: p for p in patterns}
    counters = {
        "py-naming-functions": mine_functions,
        "py-naming-classes": mine_classes,
        "py-docstrings-public": mine_docstrings,
        "py-type-annotations": mine_annotations,
        "py-import-order": mine_imports,
    }
    files = list(iter_python_files(root))
    for path in files:
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except (SyntaxError, OSError):
            continue
        rel = _rel(path, root)
        for pid, fn in counters.items():
            fn(tree, rel, by_id[pid])
    mine_test_files(root, by_id["py-test-naming"])

    strong, weak = [], []
    for p in patterns:
        if p.observed < min_observations:
            continue  # not enough evidence to call it a convention
        std = p.to_standard(min_consistency)
        (strong if std.evidence.consistency >= min_consistency else weak).append(std)
    return strong, weak

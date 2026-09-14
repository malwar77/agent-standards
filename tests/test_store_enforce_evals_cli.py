"""Store, enforcement, evals, LLM-pass-through, and end-to-end CLI tests."""

import os
import shutil

import pytest

from agent_standards.cli import main
from agent_standards.discover.ast_mine import discover
from agent_standards.discover.llm_draft import draft
from agent_standards.enforce.check import enforce
from agent_standards.evals import score_change
from agent_standards.index.store import Store, Standard, Evidence

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


@pytest.fixture()
def proj(tmp_path):
    """A store whose project profile already holds fixture-discovered standards."""
    shutil.copytree(FIXTURE, tmp_path / "repo")
    store = Store(project_dir=str(tmp_path / "repo" / ".agent-standards"))
    strong, _ = discover(str(tmp_path / "repo"), min_observations=1)
    for std in strong:
        std.status = "approved"
        store.save(std)
    return store, tmp_path / "repo"


def test_store_roundtrip(proj):
    store, _ = proj
    loaded = store.load_all(statuses=("approved",))
    by_id = {s.id: s for s in loaded}
    assert by_id["py-docstrings-public"].evidence.followed == 12
    assert by_id["py-docstrings-public"].evidence.observed == 12


def test_project_overrides_base(tmp_path):
    base = Store(project_dir=str(tmp_path / "base"), base_dir=None)
    s1 = Standard(id="x", title="Base version", body="from base", status="approved")
    base.save(s1)
    proj_store = Store(project_dir=str(tmp_path / "proj"),
                      base_dir=str(tmp_path / "base"))
    s2 = Standard(id="x", title="Project version", body="from project",
                  status="approved")
    proj_store.save(s2)
    got = {s.id: s for s in proj_store.load_all()}
    assert got["x"].title == "Project version"


def test_sync_to_base(tmp_path):
    proj_store = Store(project_dir=str(tmp_path / "proj"),
                       base_dir=str(tmp_path / "base"))
    proj_store.save(Standard(id="y", title="T", body="B", status="approved"))
    moved = proj_store.sync_to_base()
    assert moved == 1
    assert os.path.exists(tmp_path / "base" / "standards" / "y.yaml")


def test_enforce_passes_on_unchanged_codebase(proj):
    store, repo = proj
    # mark one standard critical, recorded consistency must still hold
    stds = {s.id: s for s in store.load_all()}
    s = stds["py-docstrings-public"]
    s.critical = True
    store.save(s)
    result = enforce(str(repo), store, tolerance=0.0)
    assert result.passed, result.report()


def test_enforce_fails_on_regression(proj):
    store, repo = proj
    stds = {s.id: s for s in store.load_all()}
    s = stds["py-docstrings-public"]
    s.critical = True
    store.save(s)
    # regression: add an undocumented public function
    with open(repo / "src" / "regression.py", "w") as fh:
        fh.write("def undocumented_new_public(x):\n    return x\n")
    result = enforce(str(repo), store, tolerance=0.0)
    assert not result.passed
    assert "FAIL" in result.report()


def test_enforce_noop_without_critical(proj):
    store, repo = proj
    result = enforce(str(repo), store)
    assert result.passed and result.checked == []


def test_score_change_reports_changed_code_consistency(proj):
    store, repo = proj
    stds = {s.id: s for s in store.load_all()}
    results = dict(
        (std.id, (cur, rec))
        for std, cur, rec in score_change([str(repo / "src" / "beta.py")],
                                          list(stds.values())))
    # beta.py is fully snake_case: 3 functions, all followed
    assert results["py-naming-functions"][0] == 1.0
    # recorded repo-wide value is 7/8 = 0.875
    assert results["py-naming-functions"][1] == 0.875


def test_llm_draft_passes_through_when_unreachable():
    std = Standard(id="a", title="T", body="B", status="candidate",
                   evidence=Evidence(observed=10, followed=9))
    out = draft(std, base_url="http://127.0.0.1:9", model="test")
    assert out.title == "T" and out.body == "B"
    assert out.evidence.observed == 10 and out.evidence.followed == 9


def test_cli_end_to_end_discover_review_inject(tmp_path, capsys, monkeypatch):
    shutil.copytree(FIXTURE, tmp_path / "repo")
    monkeypatch.chdir(tmp_path / "repo")
    store_dir = str(tmp_path / "repo" / ".agent-standards")

    assert main(["discover", ".", "--min-observations", "1"]) == 0
    out = capsys.readouterr().out
    assert "discovered: 5 strong, 1 weak" in out

    # auto-approve everything at >= 0.7 consistency
    assert main(["review", "--auto-approve", "--threshold", "0.7"]) == 0

    assert main(["inject", "write a new function to fetch data",
                 "--top-k", "3"]) == 0
    out = capsys.readouterr().out
    assert "## Coding standards relevant to this task" in out
    assert "snake_case" in out

    # enforce with no critical standards is a no-op pass
    assert main(["enforce", "."]) == 0

    # score the beta module
    assert main(["score", "src/beta.py"]) == 0
    out = capsys.readouterr().out
    assert "py-naming-functions" in out

    assert os.path.exists(os.path.join(store_dir, "standards",
                                       "py-naming-functions.yaml"))


def test_cli_enforce_exit_code_on_failure(tmp_path, capsys, monkeypatch):
    shutil.copytree(FIXTURE, tmp_path / "repo")
    monkeypatch.chdir(tmp_path / "repo")
    main(["discover", ".", "--min-observations", "1"])
    main(["review", "--auto-approve", "--threshold", "0.7"])
    # make docstrings critical, then break it
    store = Store(project_dir=".agent-standards")
    stds = {s.id: s for s in store.load_all()}
    s = stds["py-docstrings-public"]
    s.critical = True
    store.save(s)
    with open("src/regression.py", "w") as fh:
        fh.write("def undocumented_public(x):\n    return x\n")
    rc = main(["enforce", ".", "--tolerance", "0.0"])
    assert rc == 1
    assert "FAIL" in capsys.readouterr().out

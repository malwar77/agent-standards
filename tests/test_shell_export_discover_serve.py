"""Tests for the 50/30/20 restructure: shell discover (heuristic reference
values), shell + python export, self-contained dashboard, and serve."""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_standards.cli import main  # noqa: E402
from agent_standards.index.store import Store, Standard, Evidence  # noqa: E402

REPO = os.path.join(os.path.dirname(__file__), "..")
BIN = os.path.join(REPO, "bin", "agent-standards")
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")
SHELL_ENV = {"AGENT_STANDARDS_NO_PYTHON": "1"}


def run_shell(args, env_extra=None, cwd=None):
    env = dict(os.environ)
    env.pop("AGENT_STANDARDS_NO_PYTHON", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run([BIN] + args, capture_output=True, text=True,
                          env=env, cwd=cwd or REPO)


# --------------------------------------------------------- shell discover
def test_shell_discover_matches_ast_reference_values():
    r = run_shell(["discover", FIXTURE], env_extra=SHELL_ENV)
    assert r.returncode == 0
    out = r.stdout
    # must match the exact AST counts pinned in test_discovery_reference_values
    assert "snake_case   7/8 (87%)" in out
    assert "PascalCase   3/4 (75%)" in out
    assert "docstrings  present      12/12 (100%)" in out
    assert "test_*.py    1/2 (50%)" in out


def test_shell_discover_on_empty_dir(tmp_path):
    r = run_shell(["discover", str(tmp_path)], env_extra=SHELL_ENV)
    assert r.returncode == 0
    assert "0/0 (0%)" in r.stdout


# --------------------------------------------------------- export / dashboard
@pytest.fixture()
def ev_profile(tmp_path):
    profile = str(tmp_path / "proj" / ".agent-standards")
    os.makedirs(profile, exist_ok=True)
    store = Store(project_dir=profile)
    store.save(Standard(id="py-naming-functions",
                        title="Function names are snake_case",
                        body="Public functions use snake_case names.",
                        tags=["naming"], status="approved",
                        evidence=Evidence(observed=8, followed=7)))
    store.save(Standard(id="py-test-naming",
                        title="Test files are named test_*.py",
                        body="Test modules follow test naming.",
                        tags=["tests"], status="candidate", critical=True))
    return profile


def test_shell_export_json_with_evidence(ev_profile):
    r = run_shell(["export", ev_profile], env_extra=SHELL_ENV)
    assert r.returncode == 0
    data = json.load(open(os.path.join(ev_profile, "standards.json")))
    assert data["profile"] == ev_profile
    by_id = {s["id"]: s for s in data["standards"]}
    assert by_id["py-naming-functions"]["evidence"]["followed"] == 7
    assert by_id["py-naming-functions"]["evidence"]["observed"] == 8
    assert by_id["py-test-naming"]["evidence"] is None
    assert by_id["py-test-naming"]["critical"] is True


def test_shell_export_dashboard_is_self_contained(ev_profile):
    r = run_shell(["export", ev_profile, "--dashboard"], env_extra=SHELL_ENV)
    assert r.returncode == 0
    html = open(os.path.join(ev_profile, "dashboard.html")).read()
    assert "__STANDARDS_JSON__" not in html
    assert "Function names are snake_case" in html
    assert '"followed": 7' in html


def test_python_cli_export_and_dashboard(ev_profile, capsys):
    assert main(["export", ev_profile, "--dashboard"]) == 0
    out = capsys.readouterr().out
    assert "dashboard ->" in out
    data = json.load(open(os.path.join(ev_profile, "standards.json")))
    by_id = {s["id"]: s for s in data["standards"]}
    assert by_id["py-naming-functions"]["evidence"]["consistency"] == 0.875
    html = open(os.path.join(ev_profile, "dashboard.html")).read()
    assert "__STANDARDS_JSON__" not in html
    assert "Test files are named test_*.py" in html


def test_dashboard_template_has_valid_placeholder():
    tpl = open(os.path.join(REPO, "dashboard", "template.html")).read()
    assert "let DATA = __STANDARDS_JSON__;" in tpl


# ----------------------------------------------------------------- serve
def test_serve_serves_dashboard_and_json(ev_profile):
    import socket
    # pick a guaranteed-free port so leftover servers never break this test
    with socket.socket() as sk:
        sk.bind(("127.0.0.1", 0))
        port = sk.getsockname()[1]
    proc = subprocess.Popen(
        [BIN, "serve", str(port), ev_profile],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)   # own process group -> killable below
    try:
        for _ in range(30):
            time.sleep(0.2)
            try:
                html = urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/dashboard.html", timeout=2).read()
                break
            except OSError:
                continue
        else:
            pytest.fail("server never came up")
        assert b"agent-standards" in html
        raw = urllib.request.urlopen(
            f"http://127.0.0.1:{port}/standards.json", timeout=2).read()
        data = json.loads(raw)
        assert data["standards"][0]["id"] == "py-naming-functions"
    finally:
        # kill the WHOLE process group: the exec'd http.server is a
        # grandchild that survives a plain terminate()
        import signal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)


# ------------------------------------------------------- shell sync
def test_shell_sync_copies_to_base(ev_profile, tmp_path):
    base = str(tmp_path / "base")
    r = run_shell(["sync", ev_profile],
                  env_extra=dict(SHELL_ENV, AGENT_STANDARDS_BASE=base))
    assert r.returncode == 0
    files = os.listdir(os.path.join(base, "standards"))
    assert "py-naming-functions.yaml" in files and len(files) == 2


def test_shell_sync_needs_base(ev_profile):
    r = run_shell(["sync", ev_profile], env_extra=SHELL_ENV)
    assert r.returncode == 2
    assert "AGENT_STANDARDS_BASE" in r.stderr

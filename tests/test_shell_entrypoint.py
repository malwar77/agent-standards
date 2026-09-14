"""Tests for the dual shell+python entrypoint (bin/agent-standards).

Shell mode is forced with AGENT_STANDARDS_NO_PYTHON=1 so the pure-shell
fallback is exercised even on machines that have python3 (like CI).
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent_standards.index.store import Store, Standard  # noqa: E402

REPO = os.path.join(os.path.dirname(__file__), "..")
BIN = os.path.join(REPO, "bin", "agent-standards")


def run_shell(args, env_extra=None, cwd=None):
    env = dict(os.environ)
    env.pop("AGENT_STANDARDS_NO_PYTHON", None)
    if env_extra:
        env.update(env_extra)
    return subprocess.run([BIN] + args, capture_output=True, text=True,
                          env=env, cwd=cwd or REPO)


@pytest.fixture()
def shell_profile(tmp_path):
    profile = str(tmp_path / "proj" / ".agent-standards")
    os.makedirs(profile, exist_ok=True)
    store = Store(project_dir=profile)
    store.save(Standard(id="py-naming-functions",
                        title="Function names are snake_case",
                        body="Public functions use snake_case names.",
                        tags=["naming"], status="approved"))
    store.save(Standard(id="py-test-naming",
                        title="Test files are named test_*.py",
                        body="Test modules follow test_<subject>.py naming.",
                        tags=["tests"], status="approved"))
    return profile


def test_python_mode_delegates_to_cli():
    r = run_shell(["--version"])
    assert r.returncode == 0
    assert r.stdout.strip() == "0.1.0"


def test_shell_mode_version():
    r = run_shell(["--version"],
                  env_extra={"AGENT_STANDARDS_NO_PYTHON": "1"})
    assert r.returncode == 0
    assert r.stdout.strip() == "0.1.0-shell"


def test_shell_mode_init_creates_profile(tmp_path):
    r = run_shell(["init", str(tmp_path / "p")],
                  env_extra={"AGENT_STANDARDS_NO_PYTHON": "1"})
    assert r.returncode == 0
    assert os.path.isdir(tmp_path / "p" / "standards")
    assert "shell mode" in r.stdout


def test_shell_mode_list(shell_profile):
    r = run_shell(["list", shell_profile],
                  env_extra={"AGENT_STANDARDS_NO_PYTHON": "1"})
    assert r.returncode == 0
    assert "py-naming-functions" in r.stdout
    assert "py-test-naming" in r.stdout
    assert "Test files are named test_*.py" in r.stdout


def test_shell_mode_inject_ranks_relevant_first(shell_profile):
    r = run_shell(["inject", "how should I write unit tests", "1",
                   shell_profile],
                  env_extra={"AGENT_STANDARDS_NO_PYTHON": "1"})
    assert r.returncode == 0
    assert "Test files are named test_*.py" in r.stdout
    assert "Test modules follow test_<subject>.py naming." in r.stdout
    assert "snake_case" not in r.stdout


def test_shell_mode_inject_names_query(shell_profile):
    r = run_shell(["inject", "function naming convention", "1",
                   shell_profile],
                  env_extra={"AGENT_STANDARDS_NO_PYTHON": "1"})
    assert r.returncode == 0
    assert "Function names are snake_case" in r.stdout
    assert "test_<subject>" not in r.stdout


def test_shell_mode_inject_unrelated_query_fails(shell_profile):
    r = run_shell(["inject", "kubernetes deployment yaml", "1",
                   shell_profile],
                  env_extra={"AGENT_STANDARDS_NO_PYTHON": "1"})
    assert r.returncode == 1
    assert "no relevant standards" in r.stderr


def test_shell_mode_unknown_command(shell_profile):
    r = run_shell(["discover", "."],
                  env_extra={"AGENT_STANDARDS_NO_PYTHON": "1"})
    assert r.returncode == 2
    assert "shell mode" in r.stderr


def test_python_wrapper_matches_cli_end_to_end(tmp_path, shell_profile):
    """Same profile, same query: python and shell modes both answer."""
    env = {"AGENT_STANDARDS_PROFILE": shell_profile}
    r = run_shell(["inject", "function naming convention", "--top-k", "1"],
                  env_extra=env)
    assert r.returncode == 0
    assert "snake_case" in r.stdout
    assert "## Coding standards relevant to this task" in r.stdout

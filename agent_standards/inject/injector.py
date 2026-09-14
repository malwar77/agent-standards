"""Inject the most relevant standards as context for an AI coding agent.

Adapters:
  markdown     — a plain `## Coding standards` block (default; works anywhere)
  claude-skill — a Claude Code SKILL.md file
  cursor-rule  — a Cursor .mdc rule file

All output is markdown text; no agent has special powers here. Standards are
advisory by nature — enforcement is a separate, opt-in mechanism (enforce/).
"""

from __future__ import annotations

from ..index.retrieval import build_index
from ..index.store import Standard


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _entry(std: Standard, score: float) -> str:
    ev = std.evidence
    evidence_line = ""
    if ev and ev.observed:
        evidence_line = (f" (observed {ev.followed}/{ev.observed} in this "
                         f"codebase, {ev.consistency:.0%} consistent)")
    return f"### {std.title}{evidence_line}\n\n{std.body.strip()}\n"


def render_markdown(stds_scores: list, task: str) -> str:
    lines = ["## Coding standards relevant to this task", ""]
    for std, score in stds_scores:
        lines.append(_entry(std, score))
    return "\n".join(lines).rstrip() + "\n"


def render_claude_skill(stds_scores: list, task: str) -> str:
    body = render_markdown(stds_scores, task)
    return (
        "---\n"
        "name: codebase-standards\n"
        "description: House coding standards relevant to the current task\n"
        "---\n\n" + body
    )


def render_cursor_rule(stds_scores: list, task: str) -> str:
    body = "\n".join(_entry(std, s) for std, s in stds_scores)
    return (
        "---\n"
        "globs: **/*\n"
        "alwaysApply: false\n"
        "---\n\n" + body
    )


RENDERERS = {
    "markdown": render_markdown,
    "claude-skill": render_claude_skill,
    "cursor-rule": render_cursor_rule,
}


def inject(task: str, standards: list, fmt: str = "markdown",
           top_k: int = 5, token_budget: int = 800) -> str:
    """Retrieve the most relevant standards and render them for the agent.

    Never exceeds `token_budget` (rough 4-chars-per-token estimate): standards
    are added best-score-first until the budget is exhausted.
    """
    idx = build_index(standards)
    ranked = idx.search(task, top_k=top_k)
    picked, used = [], 0
    for score, std in ranked:
        cost = _estimate_tokens(_entry(std, score))
        if used + cost > token_budget:
            break
        picked.append((std, score))
        used += cost
    renderer = RENDERERS.get(fmt)
    if not renderer:
        raise ValueError(f"unknown format {fmt!r}; use one of {list(RENDERERS)}")
    return renderer(picked, task)

# agent-standards

**EXPERIMENTAL / EDUCATIONAL** — a lightweight, tool-agnostic system for
discovering your codebase's implicit coding conventions, turning them into
evidence-backed standards, and injecting only the relevant ones into AI coding
agents (Claude Code, Cursor, or anything that reads markdown).

> Not affiliated with [Builder Methods / Agent OS](https://github.com/buildermethods/agent-os),
> which inspired this project. This is an independent MIT-licensed
> reimplementation with a different emphasis: hard evidence, local-first
> retrieval, and optional enforcement.

## Why

AI coding agents constantly ignore or reinvent your house style. The fix is not
a bigger system prompt — it is (1) knowing what your conventions actually are,
(2) proving them with evidence, and (3) injecting only the relevant few at the
right moment.

## How it works

```
discover  →  review  →  index  →  inject  →  (optional) enforce  →  score
   AST mining    approve     BM25      context       hard gates       evals
   (evidence)    (human)     lexical   for agent     for critical    (did the
                                                          standards    code follow?)
```

1. **Discover** — deterministic AST miners extract observable patterns
   (naming, docstrings, annotations, import order, test naming) with hard
   evidence: `followed/observed` counts and sample files. No LLM required.
   An optional, *advisory-only* local Ollama pass can polish prose — it can
   never touch evidence, ids, or approval status.
2. **Review** — a human (or `--auto-approve --threshold 0.9`) approves
   candidates. Evidence is shown for every decision.
3. **Index & inject** — BM25-style lexical retrieval picks the few standards
   relevant to the current task, within a token budget. Formats: plain
   markdown, Claude Code skill, Cursor rule.
4. **Enforce (opt-in)** — standards you mark `critical: true` are re-checked
   by CI/pre-commit; a consistency regression fails the build.
5. **Score** — measure whether changed code actually follows the standards
   that were injected.

## 50% shell / 30% Python / 20% HTML

One system, three layers:

```bash
bin/agent-standards init .      # shell layer: the whole user loop
bin/agent-standards discover .  # heuristic counts; exact AST via python
bin/agent-standards inject "add a retry wrapper"
bin/agent-standards export . --dashboard
bin/agent-standards serve       # live dashboard on localhost
```

The *shell layer* (POSIX, mawk-safe) owns the interface: init, heuristic
discover, list, lexical inject, JSON export, the self-contained dashboard
build, serve, sync. It needs zero dependencies — python3 only upgrades it.

The *Python layer* is the engine: exact AST discovery with evidence,
BM25 retrieval, interactive review, enforcement gates, and evals. When
python3 is present the shell entrypoint transparently delegates to it
(`AGENT_STANDARDS_NO_PYTHON=1` forces the pure-shell path).

The *HTML layer* is the dashboard: standards cards with evidence bars
(followed/observed consistency), status and critical badges, live filter.
`export --dashboard` builds a self-contained, double-clickable file;
`serve` runs it live with `standards.json` fetched fresh.

`install.sh` copies the Agent-OS-style agent command prompts
(`commands/*.md`) into the current project — `.agent-standards/commands/`,
plus `.claude/commands/` and `.cursor/rules/` where those exist.

## Install

```bash
pip install -e .          # full CLI
./install.sh              # in your project: profile + agent command prompts
```

## Usage

```bash
cd your-repo
agent-standards init                          # creates .agent-standards/
agent-standards discover .                    # mine candidates (read-only)
agent-standards review --auto-approve         # or interactive review
agent-standards inject "add a retry wrapper for the API client"
agent-standards export . --dashboard          # standards.json + dashboard.html
agent-standards serve                         # live dashboard on :8765
agent-standards enforce .                     # exit 1 on critical regression
agent-standards score src/foo.py              # evals: changed-code consistency
```

Profiles: a base profile (`--base` or `$AGENT_STANDARDS_BASE`) plus a project
profile; project standards override base ones by id, and `sync` pushes
approved project standards back to your base profile for reuse.

## Design rules

- **Evidence over vibes** — every discovered standard carries observed counts.
- **Local-first** — zero API keys; the optional LLM pass expects a local Ollama.
- **Advisory by default, enforced only by explicit opt-in** (`critical: true`).
- **Deterministic** — same tree in, same candidates out; retrieval is stable.

## Development

```bash
pip install -e . && python -m pytest tests/ -q
```

Reference-value tests pin the discovery math to a fixture codebase with
exactly known counts, so counting-rule drift fails CI.

## License

MIT — see LICENSE.

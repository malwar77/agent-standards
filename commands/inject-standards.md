# Inject Standards

Retrieve and inject the standards relevant to the current task.

## Process

### Step 1: State the task in one sentence

Example: "add a retry wrapper around the exchange API client"

### Step 2: Retrieve

```bash
agent-standards inject "add a retry wrapper around the exchange API client"
```

- Default: top 5 relevant standards, ~800-token budget.
- Formats: markdown (default), Claude skill (`--format claude-skill`),
  Cursor rule (`--format cursor-rule`), output to file with `--output`.

### Step 3: Apply what was injected

Follow the injected standards when writing code. If a standard conflicts
with an explicit user instruction, say so and ask — the user wins.

## Constraints

- Never inject standards that were not approved (`status: approved`).
- Never pad context with irrelevant standards — retrieval precision is
  the whole point. If nothing is relevant, inject nothing.
- Shell-only environments: `bin/agent-standards inject "query" N` works
  without python3 (reduced retrieval quality, same idea).

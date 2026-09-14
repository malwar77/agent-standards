# Discover Standards

Mine this codebase's implicit conventions into evidence-backed standards.

## Process

### Step 1: Run the discovery CLI

```bash
bin/agent-standards discover .            # from the repo root, or:
agent-standards discover .                # if installed via pip
```

This is deterministic AST mining — no guessing. Read the output:
- *strong* candidates: observed >= 5 times, followed >= 70% consistently
- *weak* candidates: real pattern, but inconsistently followed

### Step 2: Present the evidence to the human

For each candidate, show:
- the standard id and title
- the evidence: `followed/observed (N% consistent)`
- 2-3 sample files that follow it, and any that violate it

Do NOT invent standards the miners did not find, and never fabricate
evidence numbers — quote them from the CLI output exactly.

### Step 3: Approve or reject

```bash
agent-standards review --auto-approve --threshold 0.9   # or interactive
```

Approval decisions belong to the human. You may recommend, they confirm.

## Constraints

- Discovery is read-only: it never modifies the codebase.
- Standards without evidence are opinions, not standards. Say so.
- If the codebase is too small (< 5 observations), say there is not
  enough evidence yet instead of guessing.

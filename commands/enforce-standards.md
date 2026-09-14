# Enforce Standards

Hard gate for standards marked `critical: true`.

## Usage

```bash
agent-standards enforce .                      # local check
agent-standards enforce . --tolerance 0.05     # allow small drift
```

- Re-runs the deterministic miner for each critical approved standard.
- Fails (exit 1) if current consistency dropped below the recorded
  consistency minus tolerance.
- Advisory standards are never enforced — only explicit opt-in.

## CI wiring (pre-commit / GitHub Actions)

```yaml
- name: standards gate
  run: agent-standards enforce . --tolerance 0.0
```

## Constraints

- Enforcement never auto-fixes code. It only reports.
- If a check fails legitimately (the convention is intentionally
  changing), the human updates or retires the standard — not the gate.

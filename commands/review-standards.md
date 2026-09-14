# Review Standards

Human-in-the-loop approval of discovered standards.

## Process

```bash
agent-standards list                  # see approved + candidates
agent-standards review                # interactive approve/reject
agent-standards review --auto-approve --threshold 0.9
```

For every candidate shown, quote the evidence exactly
(`followed/observed, N% consistent`). A standard is a claim about this
codebase; the evidence either supports it or it does not.

## When to mark a standard `critical: true`

Only when violating it breaks builds, tests, or safety. Critical
standards are enforced by CI (`agent-standards enforce`) — a consistency
regression fails the build. Everything else stays advisory.

Edit the YAML file (`.agent-standards/standards/<id>.yaml`) to set
`critical: true` and keep `status: approved`.

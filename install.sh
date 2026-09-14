#!/usr/bin/env bash
# agent-standards project installer (Agent-OS-style).
# Copies the agent command prompts into the current project and creates
# the project profile. Safe to re-run.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$(pwd)"
PROFILE="$DEST/.agent-standards"
CMD_DEST="$PROFILE/commands"

mkdir -p "$PROFILE/standards" "$CMD_DEST"

for f in "$SRC"/commands/*.md; do
  cp "$f" "$CMD_DEST/"
done

# Claude Code users: expose as project slash commands too
if [ -d "$DEST/.claude" ] || [ "${AGENT_STANDARDS_CLAUDE:-0}" = "1" ]; then
  mkdir -p "$DEST/.claude/commands"
  for f in "$SRC"/commands/*.md; do
    cp "$f" "$DEST/.claude/commands/$(basename "$f")"
  done
  echo "installed Claude Code commands: .claude/commands/"
fi

# Cursor users: expose as project rules
if [ -d "$DEST/.cursor" ] || [ "${AGENT_STANDARDS_CURSOR:-0}" = "1" ]; then
  mkdir -p "$DEST/.cursor/rules"
  for f in "$SRC"/commands/*.md; do
    cp "$f" "$DEST/.cursor/rules/$(basename "$f" .md).mdc"
  done
  echo "installed Cursor rules: .cursor/rules/"
fi

echo "project profile: $PROFILE"
echo "next: agent-standards discover . && agent-standards review"

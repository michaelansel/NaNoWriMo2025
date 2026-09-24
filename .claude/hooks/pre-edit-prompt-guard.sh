#!/usr/bin/env bash
# PreToolUse Edit|Write: refuse to write a prompt template that has no schema beside it.
# Deny is returned as JSON (hookSpecificOutput.permissionDecision); exit code stays 0.
set -u
input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -n "$file" ] || exit 0
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
rel="${file#"$root"/}"
case "$rel" in
  nanoif/prompts/*.md)
    name=$(basename "$rel" .md)
    [ "$name" = "README" ] && exit 0
    sibling="$root/nanoif/prompts/$name.schema.json"
    if [ ! -f "$sibling" ]; then
      jq -n --arg r "Prompt $rel has no sibling schema. Create nanoif/prompts/$name.schema.json first (see .claude/rules/prompts.md)." \
        '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
    fi
    ;;
esac
exit 0

#!/usr/bin/env bash
# PreToolUse Edit|Write for reviewer agents: allow writes only under the paths given as
# arguments (directory prefixes ending in "/" or exact files); deny everything else.
set -u
input=$(cat)
file=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
root="${CLAUDE_PROJECT_DIR:-$(pwd)}"
rel="${file#"$root"/}"
for allowed in "$@"; do
  case "$allowed" in
    */) [[ "$rel" == "$allowed"* ]] && exit 0 ;;
    *)  [[ "$rel" == "$allowed" ]] && exit 0 ;;
  esac
done
reason="This reviewer may only write: $*. '$rel' belongs to another layer; ask the developer or its owner."
jq -n --arg r "$reason" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
exit 0

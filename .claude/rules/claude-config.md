---
paths:
  - ".claude/**"
  - "CLAUDE.md"
---

# Claude Code configuration

- `CLAUDE.md` stays under 120 lines: commands, layout, conventions, hard rules, the delegation table, and where the truth lives. Procedures go in skills, path-specific guidance in `.claude/rules/`.
- Owner agents (`pm`, `architect`, `ceo`) write only their own intent layer: `tools: Read, Grep, Glob, Edit, Write` plus a PreToolUse `scope-writes.sh` hook naming exactly their paths, a `maxTurns`, and a `description` that says when to use them proactively. They answer in a fixed order with the verdict first. Never give an agent write access outside its layer, and never give code-writing tools to an owner agent's scope.
- Skills a human runs on purpose (`nov1-checklist`, `new-year-reset`) set `disable-model-invocation: true`. Skills that only inform Claude (`documentation-philosophy`) set `user-invocable: false`.
- Use only the frontmatter fields the current docs list: skills `name`, `description`, `disable-model-invocation`, `user-invocable`, `allowed-tools`, `context`, `agent`, `paths`, `arguments`; agents `name`, `description`, `tools`, `disallowedTools`, `model`, `permissionMode`, `maxTurns`, `skills`, `hooks`, `memory`, `effort`, `isolation`, `omitClaudeMd`.
- Hooks live in `.claude/settings.json` and call scripts in `.claude/hooks/`. A hook whose tool is missing prints a visible "skipped" line and exits 0; it never fails silently and never hides a real failure.
- `permissions.deny` protects writer prose, generated files, and `dist/`; `ask` guards paid inference and pushes. Do not loosen these for convenience.
- No template placeholders (`[User's request]`, `{TODO}`) anywhere in `.claude/`.
- Retire what is unused: a skill or agent nobody has invoked in a season is deleted in `new-year-reset`, not kept "just in case".
- Changing an agent or this directory is a tier 0 change, but say in the PR what behavior it alters.

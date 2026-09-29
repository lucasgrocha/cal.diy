# PR Auto-Approve Policy

When asked to approve a PR by link (e.g. "approve https://github.com/.../pull/123"), Claude Code may run
`gh pr review --approve` **without asking for confirmation first**, but only when the control below passes.

The policy itself (scope, rule, and the deny-list of code file extensions) is defined in
`.claude/policies/pr-auto-approve.json` — that file is the source of truth, not this doc.

Enforcement is automated, not left to judgment: a `PreToolUse` hook
(`.claude/scripts/check-pr-approve.sh`, wired in `.claude/settings.json`) intercepts every
`gh pr review --approve` command, fetches the PR's changed files via `gh pr diff --name-only`, and
classifies them against `.claude/policies/pr-auto-approve.json`'s `codeExtensions` list. If any changed file
matches, the hook denies the tool call with a reason explaining which files disqualified it; only when
every changed file is non-code does the hook allow the approval to proceed.

The `permissions.allow` rule for `Bash(gh pr review --approve*)` only avoids the manual confirmation
prompt — the hook is the actual enforcement layer and runs regardless.

The `pr-auto-approve-check` skill (`.claude/skills/pr-auto-approve-check/SKILL.md`) runs the same control
explicitly and prints the evidence (changed files + verdict) before acting, for auditable one-off checks.

This is scoped to this repository only (`cal.diy`). `.claude/settings.json`,
`.claude/scripts/check-pr-approve.sh`, and `.claude/policies/pr-auto-approve.json` are all committed, so
this policy applies to anyone using Claude Code in this repo, not just the repo owner.

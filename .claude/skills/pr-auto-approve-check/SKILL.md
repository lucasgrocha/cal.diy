---
name: pr-auto-approve-check
description: Evaluates a PR against the repo's PR auto-approve policy (text-only diffs only, see CLAUDE.md), collects evidence (changed files, classification verdict), and executes the control — approving the PR via `gh pr review --approve` if it passes, or reporting why it was blocked if it doesn't. Use when asked to "check if this PR can be auto-approved," "run the auto-approve check on PR #N," or "approve this PR" as an explicit, evidence-producing action rather than relying on the PreToolUse hook firing implicitly.
---

# PR Auto-Approve Check

Runs the same text-only-diff control defined in `CLAUDE.md`'s "PR Auto-Approve Policy" section and enforced
by `.claude/scripts/check-pr-approve.sh`, but as an explicit, evidence-producing step — not a side effect of
another command.

## Step 1 — Identify the PR

Take the PR number or link from the request (e.g. `#12`, `https://github.com/.../pull/12`). If ambiguous,
ask which PR.

## Step 2 — Collect evidence

Run the control script directly and capture its full output — this is the evidence:

```bash
echo "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"gh pr review --approve <pr>\"}}" \
  | .claude/scripts/check-pr-approve.sh
```

This prints a JSON object with `permissionDecision` (`allow` or `deny`) and `permissionDecisionReason`,
which lists the exact changed files and, on `deny`, which of them are code-logic files that disqualified
the PR. Show this evidence to the user verbatim — don't summarize away the file list.

## Step 3 — Execute the control

- If `permissionDecision` is `allow`: run `gh pr review --approve <pr>` to actually approve it, then confirm
  to the user that it was approved and why (text-only diff, per the evidence).
- If `permissionDecision` is `deny`: do **not** approve. Report the reason to the user and stop — this PR
  needs manual review.

Never approve a PR without first producing and showing the Step 2 evidence, even if the control's hook
would also catch a bad approval — this skill's job is to make the decision auditable, not just enforced.

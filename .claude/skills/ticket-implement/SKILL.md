---
name: ticket-implement
description: Third and final stage of the ticket-to-PR pipeline. Takes an approved plan produced by ticket-plan, implements it, runs tests/lint, opens a PR, and reports back — all autonomously, with no further check-ins. Invoke with the path to an approved plan as args (e.g. ".claude/tickets/<slug>/plan.md"). Don't invoke this directly unless the plan was already approved by the developer — if there's no approved plan yet, run ticket-research then ticket-plan first.
---

# Ticket Implement

Stage 3 of 3 in the ticket-to-PR pipeline: research → plan → **implement**. By the time this stage runs, the developer has already approved the plan — everything here runs autonomously without pausing for permission at each step.

## Step 0 — Read the approved plan

Read the plan at the path given in args, and confirm it has an `## Approved` note. If it doesn't look approved, stop and go back to `ticket-plan` rather than building on an unconfirmed plan.

## Step 1 — Build

1. Implement the change, following the patterns identified during research.
2. Run the project's actual test and lint commands (from the research brief — never invent or guess these).
3. **If something fails**: try to fix it yourself first. Read the actual error, not just the exit code, and make a genuine attempt at a root-cause fix — a couple of honest attempts, not one token retry. Only stop and ask the developer if you're genuinely stuck (the failure is ambiguous, or fixing it would mean deviating from the approved plan in a way that changes scope).

## Step 2 — Branch, commit, push, PR

4. Create a branch named `type/short-slug` (e.g. `feat/add-phone-validation`, `fix/booking-timezone-bug`) — infer `type` the way conventional commits do (feat/fix/chore/refactor/docs) from what the change actually is.
5. Commit with a message matching the style observed during research.
6. Push the branch and open the PR with `gh pr create`. Use this description shape:

```markdown
## Summary
<1-3 bullets: what changed and why — the "why" matters more than restating the diff>

## Screenshots / demo
<if this is a UI-visible change, note here that a screenshot/recording should be added; otherwise omit this section entirely>
```

Match whatever attribution footer convention is already active in this session, if one applies.

## Step 3 — Report back

Give the developer the PR link and a one-line summary of what shipped. If you had to self-heal any failures along the way, mention what broke and how you fixed it — that's useful signal even though it didn't need their intervention in the moment.

## Guardrails

- Never push or open a PR before confirming the plan was approved (Step 0) — that's the one non-negotiable gate in this stage.
- Never invent test/lint/build commands — if the plan/research didn't turn up a clear one, ask rather than guess, since running the wrong command can give false confidence.
- If mid-build you discover the approved plan doesn't work (an assumption was wrong, a dependency doesn't support something), stop and go back to the developer rather than silently improvising a different approach — that's a plan change, not an implementation detail.

---
name: ticket-research
description: First stage of the ticket-to-PR pipeline. Takes a task description or GitHub issue, restates it, and does a lightweight scan of the project's existing patterns, conventions, and test/lint commands. Produces a research brief and hands off to ticket-plan. Use whenever the user wants to "implement this ticket," "build this feature," "fix this issue and open a PR," pastes a GitHub issue link/number and wants it worked, or describes a task and asks you to take it end-to-end to a PR — even if they don't say "skill" or "workflow." This is the entry point for that whole pipeline; don't invoke ticket-plan or ticket-implement directly unless resuming a pipeline already in progress.
---

# Ticket Research

Stage 1 of 3 in the ticket-to-PR pipeline: **research → plan → implement**. This stage only gathers context — it never proposes a plan, never asks the developer questions, and never touches code. Its job is to produce a research brief that `ticket-plan` can build a plan from.

## Step 1 — Get the task

The task can arrive as:
- **Freeform text**: the developer just describes what they want in chat.
- **A GitHub issue**: a link or `#123`-style reference. Fetch it with `gh issue view <number> --json title,body,comments,labels` (or paste the URL directly to `gh issue view <url>`). Read the comments too — clarifications and scope changes often live there, not in the original body.

Restate the task in your own words in the brief — don't let an ambiguous restatement silently carry through to the plan.

## Step 2 — Read the room (lightweight pattern scan)

Spend a few minutes understanding how this project already does things like this. You're not doing a full architecture review — just enough that the plan stage can make something that fits in without a reviewer flagging "this isn't how we do it here." Look for:

- **Similar existing code**: grep for features/components/endpoints that resemble what's being built. If something adjacent already exists, note its shape (file layout, naming, error handling, test structure).
- **Conventions docs**: `CLAUDE.md`, `CONTRIBUTING.md`, or similar, if present.
- **Test and lint commands**: check `package.json` scripts, `Makefile`, or CI config so later stages know what "passing" means — don't guess or invent commands.
- **Commit and PR style**: `git log --oneline -20` for message conventions, and recent merged PRs (`gh pr list --state merged --limit 5`) for description style, if `gh` is available and the repo has a remote.

Keep this fast. If the task is small and an obvious pattern already exists, a couple of greps is enough — don't burn time surveying the whole codebase for a one-line fix.

## Step 3 — Write the research brief

Create `.claude/tickets/<slug>/research.md` (slug: short kebab-case from the task, e.g. `add-phone-validation`). Include:

```markdown
# Research: <task title>

## Task (as understood)
<restated task, plus the original source — pasted text or issue link/number>

## Similar existing code
<files/patterns found, with paths>

## Conventions
<relevant notes from CLAUDE.md/CONTRIBUTING.md, if any>

## Test & lint commands
<exact commands, e.g. `pnpm test`, `pnpm lint` — never invented>

## Commit / PR style
<observed conventions>

## Open questions
<anything genuinely ambiguous that the plan stage should resolve with the developer — don't answer these yourself>
```

`.claude/tickets/` is gitignored — this is a scratch artifact for the pipeline, not project documentation.

## Step 4 — Hand off to ticket-plan

Once the brief is written, invoke the `ticket-plan` skill, passing the brief's path as args, e.g.:

`Skill(skill: "ticket-plan", args: ".claude/tickets/add-phone-validation/research.md")`

Don't summarize or re-derive the plan yourself here — that's the next stage's job.

## Guardrails

- Never invent test/lint/build commands — if you can't find a clear one, say so in "Open questions" rather than guessing.
- Don't ask the developer questions at this stage — capture ambiguity in the brief and let `ticket-plan` interview them.
- Don't start writing code or a plan — this stage is research only.

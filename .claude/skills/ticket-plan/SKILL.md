---
name: ticket-plan
description: Second stage of the ticket-to-PR pipeline. Takes a research brief produced by ticket-research, interviews the developer about anything genuinely ambiguous, writes an implementation plan, and gets explicit approval before handing off to ticket-implement. Invoke with the path to a research brief as args (e.g. ".claude/tickets/<slug>/research.md"). Don't invoke this directly for a fresh task — run ticket-research first unless the user explicitly asks to resume planning from an existing brief.
---

# Ticket Plan

Stage 2 of 3 in the ticket-to-PR pipeline: research → **plan** → implement. This stage turns a research brief into an approved plan. Nothing here touches code, and nothing after the approval gate in this stage should run without the developer's explicit sign-off.

## Why this stage matters

Wrong assumptions compound: a plan built on a misunderstood requirement produces a PR that's wrong in a way that's expensive to unwind. Get the plan right here and the implement stage can move fast without hand-holding.

## Step 1 — Read the research brief

Read the brief at the path given in args. It contains the restated task, patterns found, conventions, test/lint commands, and an "Open questions" section flagging genuine ambiguity. If no path was given, ask the developer for one or run `ticket-research` first.

## Step 2 — Interview, but only about what's actually unclear

Don't run a fixed checklist. The brief's "Open questions" section is your starting point, but re-check it against the task yourself too. Ask only about things that are genuinely ambiguous or that materially change the implementation, for example:

- Scope boundaries the ticket doesn't state ("should this apply to the mobile app too, or just web?")
- A design decision with real tradeoffs (e.g. schema change vs. computed value)
- Edge cases the ticket is silent on (what happens on empty input, concurrent access, existing data)
- Anything where the codebase shows two competing patterns and it's not obvious which one applies here

If nothing is ambiguous, say what you inferred and move straight to the plan — asking questions you can already answer from the brief just slows the developer down and reads as not having done the reading.

## Step 3 — Write the plan and get explicit approval

Use `EnterPlanMode` / `ExitPlanMode` for this if you're in an environment that supports it — it's built for exactly this handoff. The plan should cover:

- What you understood the task to be (so a misunderstanding surfaces here, not in the PR)
- The files/areas you'll touch and why, referencing the patterns found in the research brief
- Anything you inferred rather than asked about, called out explicitly so the developer can correct it
- How you'll verify it works (which tests, which manual check if it's UI)

**Do not proceed until the developer approves.** Everything after this runs without further check-ins, so this is the last easy point to redirect.

## Step 4 — Save the plan and hand off to ticket-implement

Once approved, write the plan to `.claude/tickets/<slug>/plan.md` (same slug/directory as the research brief) alongside a `## Approved` note confirming sign-off. Then invoke the `ticket-implement` skill, passing the plan's path as args, e.g.:

`Skill(skill: "ticket-implement", args: ".claude/tickets/add-phone-validation/plan.md")`

## Guardrails

- Never hand off to `ticket-implement` before the developer has explicitly approved the plan — that's the one non-negotiable gate in this pipeline.
- Never invent test/lint/build commands — carry forward exactly what the research brief found; if it found none, ask rather than guess.
- If the research brief looks thin or stale (e.g. it's missing test commands entirely), it's fine to do a quick supplementary check yourself, but don't redo the full research stage.

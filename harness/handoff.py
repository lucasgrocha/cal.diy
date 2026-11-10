"""Handoff from the workflow to an interactive session, and back through the issue.

Usage: python -m harness.handoff <issue>   (needs GITHUB_TOKEN or a logged-in `gh`)
Prints the saved context; pipe it to `claude` to discuss the pending decision.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from harness.responses import ACCEPTED

DECISIONS = {
    "needs_information": "Answer the questions in the issue.",
    "awaiting_design_selection": "Comment `/option <1-3>` or `/revise <changes>`.",
    "awaiting_approval": "Comment `/approve plan <fingerprint>` or `/revise <changes>`.",
    "awaiting_code_review": "Comment `/approve merge <sha>` or ask for changes.",
    "manual_change_required": "Comment `/revise <changes>` to replan within the allowed scope.",
    "failed": "Fix the cause and comment `/resume`.",
    "stale": "Comment `/resume` to replan on the current version.",
    "deploy_failed": "Decide whether to revert the merge.",
}


def brief(number, state):
    status = state["status"]
    pending = DECISIONS.get(status, "No pending decision.")
    evidence = {k: state[k] for k in ("pm", "research", "design_need", "evaluation", "check_evidence", "test_review",
                                      "code_evals", "review", "code_gate", "error") if state.get(k)}
    plan = state.get("plan") or {}
    return "\n".join([
        f"# Issue handoff #{number}: {state['issue']['title']}",
        "", "## Goal", "", state["issue"]["body"] or "(no description)",
        "", "## Current plan", "", json.dumps(plan, ensure_ascii=False, indent=2) if plan else "(no plan yet)",
        "", "## Evidence", "", "```json", json.dumps(evidence, ensure_ascii=False, indent=2), "```",
        "", f"## Pending decision (state `{status}`)", "", pending,
        "", "After the discussion, record the decision in the issue with the command above; the workflow rechecks the gates when it resumes.",
        f"Commands accepted now: {', '.join(sorted(a for a, states in ACCEPTED.items() if status in states))}.",
    ])


def main():
    from harness.github import GitHub
    number = int(sys.argv[1])
    config = json.loads((Path(__file__).parent / "config.json").read_text())
    token = os.environ.get("GITHUB_TOKEN") or subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    state, _ = GitHub(config["repository"], token).load_state(number)
    if not state:
        sys.exit(f"Issue #{number} has no harness state.")
    print(brief(number, state))


if __name__ == "__main__":
    main()

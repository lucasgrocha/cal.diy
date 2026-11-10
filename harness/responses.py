"""Human decisions are explicit issue commands bound to the version they decide on."""
from __future__ import annotations

import re

from harness.policy import GateError

COMMANDS = [
    ("approve_plan", re.compile(r"^/approve\s+plan\s+([0-9a-f]{7,64})\b", re.I)),
    ("approve_merge", re.compile(r"^/approve\s+merge\s+([0-9a-f]{7,40})\b", re.I)),
    ("select_design", re.compile(r"^/option\s+([1-3])\b", re.I)),
    ("revise", re.compile(r"^/revise\s+(\S.*)", re.I | re.S)),
    ("handoff", re.compile(r"^/handoff\b", re.I)),
    ("resume", re.compile(r"^/resume\b", re.I)),
]
# Where each decision is accepted.
ACCEPTED = {
    "approve_plan": {"awaiting_approval"},
    "approve_merge": {"awaiting_code_review"},
    "select_design": {"awaiting_design_selection"},
    "revise": {"awaiting_approval", "awaiting_design_selection", "manual_change_required"},
    "handoff": {"needs_information", "awaiting_design_selection", "awaiting_approval", "awaiting_code_review",
                "manual_change_required", "failed", "stale", "deploy_failed"},
    "resume": {"failed", "stale"},
    "reply": {"needs_information"},
}


def parse(body):
    text = (body or "").strip()
    for name, pattern in COMMANDS:
        match = pattern.match(text)
        if match:
            return name, (match.group(1).strip() if match.groups() else None)
    return "reply", text


def matches(prefix, full):
    return bool(full) and len(prefix) >= 7 and full.startswith(prefix.lower())


def resolve(state, body):
    """(action, argument) for a comment, or None when the comment decides nothing now."""
    action, argument = parse(body)
    if not state or state["status"] not in ACCEPTED[action]:
        return None
    if action == "approve_plan" and not matches(argument, state.get("plan_fingerprint")):
        raise GateError("The approval does not match the pending plan.")
    if action == "approve_merge" and not matches(argument, state.get("head_sha")):
        raise GateError("The approval does not match the evaluated commit.")
    return action, argument

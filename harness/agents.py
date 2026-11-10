"""Trusted role routing and one bounded human report format for all agents."""
from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re

MAX_SUMMARY_WORDS = 80
TARGET_SUMMARY_WORDS = 35


@dataclass(frozen=True)
class Agent:
    role: str
    name: str
    definition: str  # .claude/agents/<definition>.md: role prompt and tools
    responsibility: str


AGENTS = {
    "pm": Agent("pm", "🤖 PM", "pm", "Coordinate delivery, clarify decisions and delegate; the gates stay in the controller."),
    "design": Agent("design", "🤖 Designer", "designer", "Create mockup alternatives for a human to choose from and guide the implementation."),
    "planning": Agent("planning", "🤖 Planner", "planner", "Research, plan and evaluate the plan; never implement."),
    "implementation": Agent("implementation", "🤖 Implementer", "implementer", "Implement or fix only the approved plan; never review or merge."),
    "test": Agent("test", "🤖 Tester", "tester", "Check criteria, coverage and the real CI evidence of the commit; never fabricate results."),
    "review": Agent("review", "🤖 Reviewer", "reviewer", "Independently review the diff, the plan and the commit's evidence; never change files."),
    "deploy": Agent("deploy", "🤖 Deployer", "deployer", "Verify the real evidence of the merged version; the controller keeps credentials and the merge."),
}
STAGE_ROLES = {
    "pm": "pm", "design_need": "pm", "design": "design",
    **dict.fromkeys(("entry", "research", "plan", "evaluate"), "planning"),
    **dict.fromkeys(("implement", "repair"), "implementation"),
    "test": "test",
    **dict.fromkeys(("code_evals", "review", "review_gate"), "review"),
    **dict.fromkeys(("merge", "deploy"), "deploy"),
}


def agent_for_stage(stage):
    return AGENTS[STAGE_ROLES[stage]]


def trusted_context(stage):
    """Role identity comes from trusted routing, never from issue/model input."""
    agent = agent_for_stage(stage)
    return {"role": agent.role, "name": agent.name, "responsibility": agent.responsibility, "stage": stage,
            "communication": "Write in English. `summary` is one or two sentences, at most 35 words, with the decision and the "
                             "next step. Short questions, one decision per question. No JSON, logs or hashes in the summary; "
                             "details go in the structured fields."}


def _bounded(text, limit):
    words = list(re.finditer(r"\S+", text))
    if len(words) <= limit:
        return text, False
    return text[:words[max(0, limit) - 1].end()] if limit else "", True


def _plain(text):
    # A model's unclosed Markdown fence must not swallow what follows; flattening
    # whitespace also prevents indented or nested block constructs.
    return escape(" ".join(str(text).split()), quote=False).translate({
        ord("\\"): "&#92;", ord("`"): "&#96;", ord("~"): "&#126;"})


def render_report(role, summary, *, decision=None, questions=None, details=None):
    """Human communication only; the controller stores full evidence separately."""
    decision_text = str(decision or "")
    if len(re.findall(r"\S+", decision_text)) > 60:
        raise ValueError("A decision must fit in 60 words; store evidence separately")
    concise, clipped = _bounded(str(summary), TARGET_SUMMARY_WORDS)
    sentences = re.split(r"(?<=[.!?])\s+", concise.strip())
    concise = " ".join(sentences[:2])
    if clipped and len(sentences) <= 2:
        complete = re.search(r"^(.+[.!?])(?:\s+[^.!?]*)?$", concise)
        concise = complete.group(1) if complete else concise.rstrip(".,;:") + "…"
    visible = f"**{AGENTS[role].name}**\n\n" + _plain(concise)
    if questions:
        # Decisions stay complete: never clip a question midway.
        visible += "\n\n" + "\n".join(f"{i}. {_plain(q)}" for i, q in enumerate(questions[:3], 1))
    if decision_text:
        visible += "\n\n" + decision_text
    if details:
        visible += f"\n\n<details><summary>Details</summary>\n\n{details}\n\n</details>"
    return visible

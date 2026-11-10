"""Output contract and instructions of every agent stage. The controller validates each result."""
from __future__ import annotations


def _obj(required_fields, **properties):
    return {"type": "object", "additionalProperties": False, "required": list(required_fields), "properties": properties}


STR = {"type": "string"}
TEXT = {"type": "string", "minLength": 1}
STRS = {"type": "array", "items": TEXT}
SCORE = {"type": "number", "minimum": 0, "maximum": 1}
RISK = {"type": "string", "enum": ["low", "medium", "high"]}
SHA = {"type": "string", "pattern": "^[0-9a-f]{40}$"}
QUESTIONS = {"type": "array", "items": TEXT, "maxItems": 3}

STAGES = {
    "pm": {
        "instructions": "Assess the issue as the PM: the problem, who is affected, what is in and out of scope, and verifiable acceptance criteria. Read the code only to understand current behavior. Classify the scope (screen = new screen; ui_change = change to an existing screen). Ask only what changes what will be built and cannot be inferred.",
        "schema": _obj(["summary", "scope_type", "complexity", "requires_plan_approval", "acceptance_criteria", "questions"],
                       summary=TEXT, scope_type={"enum": ["screen", "ui_change", "backend", "other"]},
                       complexity={"enum": ["simple", "complex"]}, requires_plan_approval={"type": "boolean"},
                       acceptance_criteria=STRS, questions=QUESTIONS),
    },
    "research": {
        "instructions": "Research the code for the PM's decision: similar files and patterns, conventions and the exact test commands. For a bug, investigate the likely cause. Do not propose the plan.",
        "schema": _obj(["summary", "kind", "relevant_files", "patterns", "test_commands"],
                       summary=TEXT, kind={"enum": ["bug", "feature", "chore"]}, relevant_files=STRS,
                       patterns=STRS, test_commands=STRS),
    },
    "design_need": {
        "instructions": "Decide whether the change needs design before the plan. A new screen always does. Changes that reuse the existing interface do not. If it does, write the Designer's brief.",
        "schema": _obj(["summary", "needed", "confidence", "design_brief"],
                       summary=TEXT, needed={"type": "boolean"}, confidence=SCORE, design_brief=STR),
    },
    "design": {
        "instructions": "Create three distinct design options for the brief, using packages/ui components and existing patterns. Each mockup is a text (ASCII) sketch with the main states. Recommend one option.",
        "schema": _obj(["summary", "recommended_option", "options"],
                       summary=TEXT, recommended_option={"type": "integer", "minimum": 1, "maximum": 3},
                       options={"type": "array", "minItems": 3, "maxItems": 3, "items": _obj(
                           ["id", "title", "summary", "mockup"], id={"type": "integer", "minimum": 1, "maximum": 3},
                           title=TEXT, summary=TEXT, mockup=TEXT)}),
    },
    "plan": {
        "instructions": "Write the implementation plan from the issue, the PM's decision, the research and the chosen design, if any. List every file that will change, the tests and the acceptance criteria. Respect `scope`. If there is `evaluation_feedback` or `owner_feedback`, fix the plan accordingly.",
        "schema": _obj(["summary", "files", "tests", "acceptance_criteria", "steps", "risk", "open_questions"],
                       summary=TEXT, files={"type": "array", "minItems": 1, "items": TEXT},
                       tests={"type": "array", "items": _obj(["path", "kind", "purpose"], path=TEXT,
                                                              kind={"enum": ["new_test", "existing_test"]}, purpose=TEXT)},
                       acceptance_criteria={"type": "array", "minItems": 1, "items": TEXT}, steps=STRS, risk=RISK,
                       open_questions=QUESTIONS),
    },
    "evaluate": {
        "instructions": "Evaluate the plan's adherence to the request (issue and PM decision) and to the chosen design. Check that each of the PM's acceptance criteria is covered by a test. Do not rewrite the plan.",
        "schema": _obj(["summary", "aligned", "score", "risk", "requires_human", "missing_acceptance_criteria", "findings"],
                       summary=TEXT, aligned={"type": "boolean"}, score=SCORE, risk=RISK,
                       requires_human={"type": "boolean"}, missing_acceptance_criteria=STRS, findings=STRS),
    },
    "implement": {
        "instructions": "Implement the approved plan, changing only `plan.files`. Run the plan's test commands. Do not commit: the controller validates and publishes the diff. If there are `failed_checks` or `test_findings`, fix exactly those failures without changing the plan.",
        "schema": _obj(["summary", "files", "verification"], summary=TEXT, files=STRS, verification=STRS),
    },
    "test": {
        "instructions": "Check each acceptance criterion against the diff and the real CI evidence of commit `head_sha` (commands, exit codes, output). Assess whether a test covers each criterion. Do not invent results; a gap is a finding.",
        "schema": _obj(["summary", "head_sha", "passed", "coverage", "findings"],
                       summary=TEXT, head_sha=SHA, passed={"type": "boolean"},
                       coverage={"type": "array", "items": _obj(["criterion", "covered", "evidence"], criterion=TEXT,
                                                                covered={"type": "boolean"}, evidence=TEXT)},
                       findings=STRS),
    },
    "code_evals": {
        "instructions": "Evaluate the diff of commit `head_sha` on three independent axes: complexity of the change, adherence to the approved plan, and code style relative to neighboring patterns. Recommend human review when there is risk.",
        "schema": _obj(["summary", "head_sha", "complexity", "plan_adherence", "style", "human_review"],
                       summary=TEXT, head_sha=SHA,
                       complexity=_obj(["level", "reasons"], level={"enum": ["low", "medium", "high"]}, reasons=STRS),
                       plan_adherence=_obj(["passed", "score", "findings"], passed={"type": "boolean"}, score=SCORE, findings=STRS),
                       style=_obj(["passed", "findings"], passed={"type": "boolean"}, findings=STRS),
                       human_review=_obj(["required", "reasons"], required={"type": "boolean"}, reasons=STRS)),
    },
    "review": {
        "instructions": "Independently review the diff of commit `head_sha` against the issue, the plan and the evidence: bugs, edge cases, security (authorization, validation, data exposure) and fit with existing patterns. List only what must change before the merge.",
        "schema": _obj(["summary", "head_sha", "aligned", "score", "risk", "findings"],
                       summary=TEXT, head_sha=SHA, aligned={"type": "boolean"}, score=SCORE, risk=RISK, findings=STRS),
    },
    "deploy": {
        "instructions": "Evaluate the merged version `merge_sha`: main's CI evidence, the acceptance criteria and what the delivery requires (migrations, environment variables, flags). Say whether the delivery is complete or must be reverted.",
        "schema": _obj(["summary", "merge_sha", "passed", "findings"], summary=TEXT, merge_sha=SHA,
                       passed={"type": "boolean"}, findings=STRS),
    },
}
STAGES["repair"] = STAGES["implement"]

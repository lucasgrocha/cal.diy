"""The diagram's paths, end to end, against a fake GitHub, CI and agents."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import harness.workflow as wf
from harness.claude import command, definition
from harness.controller import Controller
from harness.policy import GateError, safe_path
from harness.responses import parse

CONFIG = json.loads((Path(wf.__file__).parent / "config.json").read_text())
AGENTS_DIR = Path(wf.__file__).parents[1] / ".claude/agents"
BASE, HEAD1, HEAD2, MERGE = "a" * 40, "b" * 40, "c" * 40, "d" * 40
OWNER = "owner"


class FakeGitHub:
    def __init__(self):
        self.state, self.blob, self.comments, self.labels = None, None, [], []
        self.heads = {"main": BASE}
        self.body = "Show the duration on the booking page."
        self.heads_queue, self.merged, self.budget = [HEAD1, HEAD2, "e" * 40, "f" * 40], False, 0
        self.pr_files = [{"filename": "apps/web/x.tsx", "additions": 3, "deletions": 1}]

    def load_state(self, number):
        return copy.deepcopy(self.state), self.blob

    def save_state(self, number, state, blob):
        assert blob == self.blob, "stale write"
        self.state, self.blob = copy.deepcopy(state), f"blob{len(self.comments)}-{state['status']}"
        return self.blob

    def set_status_label(self, number, status):
        self.labels.append(status)

    def issue(self, number, clarification_ids=()):
        return {"number": number, "title": "Duration", "body": self.body + "".join(f"\n{i}" for i in clarification_ids),
                "labels": [{"name": "prioritized"}], "state": "open"}

    def can_write(self, login):
        return login == OWNER

    def comment(self, number, body):
        self.comments.append((number, body))
        return {"id": len(self.comments)}

    def head(self, branch):
        return self.heads.get(branch, BASE)

    def record_budget(self, reservation, config):
        self.budget += reservation["usd"]

    def publish_patch(self, number, base_sha, files, *, branch):
        self.heads[branch] = self.heads_queue.pop(0)
        return self.heads[branch]

    def open_pr(self, branch, base, title, body):
        return {"number": 99, "html_url": "https://pr/99"}

    def all(self, path):
        return self.pr_files

    def repo_api(self, method, path, data=None):
        assert path == "pulls/99"
        return {"head": {"sha": self.state["head_sha"]}, "state": "open", "title": "feat: Duration"}

    def checks(self, head):
        return [{"name": "Harness / verify", "head_sha": head, "app": {"slug": "github-actions"},
                 "status": "completed", "conclusion": "success", "id": 1}]

    def merge_pr(self, number, head_sha, title):
        self.merged = True
        self.heads["main"] = MERGE
        return {"sha": MERGE}


def result(stage, **overrides):
    defaults = {
        "pm": {"summary": "Show duration.", "scope_type": "ui_change", "complexity": "simple",
               "requires_plan_approval": False, "acceptance_criteria": ["Shows 30m"], "questions": []},
        "research": {"summary": "Duration.tsx renders it.", "kind": "feature", "relevant_files": ["apps/web/x.tsx"],
                     "patterns": [], "test_commands": ["TZ=UTC yarn vitest run apps/web/x.test.tsx"]},
        "design_need": {"summary": "No design.", "needed": False, "confidence": 0.95, "design_brief": ""},
        "design": {"summary": "Three options.", "recommended_option": 2,
                   "options": [{"id": i, "title": f"T{i}", "summary": "s", "mockup": "[ ]"} for i in (1, 2, 3)]},
        "plan": {"summary": "Change x.tsx.", "files": ["apps/web/x.tsx"],
                 "tests": [{"path": "apps/web/x.test.tsx", "kind": "new_test", "purpose": "covers"}],
                 "acceptance_criteria": ["Shows 30m"], "steps": ["edit"], "risk": "low", "open_questions": []},
        "evaluate": {"summary": "Aligned.", "aligned": True, "score": 0.9, "risk": "low", "requires_human": False,
                     "missing_acceptance_criteria": [], "findings": []},
        "implement": {"summary": "Done.", "files": ["apps/web/x.tsx"], "verification": ["vitest ok"]},
        "test": {"summary": "Criteria covered.", "passed": True, "coverage": [], "findings": []},
        "code_evals": {"summary": "Ok.", "complexity": {"level": "low", "reasons": []},
                       "plan_adherence": {"passed": True, "score": 0.95, "findings": []},
                       "style": {"passed": True, "findings": []}, "human_review": {"required": False, "reasons": []}},
        "review": {"summary": "Approved.", "aligned": True, "score": 0.9, "risk": "low", "findings": []},
        "deploy": {"summary": "Main CI is green.", "passed": True, "findings": []},
    }
    defaults["repair"] = defaults["implement"]
    return {**defaults[stage], **overrides}


class Script:
    """Scripted agent results and changed files, consumed in order."""
    def __init__(self):
        self.results, self.files, self.calls = {}, [[{"path": "apps/web/x.tsx", "content": "x", "mode": "100644",
                                                       "additions": 3, "deletions": 1}]], []

    def runner(self, config, sha):
        script = self

        class FakeRunner:
            def __init__(self):
                self.sha = sha

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def stage(self, name, context):
                script.calls.append(name)
                queue = script.results.get(name)
                value = queue.pop(0) if queue else result(name)
                if "head_sha" in context and name in {"test", "code_evals", "review"}:
                    value = {"head_sha": context["head_sha"], **value}
                if name == "deploy":
                    value = {"merge_sha": context["merge_sha"], **value}
                return {"result": value, "usage": {}, "denied_tools": []}

            def files(self):
                return script.files[0] if len(script.files) == 1 else script.files.pop(0)

            def diff(self, base_sha):
                return "diff"

        return FakeRunner()


@pytest.fixture
def env(monkeypatch):
    gh, script, ci, profiles = FakeGitHub(), Script(), [], []

    def fake_ci(github, ref, head, base, *, profile, timeout):
        profiles.append(profile)
        passed = ci.pop(0) if ci else True
        return {"head_sha": head, "passed": passed, "checks": [{"name": "tests", "exit_code": 0 if passed else 1}]}

    monkeypatch.setattr(wf, "run_ci", fake_ci)
    workflow = wf.Workflow(Controller(CONFIG, gh, runner=script.runner))
    workflow.ci_profiles = profiles
    return gh, script, ci, workflow


def start(workflow):
    event = {"repository": {"full_name": CONFIG["repository"]}, "sender": {"login": OWNER},
             "issue": {"number": 7}, "action": "labeled", "label": {"name": "prioritized"}}
    return workflow.init("issues", event)["next"]


def say(workflow, body, actor=OWNER, comment_id=500):
    event = {"repository": {"full_name": CONFIG["repository"]}, "sender": {"login": actor, "type": "User"},
             "issue": {"number": 7}, "comment": {"id": comment_id, "body": body}}
    return workflow.init("issue_comment", event)["next"]


def drive(workflow, step):
    """Runs jobs like harness.yml does, until a step needs a person or the task ends."""
    path = []
    while step:
        path.append(step)
        if step == "review":  # the two review jobs run in parallel, then their gate
            workflow.run("code_evals", 7)
            workflow.run("review", 7)
            step = "review_gate"
            path.append(step)
        step = workflow.run(step, 7)["next"]
    return path


def test_simple_change_goes_to_merge_without_pauses(env):
    gh, script, _, workflow = env
    path = drive(workflow, start(workflow))
    assert path == ["pm", "research", "design_need", "plan", "implement", "test", "review", "review_gate", "merge", "deploy"]
    assert gh.state["status"] == "done" and gh.merged
    assert workflow.ci_profiles == ["fast", "full"]  # type-check only on the merged version
    assert script.calls == ["pm", "research", "design_need", "plan", "evaluate", "implement", "test",
                            "code_evals", "review", "deploy"]
    authors = {body.split("**")[1] for _, body in gh.comments}
    assert authors == {"🤖 PM", "🤖 Planner", "🤖 Implementer", "🤖 Tester", "🤖 Reviewer", "🤖 Deployer"}


def test_new_screen_needs_design_choice_and_plan_approval(env):
    gh, script, _, workflow = env
    script.results["pm"] = [result("pm", scope_type="screen")]
    assert drive(workflow, start(workflow))[-1] == "design"
    assert gh.state["status"] == "awaiting_design_selection"
    assert "/option" in gh.comments[-1][1] and "Option 2: T2" in gh.comments[-1][1]
    assert drive(workflow, say(workflow, "/option 2")) == ["plan"]
    assert gh.state["status"] == "awaiting_approval" and gh.state["selected_design"]["id"] == 2
    with pytest.raises(GateError):
        say(workflow, "/approve plan 0000000")
    assert say(workflow, "Looks good") == ""  # free text does not approve
    assert say(workflow, f"/approve plan {gh.state['plan_fingerprint'][:12]}", actor="stranger") == ""
    assert say(workflow, f"/approve plan {gh.state['plan_fingerprint'][:12]}") == "implement"


def test_pm_questions_pause_and_the_reply_restarts_planning(env):
    gh, script, _, workflow = env
    script.results["pm"] = [result("pm", questions=["Web or embed?"])]
    assert drive(workflow, start(workflow)) == ["pm"]
    assert gh.state["status"] == "needs_information" and "1. Web or embed?" in gh.comments[-1][1]
    assert say(workflow, "Web only.", comment_id=41) == "pm"
    assert gh.state["clarification_comment_ids"] == [41] and "41" in gh.state["issue"]["body"]


def test_plan_divergence_gets_one_revision(env):
    gh, script, _, workflow = env
    script.results["evaluate"] = [result("evaluate", aligned=False, score=0.4), result("evaluate")]
    drive(workflow, start(workflow))
    assert script.calls[3:7] == ["plan", "evaluate", "plan", "evaluate"]
    assert gh.state["status"] == "done"


def test_ci_failure_is_repaired_within_the_attempt_limit(env):
    gh, script, ci, workflow = env
    ci.extend([False, True])
    drive(workflow, start(workflow))
    assert "repair" in script.calls and gh.state["status"] == "done" and gh.state["attempts"] == 2


def test_ci_failures_stop_at_the_limit_and_approval_cannot_merge(env):
    gh, script, ci, workflow = env
    ci.extend([False, False, False])
    path = drive(workflow, start(workflow))
    assert path[-1] == "test" and gh.state["status"] == "failed" and not gh.merged
    assert script.calls.count("repair") == CONFIG["max_implementation_attempts"] - 1
    assert say(workflow, f"/approve merge {gh.state['head_sha']}") == ""  # not a merge decision point
    gh.state["status"] = "ready_to_merge"  # even a forged state cannot merge a failed candidate
    with pytest.raises(GateError):
        workflow.run("merge", 7)


def test_core_files_need_human_review_of_the_exact_commit(env):
    gh, script, _, workflow = env
    gh.pr_files = [{"filename": "packages/features/bookings/lib/x.ts", "additions": 1, "deletions": 1}]
    assert drive(workflow, start(workflow))[-1] == "review_gate"
    assert gh.state["status"] == "awaiting_code_review" and not gh.merged
    with pytest.raises(GateError):
        say(workflow, "/approve merge 1234567")
    assert drive(workflow, say(workflow, f"/approve merge {gh.state['head_sha'][:12]}")) == ["merge", "deploy"]
    assert gh.merged and gh.state["status"] == "done"


def test_files_outside_the_plan_block_publication(env):
    gh, script, _, workflow = env
    script.files = [[{"path": "apps/web/other.tsx", "content": "x", "mode": "100644", "additions": 1, "deletions": 0}]]
    with pytest.raises(GateError, match="outside the approved plan"):
        drive(workflow, start(workflow))
    assert "harness/issue-7" not in gh.heads


def test_base_change_makes_the_task_stale(env):
    gh, script, _, workflow = env
    script.results["pm"] = [result("pm", requires_plan_approval=True)]
    drive(workflow, start(workflow))
    gh.heads["main"] = "9" * 40
    with pytest.raises(GateError):
        say(workflow, f"/approve plan {gh.state['plan_fingerprint'][:12]}")
    assert gh.state["status"] == "stale"
    assert say(workflow, "/resume") == "pm"


def test_handoff_saves_the_pending_decision(env):
    gh, script, _, workflow = env
    script.results["pm"] = [result("pm", requires_plan_approval=True)]
    drive(workflow, start(workflow))
    assert say(workflow, "/handoff") == ""
    assert "/approve plan" in gh.state["handoff"]["brief"] and gh.state["status"] == "awaiting_approval"


def test_deploy_failure_recommends_revert(env):
    gh, script, _, workflow = env
    script.results["deploy"] = [result("deploy", passed=False, findings=["Main CI failed"])]
    drive(workflow, start(workflow))
    assert gh.state["status"] == "deploy_failed" and "reverting" in gh.comments[-1][1]


def test_scope_and_commands():
    config = {"protected_files": [], "protected_prefixes": []}
    safe_path("apps/web/modules/x.tsx", config)
    for path in (".github/workflows/x.yml", "harness/policy.py", "apps/web/package.json", "../x.ts", "packages/prisma/schema.prisma"):
        with pytest.raises(GateError):
            safe_path(path, config)
    assert parse("/approve plan abcdef1234") == ("approve_plan", "abcdef1234")
    assert parse("/option 3") == ("select_design", "3")
    assert parse("/revise use a badge")[0] == "revise"
    assert parse("approve")[0] == "reply"


def test_agent_definitions_restrict_tools():
    for name in ("pm", "designer", "planner", "implementer", "tester", "reviewer", "deployer"):
        agent = definition(AGENTS_DIR / f"{name}.md")
        role = "implementation" if name == "implementer" else "review"
        args = command(CONFIG, agent, schema={"type": "object"}, role=role, writable=name == "implementer")
        assert args[args.index("--model") + 1] == ("opus" if name == "implementer" else "sonnet")
        tools = args[args.index("--tools") + 1].split(",")
        assert ("Edit" in tools) == (name == "implementer")
        assert "StructuredOutput" in tools
    implementer = definition(AGENTS_DIR / "implementer.md")
    assert "Bash(git diff:*)" in implementer["rules"] and "Bash(git commit:*)" not in implementer["rules"]


def test_sample_results_match_the_stage_contracts():
    import jsonschema
    from harness.schemas import STAGES
    for stage, spec in STAGES.items():
        jsonschema.Draft202012Validator.check_schema(spec["schema"])
        sample = result(stage)
        if stage in {"test", "code_evals", "review"}:
            sample = {"head_sha": HEAD1, **sample}
        if stage == "deploy":
            sample = {"merge_sha": MERGE, **sample}
        jsonschema.validate(sample, spec["schema"])


def test_planner_questions_resume_planning_with_design_kept(env):
    gh, script, _, workflow = env
    script.results["pm"] = [result("pm", scope_type="screen")]
    script.results["plan"] = [result("plan", open_questions=["Include pending bookings?"])]
    drive(workflow, start(workflow))
    drive(workflow, say(workflow, "/option 1"))
    assert gh.state["status"] == "needs_information"
    assert say(workflow, "Accepted only.", comment_id=77) == "plan"
    assert gh.state["selected_design"]["id"] == 1 and "77" in gh.state["issue"]["body"]
    assert drive(workflow, "plan") == ["plan"] and gh.state["status"] == "awaiting_approval"
    assert script.calls.count("pm") == 1 and script.calls.count("design") == 1

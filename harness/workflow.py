"""One trusted GitHub Actions job per workflow step; the task state lives on the harness-state branch.

Usage: python -m harness.workflow --step entry            (reads the GitHub event)
       python -m harness.workflow --step <step> --issue N
Each step checks that the task is in the state it expects, runs its agent, checks the result
against the gates in policy.py and writes `next` (the job that runs next, or nothing) to $GITHUB_OUTPUT.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from harness.ci import run_ci
from harness.controller import PAUSED, Controller
from harness.github import GitHub
from harness.handoff import brief
from harness.policy import (GateError, check_results_pass, code_review_gate, complete_plan_files, digest, issue_snapshot, plan_fingerprint,
                            route_plan, validate_diff, validate_plan_scope)
from harness.responses import resolve

HERE = Path(__file__).parent
FOOTER = "\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)"
# The task state each step runs from.
EXPECTED = {"pm": "pm", "research": "research", "design_need": "design_need", "design": "design", "plan": "plan",
            "implement": "implement", "test": "testing", "code_evals": "reviewing", "review": "reviewing",
            "review_gate": "reviewing", "merge": "ready_to_merge", "deploy": "deploying"}
RESTARTABLE = {None, "needs_information", "failed", "stale", "manual_change_required", "deploy_failed"}


class Workflow:
    def __init__(self, controller):
        self.c = controller

    # ── entry: events and human decisions ───────────────────────────────────────────────

    def init(self, event_name, event):
        c = self.c
        if event["repository"]["full_name"] != c.config["repository"]:
            raise GateError("Event repository does not match the harness configuration")
        actor = event["sender"]["login"]
        if event_name == "workflow_dispatch":
            number, action = int(event["inputs"]["issue_number"]), "start"
        elif event_name == "issues":
            if event["action"] == "labeled" and event["label"]["name"] != c.config["label"]:
                return {"next": ""}
            number, action = event["issue"]["number"], "start"
        elif event_name == "issue_comment":
            if event["issue"].get("pull_request") or event["sender"].get("type") != "User":
                return {"next": ""}
            number, action = event["issue"]["number"], "comment"
        else:
            return {"next": ""}
        if not c.gh.can_write(actor):
            return {"next": ""}
        c.load(number)
        if action == "start":
            issue = c.gh.issue(number)
            if c.config["label"] not in [x["name"] for x in issue["labels"]] or (c.state or {}).get("status") not in RESTARTABLE:
                return {"next": ""}
            return self.start(actor)

        decision = resolve(c.state, event["comment"]["body"])
        if not decision:
            return {"next": ""}
        name, argument = decision
        comment_id = event["comment"]["id"]
        if name == "reply":
            # The answer becomes part of the issue text and the task restarts from the PM.
            ids = c.state.get("clarification_comment_ids", []) + [comment_id]
            c.state["clarification_comment_ids"] = ids
            return self.start(actor)
        if name == "handoff":
            c.save(handoff={"actor": actor, "comment_id": comment_id, "at": int(time.time()), "brief": brief(number, c.state)})
            c.comment("pm", "Contexto salvo para a conversa.",
                      decision=f"Rode `python -m harness.handoff {number} | claude` e registre a decisão aqui.")
            return {"next": ""}
        if name == "resume":
            fresh = (c.gh.head(c.config["base_branch"]) == c.state["base_sha"]
                     and digest(issue_snapshot(c.current_issue())) == c.state["issue_digest"])
            if c.state["status"] == "failed" and fresh and c.state.get("failed_step"):
                c.save(c.state["resume_status"], error=None)
                # The two review jobs and their gate rerun together.
                step = c.state["failed_step"]
                return {"next": "review" if step in {"code_evals", "review_gate"} else step}
            return self.start(actor)
        c.ensure_fresh()
        if name == "approve_plan":
            c.save("implement", approval={"actor": actor, "comment_id": comment_id, "fingerprint": c.state["plan_fingerprint"]})
            return {"next": "implement"}
        if name == "select_design":
            option = next(o for o in c.state["design"]["options"] if o["id"] == int(argument))
            c.save("plan", selected_design={**option, "actor": actor, "comment_id": comment_id})
            c.comment("pm", f"Opção {option['id']} escolhida. Vou preparar o plano com esse design.")
            return {"next": "plan"}
        if name == "revise":
            feedback = c.state.get("owner_feedback", []) + [{"actor": actor, "comment_id": comment_id, "text": argument}]
            target = "design" if c.state["status"] == "awaiting_design_selection" else "plan"
            c.save(target, owner_feedback=feedback)
            return {"next": target}
        if name == "approve_merge":
            c.save("ready_to_merge", human_code_review={"actor": actor, "comment_id": comment_id, "head_sha": c.state["head_sha"]})
            return {"next": "merge"}
        raise GateError(f"Unsupported decision {name}")

    def start(self, actor):
        c = self.c
        issue = c.current_issue()
        c.state = {"status": "pm", "issue": issue_snapshot(issue), "issue_digest": digest(issue_snapshot(issue)),
                   "base_sha": c.gh.head(c.config["base_branch"]),
                   "run_id": f"{os.getenv('GITHUB_RUN_ID', str(time.time_ns()))}-{os.getenv('GITHUB_RUN_ATTEMPT', '1')}",
                   "started_by": actor, "stages": [],
                   "clarification_comment_ids": (c.state or {}).get("clarification_comment_ids", [])}
        c.save()
        c.comment("pm", "Recebi o pedido. Vou definir o caminho da entrega.")
        return {"next": "pm"}

    # ── steps ───────────────────────────────────────────────────────────────────────────

    def run(self, step, number):
        c = self.c
        if not c.load(number):
            raise GateError("No state exists for this issue")
        if c.state["status"] != EXPECTED[step]:
            raise GateError(f"Step {step} cannot run from {c.state['status']}")
        if step != "deploy":
            c.ensure_fresh()
        return getattr(self, "step_" + step)()

    def step_pm(self):
        c = self.c
        with c.runner(c.config, c.state["base_sha"]) as agent:
            result = c.stage(agent, "pm", {"issue": c.state["issue"]})
        if result["questions"]:
            c.save("needs_information", pm=result)
            c.comment("pm", result["summary"], questions=result["questions"], decision="Responda aqui para continuar.")
            return {"next": ""}
        c.save("research", pm=result)
        c.comment("pm", result["summary"])
        return {"next": "research"}

    def step_research(self):
        c = self.c
        with c.runner(c.config, c.state["base_sha"]) as agent:
            result = c.stage(agent, "research", {"issue": c.state["issue"], "pm": c.state["pm"]})
        c.save("design_need", research=result)
        c.comment("planning", ("Investigação" if result["kind"] == "bug" else "Pesquisa") + " concluída. " + result["summary"])
        return {"next": "design_need"}

    def step_design_need(self):
        c = self.c
        with c.runner(c.config, c.state["base_sha"]) as agent:
            result = c.stage(agent, "design_need", {"issue": c.state["issue"], "pm": c.state["pm"], "research": c.state["research"]})
        # A new screen cannot silently skip design, even if the eval is mistaken.
        needed = result["needed"] or result["confidence"] < c.config["design_min_confidence"] or c.state["pm"]["scope_type"] == "screen"
        c.save("design" if needed else "plan", design_need={**result, "effective_needed": needed}, design_required=needed)
        c.comment("pm", "Vou pedir três opções ao Designer." if needed else "A mudança aproveita a interface existente. Vou seguir para o plano.")
        return {"next": "design" if needed else "plan"}

    def step_design(self):
        c = self.c
        with c.runner(c.config, c.state["base_sha"]) as agent:
            result = c.stage(agent, "design", {"issue": c.state["issue"], "pm": c.state["pm"], "research": c.state["research"],
                                                "design_brief": c.state["design_need"]["design_brief"],
                                                "owner_feedback": c.state.get("owner_feedback", [])})
        if sorted(o["id"] for o in result["options"]) != [1, 2, 3]:
            raise GateError("The Designer must return options 1, 2 and 3")
        c.save("awaiting_design_selection", design=result, selected_design=None)
        mockups = "\n\n".join(f"**Opção {o['id']}: {o['title']}**\n\n{o['summary']}\n\n```text\n{o['mockup']}\n```"
                              for o in result["options"])
        c.comment("design", f"{result['summary']} Recomendo a opção {result['recommended_option']}.",
                  decision="Comente `/opcao <1-3>` ou `/ajustar <mudanças>`.", details=mockups)
        return {"next": ""}

    def step_plan(self):
        c = self.c
        if c.state.get("design_required") and not c.state.get("selected_design"):
            raise GateError("A required design must be selected before planning")
        context = {"issue": c.state["issue"], "pm": c.state["pm"], "research": c.state["research"],
                   "selected_design": c.state.get("selected_design"), "owner_feedback": c.state.get("owner_feedback", [])}
        with c.runner(c.config, c.state["base_sha"]) as agent:
            plan = complete_plan_files(c.stage(agent, "plan", context))
            evaluation = c.stage(agent, "evaluate", {**context, "plan": plan})
            for _ in range(c.config["max_plan_revisions"]):
                if plan["open_questions"] or (evaluation["aligned"] and evaluation["score"] >= c.config["plan_min_score"]
                                              and not evaluation["missing_acceptance_criteria"]):
                    break
                c.comment("planning", "O eval encontrou uma divergência no plano. Vou pedir a correção ao Planner.")
                plan = complete_plan_files(c.stage(agent, "plan", {**context, "previous_plan": plan, "evaluation_feedback": evaluation}))
                evaluation = c.stage(agent, "evaluate", {**context, "plan": plan})
        fingerprint = plan_fingerprint(c.state["issue"], c.state["base_sha"], plan, evaluation)
        try:
            target = route_plan(plan, evaluation, c.state["pm"], c.config)
        except GateError as error:
            c.save("manual_change_required", plan=plan, evaluation=evaluation, plan_fingerprint=fingerprint, scope_error=str(error))
            c.comment("planning", "O plano sai do escopo que o harness pode alterar.", details=str(error),
                      decision="Comente `/ajustar <mudanças>` ou faça a mudança numa PR separada.")
            return {"next": ""}
        c.save(target, plan=plan, evaluation=evaluation, plan_fingerprint=fingerprint)
        details = "\n".join([f"- Arquivos: {', '.join(plan['files'])}", "- Critérios:",
                             *[f"  - {x}" for x in plan["acceptance_criteria"]], "- Passos:", *[f"  - {x}" for x in plan["steps"]],
                             f"- Risco: {plan['risk']} · eval: {evaluation['score']:.2f}"])
        if target == "needs_information":
            questions = plan["open_questions"] or evaluation["missing_acceptance_criteria"] or evaluation["findings"]
            c.comment("planning", plan["summary"], questions=questions, decision="Responda aqui para continuar.")
            return {"next": ""}
        if target == "awaiting_approval":
            c.comment("planning", plan["summary"], details=details,
                      decision=f"Comente `/aprovar plano {fingerprint[:12]}` ou `/ajustar <mudanças>`.")
            return {"next": ""}
        c.comment("planning", plan["summary"] + " Mudança simples; sigo sem pausa.", details=details)
        return {"next": "implement"}

    def step_implement(self):
        c = self.c
        with c.runner(c.config, c.state["base_sha"]) as agent:
            result = c.stage(agent, "implement", {"issue": c.state["issue"], "pm": c.state["pm"], "plan": c.state["plan"],
                                                   "research": c.state["research"], "selected_design": c.state.get("selected_design")})
            files = agent.files()
        validate_diff(files, c.config)
        validate_plan_scope(files, c.state["plan"])
        branch = f"harness/issue-{c.number}"
        head = c.gh.publish_patch(c.number, c.state["base_sha"], files, branch=branch)
        body = (f"{result['summary']}\n\nCloses #{c.number}\n\nCI, 🤖 Tester e review são exigidos antes do merge. "
                f"Decisões humanas na issue #{c.number}." + FOOTER)
        pr = c.gh.open_pr(branch, c.config["base_branch"], f"feat: {c.state['issue']['title']}", body)
        c.save("testing", branch=branch, head_sha=head, pr_number=pr["number"], pr_url=pr["html_url"],
               implementation=result, attempts=1)
        c.comment("implementation", f"Implementação pronta na PR #{pr['number']}. A CI e o Tester vão verificar a mudança.")
        return {"next": "test"}

    def repair(self, failure):
        """The Implementer fixes the same candidate within the approved plan."""
        c = self.c
        with c.runner(c.config, c.state["head_sha"]) as agent:
            result = c.stage(agent, "repair", {"issue": c.state["issue"], "plan": c.state["plan"], **failure})
            files = agent.files()
        validate_diff(files, c.config)
        validate_plan_scope(files, c.state["plan"])
        head = c.gh.publish_patch(c.number, c.state["head_sha"], files, branch=c.state["branch"])
        c.save(head_sha=head, attempts=c.state["attempts"] + 1, implementation=result)
        c.comment("implementation", result["summary"])

    def step_test(self):
        c = self.c
        while True:
            head = c.state["head_sha"]
            evidence = run_ci(c.gh, c.state["branch"], head, c.state["base_sha"], timeout=c.config["ci_timeout_seconds"])
            c.save(check_evidence=evidence)
            failure = None
            if not evidence["passed"]:
                failure = {"failed_checks": [x for x in evidence["checks"] if x["exit_code"]]}
                summary = "A CI encontrou uma falha."
            else:
                with c.runner(c.config, head) as agent:
                    review = c.stage(agent, "test", {"head_sha": head, "issue": c.state["issue"], "pm": c.state["pm"],
                                                     "plan": c.state["plan"], "diff": agent.diff(c.state["base_sha"]),
                                                     "checks": evidence})
                c.save(test_review=review)
                c.evidence_comment("test", review)
                if review["head_sha"] == head and review["passed"] and not review["findings"]:
                    c.save("reviewing")
                    c.comment("test", review["summary"])
                    return {"next": "review"}
                failure = {"test_findings": review["findings"] or ["O Tester não aprovou os critérios."]}
                summary = "O Tester encontrou uma lacuna."
            if c.state["attempts"] >= c.config["max_implementation_attempts"]:
                c.save("failed", resume_status="testing", failed_step="test", error=summary)
                c.comment("test", summary + " O limite de tentativas acabou.",
                          decision="Aprovação humana não libera testes reprovados. Use `/conversar` ou corrija e comente `/retomar`.")
                return {"next": ""}
            c.comment("test", summary + " O Implementer vai corrigi-la dentro do plano aprovado.")
            self.repair(failure)

    def _review_stage(self, name, field):
        c = self.c
        head = c.state["head_sha"]
        with c.runner(c.config, head) as agent:
            result = c.stage(agent, name, {"head_sha": head, "issue": c.state["issue"], "plan": c.state["plan"],
                                            "selected_design": c.state.get("selected_design"),
                                            "diff": agent.diff(c.state["base_sha"]), "checks": c.state["check_evidence"],
                                            "test_review": c.state["test_review"]})
        c.save(**{field: result})
        c.evidence_comment(name, result)
        return {"next": "review_gate"}

    def step_code_evals(self):
        return self._review_stage("code_evals", "code_evals")

    def step_review(self):
        return self._review_stage("review", "review")

    def step_review_gate(self):
        c = self.c
        head = c.state["head_sha"]
        files = [{"path": f["filename"], "additions": f["additions"], "deletions": f["deletions"]}
                 for f in c.gh.all(f"pulls/{c.state['pr_number']}/files")]
        validate_diff(files, c.config)
        gate = code_review_gate(files, c.state.get("code_evals"), c.state.get("review"), head, c.config)
        c.evidence_comment("review_gate", gate)
        if gate["requires_human"]:
            c.save("awaiting_code_review", code_gate=gate)
            c.comment("review", " ".join(gate["reasons"][:2]),
                      decision=f"Revise a PR #{c.state['pr_number']} e comente `/aprovar merge {head[:12]}` ou `/conversar`.")
            return {"next": ""}
        c.save("ready_to_merge", code_gate=gate)
        c.comment("review", c.state["review"]["summary"] + " Gate automático aprovado.")
        return {"next": "merge"}

    def step_merge(self):
        c = self.c
        head = c.state["head_sha"]
        pr = c.gh.repo_api("GET", f"pulls/{c.state['pr_number']}")
        if pr["head"]["sha"] != head or pr["state"] != "open":
            raise GateError("The PR changed after its evaluation")
        test = c.state.get("test_review") or {}
        if test.get("head_sha") != head or not test.get("passed") or test.get("findings"):
            raise GateError("Human review cannot bypass the Tester gate")
        if not c.state["check_evidence"]["passed"] or c.state["check_evidence"]["head_sha"] != head:
            raise GateError("The evaluated commit has no passing CI evidence")
        if not check_results_pass(c.gh.checks(head), head, c.config["required_checks"]):
            raise GateError("Required checks did not pass on the evaluated commit")
        gate = c.state.get("code_gate") or {}
        if gate.get("head_sha") != head:
            raise GateError("The review gate did not evaluate this commit")
        human = c.state.get("human_code_review")
        if gate["requires_human"] and (not human or human["head_sha"] != head):
            raise GateError("This commit needs a human approval in the issue")
        merged = c.gh.merge_pr(c.state["pr_number"], head, f"{pr['title']} (#{c.state['pr_number']})")
        c.save("deploying", merge_sha=merged["sha"])
        c.comment("deploy", f"PR #{c.state['pr_number']} integrada. Vou verificar a versão integrada.")
        return {"next": "deploy"}

    def step_deploy(self):
        c = self.c
        merge_sha = c.state["merge_sha"]
        evidence = run_ci(c.gh, c.config["base_branch"], merge_sha, c.state["base_sha"], timeout=c.config["ci_timeout_seconds"])
        with c.runner(c.config, merge_sha) as agent:
            result = c.stage(agent, "deploy", {"merge_sha": merge_sha, "issue": c.state["issue"], "pm": c.state["pm"],
                                                "plan": c.state["plan"], "checks": evidence})
        c.save(deploy_evidence=evidence, deploy=result)
        if evidence["passed"] and result["merge_sha"] == merge_sha and result["passed"] and not result["findings"]:
            c.save("done")
            c.comment("deploy", result["summary"] + " Entrega concluída.")
            return {"next": ""}
        c.save("deploy_failed")
        c.comment("deploy", result["summary"], details="\n".join(f"- {x}" for x in result["findings"]) or None,
                  decision=f"Recomendo reverter o merge {merge_sha[:12]} (botão Revert na PR #{c.state['pr_number']}).")
        return {"next": ""}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", required=True)
    parser.add_argument("--issue", type=int)
    args = parser.parse_args()
    config = json.loads((HERE / "config.json").read_text())
    c = Controller(config, GitHub(config["repository"], os.environ["GITHUB_TOKEN"]))
    workflow = Workflow(c)
    try:
        if args.step == "entry":
            event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
            result = workflow.init(os.environ["GITHUB_EVENT_NAME"], event)
        else:
            result = workflow.run(args.step, args.issue)
    except Exception as error:
        if c.state and c.state.get("status") not in PAUSED | {"failed"}:
            c.save("failed", resume_status=c.state["status"], failed_step=None if args.step == "entry" else args.step,
                   error=str(error)[:2000])
        if c.number and c.state and c.state["status"] != "stale":  # a stale task was already reported
            c.comment("pm", "A etapa foi interrompida.", details=str(error)[:2000],
                      decision="Corrija a causa e comente `/retomar`, ou use `/conversar`." if c.state["status"] == "failed" else None)
        raise
    result = {"issue": c.number or "", **result}
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            for name, value in result.items():
                output.write(f"{name}={value}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

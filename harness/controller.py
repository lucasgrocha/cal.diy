"""Task state, human reports and agent calls. Everything an agent produces passes through here."""
from __future__ import annotations

import json
import os
import time
import urllib.error

from harness.agents import agent_for_stage, render_report
from harness.policy import GateError, digest, issue_snapshot
from harness.runner import Runner

# States where the harness waits for a person; a failure there doesn't overwrite them.
PAUSED = {"needs_information", "awaiting_design_selection", "awaiting_approval", "awaiting_code_review",
          "manual_change_required", "stale", "deploy_failed", "done"}


class Controller:
    def __init__(self, config, github, runner=Runner):
        self.config, self.gh, self.runner = config, github, runner
        self.state, self.blob, self.number = None, None, None

    def load(self, number):
        self.number = number
        self.state, self.blob = self.gh.load_state(number)
        return self.state

    def save(self, status=None, **fields):
        """Persists the state; on a concurrent write, reapplies this update to the newer version."""
        previous = (self.state or {}).get("status")
        for _ in range(5):
            if status:
                self.state["status"] = status
            self.state.update(fields)
            self.state["updated_at"] = int(time.time())
            try:
                self.blob = self.gh.save_state(self.number, self.state, self.blob)
                break
            except urllib.error.HTTPError as exc:
                if exc.code not in {409, 422}:
                    raise
                self.state, self.blob = self.gh.load_state(self.number)
        else:
            raise GateError("Could not save the task state: concurrent updates")
        if self.state["status"] != previous:
            self.gh.set_status_label(self.number, self.state["status"])

    def current_issue(self):
        return self.gh.issue(self.number, clarification_ids=(self.state or {}).get("clarification_comment_ids", []))

    def ensure_fresh(self):
        """Plans and evaluations hold only for the issue text and base commit they were made on."""
        if (self.gh.head(self.config["base_branch"]) != self.state["base_sha"]
                or digest(issue_snapshot(self.current_issue())) != self.state["issue_digest"]):
            self.save("stale")
            self.comment("planning", "A issue ou o main mudaram depois do planejamento.",
                         decision="Comente `/retomar` para replanejar sobre a versão atual.")
            raise GateError("Issue or base changed; plan again")

    def comment(self, role, summary, *, decision=None, questions=None, details=None, pr=False):
        body = render_report(role, summary, decision=decision, questions=questions, details=details)
        return self.gh.comment(self.state["pr_number"] if pr else self.number, body)

    def stage(self, runner, name, context):
        """Runs one agent stage: reserves budget, records usage and returns the validated result."""
        execution = f"{os.getenv('GITHUB_RUN_ID', 'local')}-{os.getenv('GITHUB_RUN_ATTEMPT', '1')}"
        writable = name in {"implement", "repair"}
        self.gh.record_budget({"key": f"{self.number}-{self.state['run_id']}-{name}-{execution}-{runner.sha[:12]}",
                               "usd": self.config["implementation_budget_usd" if writable else "agent_reservation_per_stage_usd"]},
                              self.config)
        response = runner.stage(name, context)
        record = {"name": name, "sha": runner.sha, "agent": agent_for_stage(name).role, "at": int(time.time()),
                  "usage": response["usage"], "denied_tools": response["denied_tools"]}
        self.save(stages=self.state.get("stages", [])[-40:] + [record])
        return response["result"]

    def evidence_comment(self, title, data):
        """Full evaluation details go to the PR; the issue only gets the short report."""
        details = "```json\n" + json.dumps(data, ensure_ascii=False, indent=2)[:60_000] + "\n```"
        role = agent_for_stage(title).role
        self.comment(role, f"Avaliação {title} do commit {self.state['head_sha'][:7]}.", details=details, pr=True)

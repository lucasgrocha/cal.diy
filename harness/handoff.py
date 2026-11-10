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
    "needs_information": "Responda às perguntas na issue.",
    "awaiting_design_selection": "Comente `/opcao <1-3>` ou `/ajustar <mudanças>`.",
    "awaiting_approval": "Comente `/aprovar plano <fingerprint>` ou `/ajustar <mudanças>`.",
    "awaiting_code_review": "Comente `/aprovar merge <sha>` ou peça ajustes.",
    "manual_change_required": "Comente `/ajustar <mudanças>` para replanejar dentro do escopo permitido.",
    "failed": "Corrija a causa e comente `/retomar`.",
    "stale": "Comente `/retomar` para replanejar sobre a versão atual.",
    "deploy_failed": "Decida se reverte o merge.",
}


def brief(number, state):
    status = state["status"]
    pending = DECISIONS.get(status, "Nenhuma decisão pendente.")
    evidence = {k: state[k] for k in ("pm", "research", "design_need", "evaluation", "check_evidence", "test_review",
                                      "code_evals", "review", "code_gate", "error") if state.get(k)}
    plan = state.get("plan") or {}
    return "\n".join([
        f"# Handoff da issue #{number}: {state['issue']['title']}",
        "", "## Objetivo", "", state["issue"]["body"] or "(sem descrição)",
        "", "## Plano atual", "", json.dumps(plan, ensure_ascii=False, indent=2) if plan else "(ainda sem plano)",
        "", "## Evidências", "", "```json", json.dumps(evidence, ensure_ascii=False, indent=2), "```",
        "", f"## Decisão pendente (estado `{status}`)", "", pending,
        "", "Depois da conversa, registre a decisão na issue com o comando acima; o workflow reavalia os gates ao retomar.",
        f"Comandos aceitos agora: {', '.join(sorted(a for a, states in ACCEPTED.items() if status in states))}.",
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

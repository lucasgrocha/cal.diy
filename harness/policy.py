"""Deterministic gates. Model decisions cannot override these controls."""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath


class GateError(RuntimeError):
    pass


APPLICATION_PREFIXES = ("apps/web/", "packages/features/", "packages/lib/", "packages/ui/", "packages/i18n/locales/")
APPLICATION_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".css")


def application_scope(config):
    return {"allowed_prefixes": list(APPLICATION_PREFIXES),
            "allowed_extensions": list(APPLICATION_EXTENSIONS),
            "protected_prefixes": config.get("protected_prefixes", []),
            "protected_files": config.get("protected_files", []),
            "human_review_prefixes": config.get("human_risk_prefixes", []) + config.get("core_review_prefixes", []),
            "human_review_files": config.get("core_review_files", []),
            "rules": "Every planned edit, including tests, must satisfy this scope. Choose test locations inside it. "
                     "Do not add lockfile, tooling or dependency changes. Human approval does not expand this scope."}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def issue_snapshot(issue):
    return {"number": issue["number"], "title": issue["title"], "body": issue.get("body") or ""}


def plan_fingerprint(issue, base_sha, plan, evaluation):
    return digest({"issue": issue_snapshot(issue), "base_sha": base_sha, "plan": plan, "evaluation": evaluation})


def safe_path(path, config):
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or "\\" in path or not p.parts or any(ord(c) < 32 for c in path):
        raise GateError(f"Invalid changed path: {path!r}")
    if any(x in {".git", ".github", ".agents", ".codex", ".claude", "node_modules", ".next"} or x.startswith(".env") for x in p.parts):
        raise GateError(f"Protected path: {path}")
    protected_name = p.name in {"AGENTS.md", "CLAUDE.md", "package.json", "yarn.lock", ".yarnrc.yml"} or p.name.startswith(("tsconfig", "vitest.config"))
    if protected_name or path in config["protected_files"] or any(path.startswith(x) for x in config["protected_prefixes"]):
        raise GateError(f"Protected path: {path}. Change the harness through a separate reviewed PR.")
    if p.suffix not in APPLICATION_EXTENSIONS:
        raise GateError(f"Unsupported changed file type: {path}")
    if not path.startswith(APPLICATION_PREFIXES):
        raise GateError(f"Outside the application change scope: {path}")


def validate_diff(files, config):
    if not files or len(files) > config["max_changed_files"]:
        raise GateError("Empty patch or changed-file limit exceeded")
    if sum(f.get("additions", 0) + f.get("deletions", 0) for f in files) > config["max_changed_lines"]:
        raise GateError("Changed-line limit exceeded")
    for f in files:
        safe_path(f["path"], config)
        if f.get("mode", "100644") not in {"100644", "100755"}:
            raise GateError("Symlinks and submodules are not accepted")


def validate_plan_scope(files, plan):
    outside = sorted(f["path"] for f in files if f["path"] not in plan["files"])
    if outside:
        raise GateError("Implementation includes files outside the approved plan: " + ", ".join(outside))


def complete_plan_files(plan):
    """Bind declared new tests into the plan before evaluation and approval."""
    files = list(plan["files"])
    for test in plan.get("tests", []):
        if test.get("kind") == "new_test" and test["path"] not in files:
            files.append(test["path"])
    return {**plan, "files": files}


def route_plan(plan, evaluation, pm, config):
    """implement, awaiting_approval or needs_information; raises GateError for protected scope."""
    if evaluation["score"] < config["plan_min_score"] or not evaluation["aligned"] or evaluation["missing_acceptance_criteria"] or plan["open_questions"]:
        return "needs_information"
    for path in plan["files"]:
        safe_path(path, config)
    if plan["risk"] != "low" or evaluation["risk"] != "low" or evaluation["requires_human"]:
        return "awaiting_approval"
    if pm["requires_plan_approval"] or pm["complexity"] == "complex" or pm["scope_type"] == "screen":
        return "awaiting_approval"
    if any(path.startswith(prefix) for path in plan["files"] for prefix in config["human_risk_prefixes"]):
        return "awaiting_approval"
    return "implement"


def review_passes(review, head_sha, config):
    return (review["head_sha"] == head_sha and review["score"] >= config["review_min_score"]
            and review["aligned"] and not review["findings"] and review["risk"] == "low")


def check_results_pass(results, head_sha, required):
    by_name = {}
    for check in results:
        if check.get("head_sha") != head_sha or check.get("app", {}).get("slug") != "github-actions":
            continue
        old = by_name.get(check["name"])
        if old is None or check.get("id", 0) > old.get("id", 0):
            by_name[check["name"]] = check
    return all(name in by_name and by_name[name].get("status") == "completed"
               and by_name[name].get("conclusion") == "success" for name in required)


def validate_check_evidence(evidence, head_sha):
    """A summary or green workflow alone cannot stand in for executed checks."""
    if not isinstance(evidence, dict) or evidence.get("head_sha") != head_sha:
        raise GateError("Checks artifact commit mismatch")
    checks = evidence.get("checks")
    if not isinstance(checks, list) or not checks:
        raise GateError("Checks artifact contains no actual checks")
    names = set()
    for check in checks:
        if (not isinstance(check, dict) or not isinstance(check.get("name"), str) or check["name"] in names
                or type(check.get("exit_code")) is not int
                or not isinstance(check.get("command"), list) or not check["command"]):
            raise GateError("Checks artifact has invalid execution evidence")
        names.add(check["name"])
    if {"tests", "web-types", "lint"} - names:
        raise GateError("Checks artifact omits required application checks")
    if evidence.get("passed") is not all(check["exit_code"] == 0 for check in checks):
        raise GateError("Checks artifact conclusion disagrees with its executed checks")


def deterministic_review(files, config):
    """Path-based human review requirements, unaffected by model scores."""
    paths = sorted({f["path"] for f in files})
    migrations, core = [], []
    for path in paths:
        p = PurePosixPath(path)
        if any(part.casefold() in config["migration_review_segments"] for part in p.parts) or p.name.casefold() in config["migration_review_files"]:
            migrations.append(path)
        if path in config["core_review_files"] or any(path.startswith(prefix) for prefix in config["core_review_prefixes"] + config["human_risk_prefixes"]):
            core.append(path)
    return {"migration_files": migrations, "core_files": core, "requires_human": bool(migrations or core)}


def code_review_gate(files, code_evals, review, head_sha, config):
    fixed = deterministic_review(files, config)
    reasons = []
    if fixed["migration_files"]:
        reasons.append("Migrações alteradas exigem review humano.")
    if fixed["core_files"]:
        reasons.append("Arquivos core alterados exigem review humano.")
    if not code_evals or code_evals["head_sha"] != head_sha:
        raise GateError("Code evals must identify the evaluated commit")
    if code_evals["complexity"]["level"] in config["human_review_complexity_levels"]:
        reasons.append("A complexidade da mudança exige review humano.")
    adherence = code_evals["plan_adherence"]
    if not adherence["passed"] or adherence["score"] < config["review_min_score"] or adherence["findings"]:
        reasons.append("O eval encontrou divergências em relação ao plano.")
    if not code_evals["style"]["passed"] or code_evals["style"]["findings"]:
        reasons.append("O eval encontrou divergências nas regras de estilo.")
    if code_evals["human_review"]["required"]:
        reasons.extend(code_evals["human_review"]["reasons"] or ["O eval recomenda review humano."])
    if not review or review["head_sha"] != head_sha:
        raise GateError("The review must identify the evaluated commit")
    if not review_passes(review, head_sha, config):
        if review["findings"]:
            reasons.append("O Reviewer encontrou pontos que exigem revisão humana.")
        elif review["aligned"] and review["score"] >= config["review_min_score"]:
            reasons.append("A revisão não encontrou problemas. O risco exige aprovação humana.")
        else:
            reasons.append("O Reviewer não confirmou alinhamento suficiente com o pedido.")
    return {"head_sha": head_sha, "requires_human": bool(reasons), "reasons": list(dict.fromkeys(reasons)),
            "deterministic_checks": fixed}

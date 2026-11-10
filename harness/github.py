"""GitHub operations owned by the controller, never by an agent."""
from __future__ import annotations

import base64
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from harness.policy import GateError, validate_check_evidence

STATE_BRANCH = "harness-state"
CI_WORKFLOW = "harness-ci.yml"


class GitHub:
    def __init__(self, repo, token):
        self.repo, self.token = repo, token

    def api(self, method, path, data=None):
        url = path if path.startswith("https://") else "https://api.github.com" + path
        headers = {"Authorization": "Bearer " + self.token, "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28"}
        body = json.dumps(data).encode() if data is not None else None
        request = urllib.request.Request(url, body, headers, method=method)
        # Retry reads only. Retrying a mutation can create duplicate PRs or comments.
        for attempt in range(3 if method == "GET" else 1):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as exc:
                if method == "GET" and exc.code in {429, 502, 503, 504} and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise

    def repo_api(self, method, path, data=None):
        return self.api(method, f"/repos/{self.repo}/{path}", data)

    def all(self, path):
        result, page = [], 1
        while True:
            separator = "&" if "?" in path else "?"
            items = self.repo_api("GET", f"{path}{separator}per_page=100&page={page}")
            result.extend(items)
            if len(items) < 100:
                return result
            page += 1

    # ── issue ─────────────────────────────────────────────────────────────────────────

    def issue(self, number, *, clarification_ids=()):
        issue = self.repo_api("GET", f"issues/{number}")
        if "pull_request" in issue:
            raise GateError("A pull request cannot trigger an issue workflow")
        if issue["state"] != "open":
            raise GateError("Issue is closed")
        clarifications = [f"Details from @{c['user']['login']} (comment {c['id']}):\n{c['body']}"
                          for c in self.all(f"issues/{number}/comments")
                          if c["id"] in clarification_ids and c["user"].get("type") == "User"
                          and self.can_write(c["user"]["login"])]
        if clarifications:
            issue["body"] = (issue.get("body") or "") + "\n\n" + "\n\n".join(clarifications)
        return issue

    def can_write(self, login):
        try:
            response = self.repo_api("GET", f"collaborators/{urllib.parse.quote(login, safe='')}/permission")
            return response["permission"] in {"admin", "maintain", "write"}
        except urllib.error.HTTPError:
            return False

    def comment(self, number, body):
        return self.repo_api("POST", f"issues/{number}/comments", {"body": body})

    def set_status_label(self, number, status):
        """One `harness:<status>` label shows where the issue is."""
        label = f"harness:{status}"
        try:
            self.repo_api("POST", "labels", {"name": label, "color": "5319E7"})
        except urllib.error.HTTPError as exc:
            if exc.code != 422:  # already exists
                raise
        for current in self.repo_api("GET", f"issues/{number}/labels"):
            if current["name"].startswith("harness:") and current["name"] != label:
                self.repo_api("DELETE", f"issues/{number}/labels/{urllib.parse.quote(current['name'], safe='')}")
        self.repo_api("POST", f"issues/{number}/labels", {"labels": [label]})

    # ── persisted state ───────────────────────────────────────────────────────────────

    def head(self, branch):
        return self.repo_api("GET", "git/ref/heads/" + urllib.parse.quote(branch, safe="/"))["object"]["sha"]

    def _ensure_state_branch(self):
        try:
            self.head(STATE_BRANCH)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            # An orphan branch: state never shares history with the application.
            readme = "# harness-state\n\nHarness state, budget and evidence. Do not merge.\n"
            tree = self.repo_api("POST", "git/trees", {"tree": [{"path": "README.md", "mode": "100644", "type": "blob", "content": readme}]})
            commit = self.repo_api("POST", "git/commits", {"message": "harness: state branch", "tree": tree["sha"], "parents": []})
            self.repo_api("POST", "git/refs", {"ref": f"refs/heads/{STATE_BRANCH}", "sha": commit["sha"]})

    def load_json(self, path):
        try:
            item = self.repo_api("GET", f"contents/{path}?ref={STATE_BRANCH}")
            return json.loads(base64.b64decode(item["content"])), item["sha"]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None, None
            raise

    def put_json(self, path, data, blob, message):
        """Writes only if the file is still at `blob`; a concurrent writer gets HTTP 409."""
        self._ensure_state_branch()
        body = {"message": message, "branch": STATE_BRANCH,
                "content": base64.b64encode((json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode()).decode()}
        if blob:
            body["sha"] = blob
        return self.repo_api("PUT", f"contents/{path}", body)["content"]["sha"]

    def load_state(self, number):
        return self.load_json(f"runs/{number}.json")

    def save_state(self, number, state, blob):
        return self.put_json(f"runs/{number}.json", state, blob, f"harness: issue #{number} {state['status']}")

    def record_budget(self, reservation, config):
        for _ in range(5):
            ledger, blob = self.load_json("budget.json")
            ledger = ledger or {"reserved_agent_usd": 0, "runs": []}
            if any(x["key"] == reservation["key"] for x in ledger["runs"]):
                return
            if ledger["reserved_agent_usd"] + reservation["usd"] > config["agent_budget_usd"]:
                raise GateError("Project agent budget exhausted. No agent started.")
            ledger["reserved_agent_usd"] += reservation["usd"]
            ledger["runs"].append(reservation)
            try:
                self.put_json("budget.json", ledger, blob, f"harness: reserve {reservation['key']}")
                return
            except urllib.error.HTTPError as exc:
                if exc.code not in {409, 422}:
                    raise
        raise GateError("Could not reserve budget: concurrent updates")

    # ── candidate commit and PR ───────────────────────────────────────────────────────

    def publish_patch(self, number, base_sha, files, *, branch):
        """Commits the files on top of base_sha and points `branch` at it. Agents never push."""
        base = self.repo_api("GET", f"git/commits/{base_sha}")
        tree = []
        for file in files:
            if file["content"] is None:
                tree.append({"path": file["path"], "mode": file["mode"], "type": "blob", "sha": None})
            else:
                blob = self.repo_api("POST", "git/blobs", {"content": file["content"], "encoding": "utf-8"})
                tree.append({"path": file["path"], "mode": file["mode"], "type": "blob", "sha": blob["sha"]})
        new_tree = self.repo_api("POST", "git/trees", {"base_tree": base["tree"]["sha"], "tree": tree})
        commit = self.repo_api("POST", "git/commits", {"message": f"feat: implement issue #{number}",
                                                       "tree": new_tree["sha"], "parents": [base_sha]})
        try:
            self.repo_api("PATCH", "git/refs/heads/" + branch, {"sha": commit["sha"], "force": True})
        except urllib.error.HTTPError as exc:
            if exc.code != 422:
                raise
            self.repo_api("POST", "git/refs", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
        return commit["sha"]

    def open_pr(self, branch, base, title, body):
        existing = self.repo_api("GET", f"pulls?state=open&head={self.repo.split('/')[0]}:{branch}")
        if existing:
            return self.repo_api("PATCH", f"pulls/{existing[0]['number']}", {"title": title, "body": body})
        return self.repo_api("POST", "pulls", {"title": title, "head": branch, "base": base, "body": body})

    def merge_pr(self, number, head_sha, title):
        return self.repo_api("PUT", f"pulls/{number}/merge", {"sha": head_sha, "merge_method": "squash",
                                                              "commit_title": title})

    # ── CI evidence ───────────────────────────────────────────────────────────────────

    def checks(self, head):
        checks, page = [], 1
        while True:
            data = self.repo_api("GET", f"commits/{head}/check-runs?per_page=100&page={page}")
            checks.extend(data["check_runs"])
            if len(checks) >= data["total_count"]:
                return checks
            page += 1

    def dispatch_ci(self, ref, base_sha):
        """PRs and pushes made with GITHUB_TOKEN don't start workflows; a dispatch does."""
        self.repo_api("POST", f"actions/workflows/{CI_WORKFLOW}/dispatches", {"ref": ref, "inputs": {"base_sha": base_sha}})

    def ci_run(self, head_sha, since):
        runs = self.repo_api("GET", f"actions/workflows/{CI_WORKFLOW}/runs?event=workflow_dispatch&head_sha={head_sha}&per_page=20")
        runs = [r for r in runs["workflow_runs"] if r["created_at"] >= since and r["head_sha"] == head_sha]
        return max(runs, key=lambda r: r["id"], default=None)

    def check_evidence(self, run_id, head_sha):
        run = self.repo_api("GET", f"actions/runs/{run_id}")
        if (run.get("head_sha") != head_sha or run.get("path") != f".github/workflows/{CI_WORKFLOW}"
                or run.get("repository", {}).get("full_name") != self.repo
                or run.get("head_repository", {}).get("full_name") != self.repo
                or run.get("status") != "completed"):
            raise GateError("CI run does not belong to the candidate commit")
        artifacts = self.repo_api("GET", f"actions/runs/{run_id}/artifacts")["artifacts"]
        artifact = next((x for x in artifacts if x["name"] == "harness-checks-" + head_sha and not x["expired"]), None)
        if not artifact:
            raise GateError("The exact-commit checks artifact is missing")

        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        request = urllib.request.Request(artifact["archive_download_url"], headers={"Authorization": "Bearer " + self.token})
        try:
            urllib.request.build_opener(NoRedirect).open(request, timeout=30)
            raise GateError("Expected a signed artifact download URL")
        except urllib.error.HTTPError as exc:
            if exc.code != 302:
                raise
            url = exc.headers["Location"]
        if not url.startswith("https://"):
            raise GateError("Invalid artifact download URL")
        # The GitHub credential is not forwarded to the object-storage redirect.
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(10_000_001)
        if len(data) > 10_000_000:
            raise GateError("Checks artifact exceeds the download limit")
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            evidence = json.loads(archive.read("checks.json"))
        validate_check_evidence(evidence, head_sha)
        return {**evidence, "run_id": run_id, "run_url": run["html_url"]}

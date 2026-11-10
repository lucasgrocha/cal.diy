"""Runs Harness CI on an exact commit and returns its executed-check evidence."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from harness.policy import GateError


def run_ci(gh, ref, head_sha, base_sha, *, profile, timeout, poll=20):
    """Dispatches Harness CI on `ref`, which must point at head_sha, and waits for its evidence.
    The checks cover the files changed since base_sha; `profile` is fast (candidate) or full (merged)."""
    if gh.head(ref) != head_sha:
        raise GateError(f"{ref} moved away from the commit under evaluation")
    since = (datetime.now(timezone.utc) - timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    gh.dispatch_ci(ref, base_sha, profile)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = gh.ci_run(head_sha, since)
        if run and run["status"] == "completed":
            return gh.check_evidence(run["id"], head_sha, profile)
        time.sleep(poll)
    raise GateError(f"Harness CI did not finish within {timeout}s")

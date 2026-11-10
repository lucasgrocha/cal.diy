"""Executed-check evidence for Harness CI. Runs the candidate's checks and writes checks.json.

Usage: python ci_checks.py <base_sha> <head_sha> <output.json>   (cwd: the candidate checkout)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

CODE = (".ts", ".tsx", ".js", ".jsx")


def run(name, command, head_sha):
    env = {**os.environ, "TZ": "UTC"}
    done = subprocess.run(command, capture_output=True, text=True, env=env)
    output = (done.stdout + done.stderr)[-6000:]
    print(f"::group::{name} (exit {done.returncode})\n{output}\n::endgroup::")
    return {"name": name, "head_sha": head_sha, "command": command, "exit_code": done.returncode,
            "conclusion": "success" if done.returncode == 0 else "failure", "output_tail": output}


def main():
    base_sha, head_sha, output = sys.argv[1:4]
    changed = subprocess.run(["git", "diff", "--name-only", "--diff-filter=d", base_sha, head_sha],
                             capture_output=True, text=True, check=True).stdout.split()
    code = [path for path in changed if path.endswith(CODE)]
    checks = [
        run("tests", ["yarn", "vitest", "related", "--run", "--passWithNoTests", *code] if code else ["true"], head_sha),
        run("web-types", ["yarn", "workspace", "@calcom/web", "type-check"], head_sha),
        run("lint", ["yarn", "biome", "check", "--diagnostic-level=error", "--no-errors-on-unmatched", *changed]
            if changed else ["true"], head_sha),
    ]
    evidence = {"head_sha": head_sha, "base_sha": base_sha, "changed_files": changed, "checks": checks,
                "passed": all(check["exit_code"] == 0 for check in checks)}
    with open(output, "w") as file:
        json.dump(evidence, file, indent=2)
    sys.exit(0 if evidence["passed"] else 1)


if __name__ == "__main__":
    main()

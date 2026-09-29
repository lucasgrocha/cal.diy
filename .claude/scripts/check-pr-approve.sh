#!/usr/bin/env bash
# PreToolUse hook: only let `gh pr review --approve` run when the target PR's
# diff is text-only (docs/copy/config). Blocks the tool call otherwise.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
policy_file="$script_dir/../policies/pr-auto-approve.json"

input="$(cat)"
command="$(printf '%s' "$input" | jq -r '.tool_input.command // empty')"

# Only act on `gh pr review --approve` invocations; allow everything else.
if ! printf '%s' "$command" | grep -qE 'gh[[:space:]]+pr[[:space:]]+review[[:space:]]+--approve'; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}'
  exit 0
fi

# Extract the PR argument: a URL, a number, or a bare branch name after --approve.
pr_arg="$(printf '%s' "$command" | grep -oE 'gh[[:space:]]+pr[[:space:]]+review[[:space:]]+--approve[[:space:]]+[^ ]+' | awk '{print $NF}')"

if [ -z "$pr_arg" ]; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Could not determine which PR this approves — refusing to auto-approve."}}'
  exit 0
fi

if ! diff_output="$(gh pr diff "$pr_arg" --name-only 2>&1)"; then
  echo "$(jq -n --arg reason "Could not fetch PR diff for '$pr_arg': $diff_output" '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$reason}}')"
  exit 0
fi

if [ -z "$diff_output" ]; then
  echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"PR diff returned no changed files — refusing to auto-approve."}}'
  exit 0
fi

# Extensions that indicate code/logic changes, loaded from the policy config —
# anything else is treated as text. Source of truth: .claude/policies/pr-auto-approve.json
if [ ! -f "$policy_file" ]; then
  jq -n --arg reason "Policy file missing at $policy_file — refusing to auto-approve." \
    '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$reason}}'
  exit 0
fi

code_ext_regex="$(jq -r '.codeExtensions | map(ltrimstr(".") | "\\." + . ) | join("|") | "(" + . + ")$"' "$policy_file")"

logic_files="$(printf '%s\n' "$diff_output" | grep -iE "$code_ext_regex" || true)"

if [ -n "$logic_files" ]; then
  reason="PR $pr_arg touches code-logic files, not just text/docs/config:
$logic_files
Auto-approve policy only covers text-only PRs — approve manually instead."
  jq -n --arg reason "$reason" '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":$reason}}'
  exit 0
fi

jq -n --arg files "$diff_output" '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":("Diff is text-only, auto-approving:\n" + $files)}}'

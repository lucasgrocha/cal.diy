# Helpers for .github/workflows/harness.yml (see the state machine documented there).
# Expects GH_TOKEN, REPO, ISSUE, ACTOR, RUN_URL and RUNNER_TEMP in the environment.

HARNESS_BLOCKED="harness:blocked"
HARNESS_TICKET_DIR=".claude/tickets/issue-$ISSUE"

# Records why the run stopped, for the workflow's failure step, and aborts the step.
harness_fail() {
  echo "$1" >"$RUNNER_TEMP/harness-block-reason"
  echo "::error::$1"
  exit 1
}

# Only the repository owner may steer the harness or feed it context.
harness_trusted() {
  [[ $1 == "${REPO%%/*}" ]]
}

harness_labels() {
  gh issue view "$ISSUE" --repo "$REPO" --json labels --jq '.labels[].name'
}

# Leaves the issue with exactly one stage label, clearing the blocked flag.
harness_set_stage() {
  local label args=()
  while read -r label; do
    if [[ $label == harness:* && $label != "harness:$1" ]]; then args+=(--remove-label "$label"); fi
  done < <(harness_labels)
  gh label create "harness:$1" --repo "$REPO" --color 5319E7 --force >/dev/null
  gh issue edit "$ISSUE" --repo "$REPO" --add-label "harness:$1" "${args[@]}" >/dev/null
}

harness_block() {
  gh label create "$HARNESS_BLOCKED" --repo "$REPO" --color B60205 --force >/dev/null
  gh issue edit "$ISSUE" --repo "$REPO" --add-label "$HARNESS_BLOCKED" >/dev/null
}

# Usage: harness_comment <kind> <title> <body> [request to the human]
# The hidden marker lets later stages find harness records in the thread.
harness_comment() {
  {
    printf '<!-- harness:%s -->\n%s\n\n%s\n\n' "$1" "$2" "$3"
    if [[ -n ${4:-} ]]; then printf '**%s**\n\n' "$4"; fi
    printf '<sub>Harness · [run](%s)</sub>\n' "$RUN_URL"
  } | gh issue comment "$ISSUE" --repo "$REPO" --body-file - >/dev/null
}

# Decides which stage this event starts and applies its label. Writes `stage=` (empty when
# the event changes nothing) to $GITHUB_OUTPUT. Needs EVENT_NAME and, for comments, COMMENT.
harness_route() {
  local issue labels stage cmd next=""
  issue=$(gh issue view "$ISSUE" --repo "$REPO" --json state,labels)
  labels=$(jq -r '.labels[].name' <<<"$issue")
  stage=$(grep '^harness:' <<<"$labels" | grep -vx "$HARNESS_BLOCKED" | sed 's/^harness://' || true)

  if [[ $(jq -r .state <<<"$issue") != OPEN ]] || ! grep -qx prioritized <<<"$labels"; then
    echo "::notice::Issue is closed or lacks the prioritized label; nothing to do."
  elif [[ $(grep -c . <<<"$stage") -gt 1 ]]; then
    echo "::warning::The issue has more than one stage (${stage//$'\n'/, }); keep a single harness:* label."
  elif [[ $EVENT_NAME == issues ]]; then
    if [[ -z $stage ]]; then next=research; fi
  elif harness_trusted "$ACTOR"; then
    cmd=$(awk 'NF { print $1; exit }' <<<"$COMMENT")
    case "$stage:$cmd" in
      research:/resume | plan:/resume | implementation:/resume) next=$stage ;;
      awaiting-answers:*) next=plan ;;
      awaiting-approval:/approve) next=implementation ;;
      awaiting-approval:/revise) next=plan ;;
    esac
  else
    echo "::notice::@$ACTOR is not the repository owner; comment ignored."
  fi

  if [[ -n $next ]]; then harness_set_stage "$next"; fi
  echo "stage=$next" >>"$GITHUB_OUTPUT"
}

# Writes the issue and its trusted discussion (the owner plus harness records) to
# the file Claude reads, so comments from anyone else never reach the model.
harness_context() {
  local tmp login trusted='[]'
  tmp=$(mktemp -d)
  gh api "repos/$REPO/issues/$ISSUE" >"$tmp/issue.json"
  gh api --paginate "repos/$REPO/issues/$ISSUE/comments" | jq -s 'add // []' >"$tmp/comments.json"
  for login in $(jq -r '[.[] | select(.user.type != "Bot") | .user.login] | unique[]' "$tmp/comments.json"); do
    if harness_trusted "$login"; then trusted=$(jq -c --arg l "$login" '. + [$l]' <<<"$trusted"); fi
  done
  mkdir -p "$HARNESS_TICKET_DIR"
  jq -r --argjson trusted "$trusted" --slurpfile comments "$tmp/comments.json" '
    "# Issue #\(.number): \(.title)\n\n\(.body // "")\n\n## Discussion\n" +
    ($comments[0]
      | map(select(
          (.user.login == "github-actions[bot]" and (.body | contains("<!-- harness:")))
          or (.user.login as $l | $trusted | index($l))))
      | map("\n### @\(.user.login) at \(.created_at)\n\n\(.body)\n")
      | join(""))' "$tmp/issue.json" >"$HARNESS_TICKET_DIR/context.md"
}

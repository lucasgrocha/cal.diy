"""Claude Code invocation and strict result validation."""
from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema


def definition(path):
    """Role prompt and tool rules of an agent file in .claude/agents."""
    text = Path(path).read_text()
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not match:
        raise ValueError(f"{path} has no frontmatter")
    tools = re.search(r"^tools:\s*(.+)$", match.group(1), re.M)
    if not tools:
        raise ValueError(f"{path} lists no tools")
    rules = [rule.strip() for rule in re.split(r",\s*(?![^()]*\))", tools.group(1)) if rule.strip()]
    return {"prompt": match.group(2).strip(), "rules": rules}


def command(config, agent, *, schema, role, writable=False, executable="claude"):
    rules = [*agent["rules"], "StructuredOutput"]
    names = ",".join(dict.fromkeys(rule.split("(")[0] for rule in rules))
    settings = {"disableAllHooks": True, "autoMemoryEnabled": False}
    model = {"model": config["model"], "reasoning_effort": config["reasoning_effort"], **config["role_models"].get(role, {})}
    jsonschema.Draft202012Validator.check_schema(schema)
    return [executable, "-p", "--output-format", "json", "--no-session-persistence",
            "--restricted", "--permission-mode", "dontAsk", "--permission-prompts", "none",
            "--tools", names, "--allowedTools", ",".join(rules), "--disallowedTools", "mcp__*",
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--disable-slash-commands", "--settings", json.dumps(settings),
            "--append-system-prompt", agent["prompt"],
            "--model", model["model"], "--effort", model["reasoning_effort"],
            "--max-turns", str(config["implementation_max_turns"] if writable else config["agent_max_turns"]),
            "--max-budget-usd", str(config["implementation_budget_usd"] if writable else config["agent_reservation_per_stage_usd"]),
            "--json-schema", json.dumps(schema)]


def parse_result(raw, *, schema):
    if len(raw.encode()) > 2_000_000:
        raise ValueError("Claude result exceeds the size limit")
    envelope = json.loads(raw)
    if (not isinstance(envelope, dict) or envelope.get("type") != "result"
            or envelope.get("subtype") != "success" or envelope.get("is_error") is not False):
        # The provider error may contain task input or credentials; report only its type.
        raise ValueError(f"Claude did not return a successful result ({envelope.get('subtype')})")
    result = envelope.get("structured_output")
    jsonschema.validate(result, schema)
    usage = envelope.get("usage") or {}
    return {"result": result, "denied_tools": sorted({d.get("tool_name", "unknown") for d in envelope.get("permission_denials") or []}),
            "usage": {"input_tokens": usage.get("input_tokens", 0), "output_tokens": usage.get("output_tokens", 0),
                      "total_cost_usd": envelope.get("total_cost_usd")}}


def redact(text, secrets=()):
    for secret in sorted(filter(None, secrets), key=len, reverse=True):
        text = text.replace(secret, "[redacted]")
    return re.sub(r"(?:sk-ant-[A-Za-z0-9_-]+|gh[pousr]_[A-Za-z0-9]+|eyJ[A-Za-z0-9_.-]+)", "[redacted]", text)

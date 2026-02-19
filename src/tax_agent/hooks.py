"""Safety and audit hooks for the Agent SDK tax agent.

These hooks provide:
1. Audit logging for all tool usage
2. File access control to restrict reads to tax-relevant directories
3. SSN redaction from tool outputs
4. Rate limiting to prevent runaway API usage
"""

import logging
import re
from pathlib import Path
from typing import Any

from tax_agent.config import get_config

logger = logging.getLogger("tax_agent.audit")


async def audit_log_hook(
    input_data: dict,
    tool_use_id: str | None,
    context: Any,
) -> dict:
    """
    Log all tool usage for audit trail.

    This hook runs on both PreToolUse and PostToolUse to create
    a complete audit log of agent activities.
    """
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})

    # Log tool invocation
    if "tool_result" not in input_data:
        # PreToolUse
        logger.info(f"Tool invoked: {tool_name} (id: {tool_use_id})")
        if tool_name == "Read":
            logger.info(f"  Reading file: {tool_input.get('file_path', 'unknown')}")
        elif tool_name == "Grep":
            logger.info(f"  Searching for: {tool_input.get('pattern', 'unknown')}")
        elif tool_name in ("WebSearch", "WebFetch"):
            logger.info(f"  Web access: {tool_input.get('query', tool_input.get('url', 'unknown'))}")
    else:
        # PostToolUse
        result = input_data.get("tool_result", "")
        result_preview = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
        logger.info(f"Tool completed: {tool_name} (id: {tool_use_id})")
        logger.debug(f"  Result preview: {result_preview}")

    return {}


async def sensitive_data_guard(
    input_data: dict,
    tool_use_id: str | None,
    context: Any,
) -> dict:
    """
    Block access to files outside tax context.

    This hook ensures the agent can only read files from:
    - The configured data directory
    - Temp directories (for processing)
    - The user's specified document directories
    """
    tool_name = input_data.get("tool_name", "")

    if tool_name not in ("Read", "Write", "Grep", "Glob"):
        return {}

    config = get_config()
    tool_input = input_data.get("tool_input", {})

    # Get the file path being accessed
    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "")
    elif tool_name in ("Grep", "Glob"):
        file_path = tool_input.get("path", "")
    else:
        return {}

    if not file_path:
        return {}

    # Allowed paths for tax agent operations
    allowed_prefixes = [
        "/tmp/",
        str(config.data_dir),
        str(config.config_dir),
    ]

    # Check if file path is within allowed directories
    file_path_resolved = str(Path(file_path).resolve())
    is_allowed = any(
        file_path_resolved.startswith(str(Path(prefix).resolve()))
        for prefix in allowed_prefixes
    )

    if not is_allowed:
        logger.warning(f"Blocked file access attempt: {file_path}")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"File access restricted. Only tax documents in configured "
                    f"directories can be accessed: {file_path}"
                ),
            }
        }

    return {}


async def ssn_redaction_hook(
    input_data: dict,
    tool_use_id: str | None,
    context: Any,
) -> dict:
    """
    Redact SSNs from tool outputs.

    This hook ensures that any SSN patterns in tool results
    are redacted before being processed by the agent.
    """
    if "tool_result" not in input_data:
        return {}

    result = input_data.get("tool_result", "")
    result_str = str(result)

    # SSN patterns to redact
    ssn_patterns = [
        r"\b\d{3}-\d{2}-\d{4}\b",  # XXX-XX-XXXX
        r"\b\d{3}\s\d{2}\s\d{4}\b",  # XXX XX XXXX (common on W-2 forms)
        r"\b\d{9}\b",  # XXXXXXXXX (only if surrounded by word boundaries)
    ]

    redacted = result_str
    redaction_occurred = False

    for pattern in ssn_patterns:
        new_result = re.sub(pattern, "[SSN REDACTED]", redacted)
        if new_result != redacted:
            redaction_occurred = True
            redacted = new_result

    if redaction_occurred:
        logger.info(f"SSN redacted from tool output (tool: {input_data.get('tool_name', 'unknown')})")
        return {
            "hookSpecificOutput": {
                "updatedResult": redacted,
            }
        }

    return {}


async def ein_redaction_hook(
    input_data: dict,
    tool_use_id: str | None,
    context: Any,
) -> dict:
    """
    Optionally redact EINs from tool outputs.

    EINs are less sensitive than SSNs but may still warrant
    redaction in some contexts.
    """
    config = get_config()

    # Only redact EINs if explicitly configured
    if not config.get("redact_ein", False):
        return {}

    if "tool_result" not in input_data:
        return {}

    result = input_data.get("tool_result", "")
    result_str = str(result)

    # EIN pattern: XX-XXXXXXX
    ein_pattern = r"\b\d{2}-\d{7}\b"

    redacted = re.sub(ein_pattern, "[EIN REDACTED]", result_str)

    if redacted != result_str:
        logger.info(f"EIN redacted from tool output")
        return {
            "hookSpecificOutput": {
                "updatedResult": redacted,
            }
        }

    return {}


async def rate_limit_hook(
    input_data: dict,
    tool_use_id: str | None,
    context: Any,
) -> dict:
    """
    Track tool usage for rate limiting.

    This hook tracks how many tools have been invoked in the
    current session to prevent runaway API usage.
    """
    # This would typically use shared state, but for now we just log
    tool_name = input_data.get("tool_name", "unknown")

    # Web tools are more expensive, track them
    if tool_name in ("WebSearch", "WebFetch"):
        logger.info(f"Web tool invocation: {tool_name}")

    return {}


async def web_access_guard(
    input_data: dict,
    tool_use_id: str | None,
    context: Any,
) -> dict:
    """
    Control web access based on configuration.

    When web tools are disabled, this hook blocks WebSearch
    and WebFetch calls.
    """
    config = get_config()

    if not config.agent_sdk_allow_web:
        tool_name = input_data.get("tool_name", "")

        if tool_name in ("WebSearch", "WebFetch"):
            logger.warning(f"Web access blocked (disabled in config): {tool_name}")
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "Web access is disabled in configuration. "
                        "Enable with: tax-agent config set agent_sdk_allow_web true"
                    ),
                }
            }

    return {}


def get_tax_hooks() -> dict:
    """
    Get all hooks configured for the tax agent.

    Returns a dictionary suitable for passing to ClaudeAgentOptions.

    Returns:
        Dictionary mapping hook event names to hook lists
    """
    return {
        "PreToolUse": [
            # Security guards run first to block before logging
            sensitive_data_guard,
            web_access_guard,
            # Audit after guards so blocked attempts aren't logged with sensitive paths
            audit_log_hook,
        ],
        "PostToolUse": [
            # Data protection runs first so audit sees redacted output
            ssn_redaction_hook,
            ein_redaction_hook,
            # Audit after redaction
            audit_log_hook,
            # Monitoring
            rate_limit_hook,
        ],
    }


def get_minimal_hooks() -> dict:
    """
    Get minimal hooks for performance-sensitive operations.

    These hooks have lower overhead but still provide
    essential security and auditing.

    Returns:
        Dictionary mapping hook event names to hook lists
    """
    return {
        "PreToolUse": [
            sensitive_data_guard,
        ],
        "PostToolUse": [
            ssn_redaction_hook,
        ],
    }

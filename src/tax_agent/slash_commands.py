"""Slash command registry for the Agent SDK interactive interface.

Slash commands allow users to access CLI features directly through the
interactive agent interface. They provide structured access to all
tax agent capabilities.

Usage in interactive mode:
    /help - Show available commands
    /status - Show current status
    /documents list - List collected documents
    /analyze - Run tax analysis
    /subagent deduction-finder - Use specialized subagent
"""

from dataclasses import dataclass, field
from typing import Any, Callable
from pathlib import Path


@dataclass
class SlashCommand:
    """Definition of a slash command."""

    name: str
    description: str
    handler: Callable[..., str]
    aliases: list[str] = field(default_factory=list)
    subcommands: dict[str, "SlashCommand"] = field(default_factory=dict)
    requires_init: bool = True
    usage: str = ""


# Registry of all slash commands
_commands: dict[str, SlashCommand] = {}


def register_command(
    name: str,
    description: str,
    handler: Callable[..., str],
    aliases: list[str] | None = None,
    requires_init: bool = True,
    usage: str = "",
) -> SlashCommand:
    """Register a slash command."""
    cmd = SlashCommand(
        name=name,
        description=description,
        handler=handler,
        aliases=aliases or [],
        requires_init=requires_init,
        usage=usage,
    )
    _commands[name] = cmd
    for alias in cmd.aliases:
        _commands[alias] = cmd
    return cmd


def get_command(name: str) -> SlashCommand | None:
    """Get a slash command by name."""
    return _commands.get(name.lstrip("/"))


def list_commands() -> list[SlashCommand]:
    """List all unique slash commands."""
    seen = set()
    result = []
    for cmd in _commands.values():
        if cmd.name not in seen:
            seen.add(cmd.name)
            result.append(cmd)
    return sorted(result, key=lambda c: c.name)


def get_completions(partial: str) -> list[str]:
    """
    Get command completions for partial input.

    Args:
        partial: Partial command text (with or without leading /)

    Returns:
        List of matching command names with /
    """
    text = partial.lstrip("/").lower()
    completions = []

    for cmd in list_commands():
        if cmd.name.lower().startswith(text):
            completions.append(f"/{cmd.name}")
        for alias in cmd.aliases:
            if alias.lower().startswith(text) and f"/{alias}" not in completions:
                completions.append(f"/{alias}")

    return sorted(completions)


def get_all_command_names() -> list[str]:
    """Get all command names including aliases, prefixed with /."""
    names = set()
    for cmd in list_commands():
        names.add(f"/{cmd.name}")
        for alias in cmd.aliases:
            names.add(f"/{alias}")
    return sorted(names)


def parse_slash_command(input_text: str) -> tuple[str | None, list[str]]:
    """
    Parse a slash command from input text.

    Returns:
        Tuple of (command_name, args) or (None, []) if not a slash command
    """
    text = input_text.strip()
    if not text.startswith("/"):
        return None, []

    parts = text[1:].split()
    if not parts:
        return None, []

    return parts[0], parts[1:]


def _find_similar_commands(name: str, threshold: float = 0.5) -> list[str]:
    """Find similar command names for suggestions."""
    from difflib import SequenceMatcher

    name_lower = name.lower()
    suggestions = []

    for cmd in list_commands():
        # Check main command name
        ratio = SequenceMatcher(None, name_lower, cmd.name.lower()).ratio()
        if ratio >= threshold:
            suggestions.append((ratio, f"/{cmd.name}"))

        # Check aliases too
        for alias in cmd.aliases:
            ratio = SequenceMatcher(None, name_lower, alias.lower()).ratio()
            if ratio >= threshold:
                suggestions.append((ratio, f"/{alias}"))

    # Sort by similarity (highest first) and return top 3
    suggestions.sort(reverse=True, key=lambda x: x[0])
    return [s[1] for s in suggestions[:3]]


async def execute_slash_command(
    command_name: str,
    args: list[str],
    context: dict[str, Any] | None = None,
) -> str:
    """Execute a slash command and return the result."""
    cmd = get_command(command_name)
    if not cmd:
        # Suggest similar commands
        similar = _find_similar_commands(command_name)
        if similar:
            suggestions = ", ".join(similar)
            return f"✗ Unknown command: /{command_name}\n\n**Did you mean:** {suggestions}\n\nType `/help` for all commands."
        return f"✗ Unknown command: /{command_name}. Type `/help` for available commands."

    from tax_agent.config import get_config
    config = get_config()

    if cmd.requires_init and not config.is_initialized:
        return "Tax agent not initialized. Please run 'tax-agent init' first."

    try:
        result = cmd.handler(args, context or {})
        if isinstance(result, str):
            return result
        return str(result)
    except Exception as e:
        return f"Error executing /{command_name}: {str(e)}"


# ============================================================================
# Command Handlers
# ============================================================================

def cmd_start(args: list[str], context: dict) -> str:
    """Guide users through the three main workflows."""
    from tax_agent.storage.database import get_database
    from tax_agent.config import get_config
    from tax_agent.session import get_session_manager

    config = get_config()
    db = get_database()
    docs = db.get_documents()
    session = get_session_manager()

    lines = ["# Tax Agent - Choose Your Task\n"]

    lines.append("## 1. Prepare a Tax Return (`/prep`)\n")
    lines.append("Upload documents, analyze, find deductions\n")
    lines.append("```")
    lines.append("/collect ~/Documents/W2.pdf   # Add documents")
    lines.append("/analyze                       # Get analysis")
    lines.append("/optimize                      # Find deductions")
    lines.append("```\n")

    lines.append("## 2. Review a Filed Return (`/review <file>`)\n")
    lines.append("Check for errors, missed deductions, amendments\n")
    lines.append("```")
    lines.append("/review ~/Documents/2024_1040.pdf")
    lines.append("```\n")

    lines.append("## 3. Tax Planning (`/planning`)\n")
    lines.append("Retirement, scenarios, long-term strategy\n")
    lines.append("```")
    lines.append("What if I convert to Roth?")
    lines.append("How can I reduce taxes next year?")
    lines.append("```\n")

    # Show current state
    lines.append("---\n")
    mode_info = session.mode_info
    lines.append(f"**Current Mode:** {mode_info['name']} - {mode_info['description']}")
    lines.append(f"**Tax Year:** {config.tax_year} | **State:** {config.state or 'Not set'}")
    lines.append(f"**Documents:** {len(docs)} collected\n")

    lines.append("Type a command or describe what you want to do.")
    lines.append("Use `/mode` to see your current mode or switch modes.")

    return "\n".join(lines)


def cmd_help(args: list[str], context: dict) -> str:
    """Show available slash commands."""
    commands = list_commands()

    lines = ["# Available Slash Commands\n"]

    lines.append("**New here?** Try `/start` for a guided walkthrough.\n")

    # Group by category
    categories = {
        "General": ["help", "status", "start"],
        "Modes": ["mode", "prep", "review", "planning"],
        "Documents": ["documents", "collect", "find"],
        "Analysis": ["analyze", "optimize", "chat"],
        "AI Features": ["subagent", "subagents", "validate", "audit"],
        "Google Drive": ["drive"],
        "Memory": ["memory", "forget"],
        "Configuration": ["config", "year", "state"],
    }

    for category, cmd_names in categories.items():
        category_cmds = [c for c in commands if c.name in cmd_names]
        if category_cmds:
            lines.append(f"\n## {category}\n")
            for cmd in category_cmds:
                usage = f" {cmd.usage}" if cmd.usage else ""
                aliases = f" (aliases: {', '.join('/' + a for a in cmd.aliases)})" if cmd.aliases else ""
                lines.append(f"- **/{cmd.name}**{usage} - {cmd.description}{aliases}")

    # Show any uncategorized commands
    all_categorized = set(sum(categories.values(), []))
    uncategorized = [c for c in commands if c.name not in all_categorized]
    if uncategorized:
        lines.append("\n## Other\n")
        for cmd in uncategorized:
            lines.append(f"- **/{cmd.name}** - {cmd.description}")

    return "\n".join(lines)


def cmd_status(args: list[str], context: dict) -> str:
    """Show current tax agent status."""
    from tax_agent.config import get_config, AI_PROVIDER_AWS_BEDROCK

    config = get_config()

    lines = ["# Tax Agent Status\n"]

    lines.append(f"- **Initialized:** {'✓ Yes' if config.is_initialized else '✗ No'}")
    lines.append(f"- **Tax Year:** {config.tax_year}")
    lines.append(f"- **State:** {config.state or 'Not set'}")
    lines.append(f"- **AI Provider:** {config.ai_provider}")
    lines.append(f"- **Model:** {config.get('model', 'claude-sonnet-4-5')}")
    lines.append(f"- **Agent SDK:** {'✓ Enabled' if config.use_agent_sdk else 'Disabled'}")

    if config.ai_provider == AI_PROVIDER_AWS_BEDROCK:
        lines.append(f"- **AWS Region:** {config.aws_region}")

    # Show document count and guidance
    try:
        from tax_agent.storage.database import get_database
        db = get_database()
        docs = db.get_documents()
        doc_count = len(docs)
        lines.append(f"- **Documents Collected:** {doc_count}")

        # Show document years breakdown if multiple years
        if doc_count > 0:
            years = {}
            for doc in docs:
                y = doc.tax_year
                years[y] = years.get(y, 0) + 1

            if len(years) == 1:
                year = list(years.keys())[0]
                if year != config.tax_year:
                    lines.append(f"- **Document Year:** {year} ⚠️ (config set to {config.tax_year})")
            elif len(years) > 1:
                year_summary = ", ".join(f"{y}: {c}" for y, c in sorted(years.items()))
                lines.append(f"- **Document Years:** {year_summary}")

        # Empty state guidance
        if doc_count == 0:
            lines.append("\n## Get Started\n")
            lines.append("No documents collected yet. Here's how to begin:\n")
            lines.append("1. `/find` - Search for tax documents on your computer")
            lines.append("2. `/collect <file>` - Add a tax document")
            lines.append("3. `/analyze` - Analyze your tax situation\n")
            lines.append("**Tip:** Try `/find ~/Downloads` to search your Downloads folder")
        elif doc_count > 0:
            lines.append("\n## Next Steps\n")
            lines.append("- `/analyze` - Get a full tax analysis")
            lines.append("- `/optimize` - Find missed deductions")
            lines.append("- `/documents` - View collected documents")
    except Exception:
        lines.append("- **Documents Collected:** (unavailable)")

    return "\n".join(lines)


def cmd_documents(args: list[str], context: dict) -> str:
    """List or manage collected documents."""
    from tax_agent.storage.database import get_database

    subcommand = args[0] if args else "list"

    if subcommand == "list":
        db = get_database()
        docs = db.get_documents()

        if not docs:
            return "No documents collected yet. Use `/collect <path>` to add documents."

        lines = ["# Collected Documents\n"]
        for doc in docs:
            doc_type = doc.document_type
            issuer = doc.issuer_name
            year = doc.tax_year
            lines.append(f"- **{doc_type}** from {issuer} ({year}) `{doc.id[:8]}...`")

        return "\n".join(lines)

    elif subcommand == "show":
        if len(args) < 2:
            return "Usage: /documents show <document_id>"
        doc_id = args[1]
        db = get_database()
        doc = db.get_document(doc_id)
        if not doc:
            return f"Document not found: {doc_id}"

        return f"""# Document Details

- **ID:** {doc.id}
- **Type:** {doc.document_type}
- **Issuer:** {doc.issuer_name}
- **Tax Year:** {doc.tax_year}
- **Confidence:** {doc.confidence_score:.0%}
- **Needs Review:** {'Yes' if doc.needs_review else 'No'}
- **File:** {doc.file_path or 'N/A'}
"""

    elif subcommand == "delete":
        if len(args) < 2:
            return "Usage: /documents delete <document_id>"
        doc_id = args[1]
        db = get_database()

        # Get document details first
        doc = db.get_document(doc_id)
        if not doc:
            return f"✗ Document not found: {doc_id}"

        # Show what will be deleted and require confirmation
        doc_type = doc.document_type
        issuer = doc.issuer_name

        # Check for --force flag to skip confirmation
        if "--force" in args or "-f" in args:
            db.delete_document(doc_id)
            return f"✓ Deleted: {doc_type} from {issuer}"

        return (
            f"⚠️ **Confirm deletion**\n\n"
            f"Document: **{doc_type}** from {issuer}\n"
            f"ID: `{doc_id}`\n\n"
            f"To confirm, run: `/documents delete {doc_id} --force`"
        )

    elif subcommand == "purge":
        db = get_database()
        docs = db.get_documents()
        count = len(docs)

        if count == 0:
            return "No documents to purge."

        # Parse --year option for selective purge
        year = None
        if "--year" in args:
            idx = args.index("--year")
            if idx + 1 < len(args):
                try:
                    year = int(args[idx + 1])
                    # Recount for specific year
                    docs = db.get_documents(tax_year=year)
                    count = len(docs)
                    if count == 0:
                        return f"No documents found for tax year {year}."
                except ValueError:
                    return f"✗ Invalid year: {args[idx + 1]}"

        # Check for --force flag to skip confirmation
        if "--force" in args or "-f" in args:
            deleted = db.clear_documents(tax_year=year)
            year_msg = f" for {year}" if year else ""
            return f"✓ Purged {deleted} document(s){year_msg}"

        # Show confirmation prompt
        year_msg = f" for tax year {year}" if year else ""
        confirm_cmd = f"/documents purge{f' --year {year}' if year else ''} --force"
        return (
            f"⚠️ **Confirm purge**\n\n"
            f"This will delete **{count} document(s)**{year_msg}.\n\n"
            f"To confirm, run: `{confirm_cmd}`"
        )

    else:
        return f"Unknown subcommand: {subcommand}. Use 'list', 'show', 'delete', or 'purge'."


def cmd_collect(args: list[str], context: dict) -> str:
    """Collect a tax document."""
    if not args:
        return "Usage: /collect <file_path> [--year YEAR]\n\nExample: /collect ~/Downloads/w2.pdf --year 2024"

    file_path = Path(args[0]).expanduser()
    year = None

    # Parse --year option
    if "--year" in args:
        idx = args.index("--year")
        if idx + 1 < len(args):
            try:
                year = int(args[idx + 1])
            except ValueError:
                return f"Invalid year: {args[idx + 1]}"

    if not file_path.exists():
        return f"✗ File not found: {file_path}\n\n**Tip:** Use `/find` to search for tax documents"

    from tax_agent.collectors.document_classifier import get_document_collector
    from tax_agent.config import get_config

    config = get_config()
    config_year = config.tax_year

    collector = get_document_collector()
    result = collector.process_file(file_path, tax_year=year)

    if isinstance(result, Exception):
        return f"✗ Error processing file: {result}"

    doc = result

    # Check if document year differs from config year
    year_notice = ""
    if doc.tax_year != config_year:
        year_notice = (
            f"\n\n**Note:** Document is for tax year {doc.tax_year}, "
            f"but your config is set to {config_year}.\n"
            f"Update with: `/year {doc.tax_year}`"
        )

    return (
        f"# ✓ Document Collected\n\n"
        f"- **Type:** {doc.document_type}\n"
        f"- **Issuer:** {doc.issuer_name}\n"
        f"- **Tax Year:** {doc.tax_year}\n"
        f"- **Confidence:** {doc.confidence:.0%}"
        f"{year_notice}\n\n"
        f"**Next:** `/analyze` to see tax implications or `/collect` to add more documents"
    )


def cmd_analyze(args: list[str], context: dict) -> str:
    """Analyze tax situation based on collected documents."""
    from tax_agent.agent_compat import get_compatible_agent
    from tax_agent.storage.database import get_database
    from tax_agent.profile import get_profile

    storage = get_database()
    profile = get_profile()

    docs = storage.get_documents()
    if not docs:
        return "No documents collected. Use `/collect <path>` to add tax documents first."

    # Build documents summary
    doc_summary_lines = []
    for doc in docs:
        doc_type = doc.document_type
        issuer = doc.issuer_name
        if doc.extracted_data:
            import json
            data = json.dumps(doc.extracted_data, indent=2)
            doc_summary_lines.append(f"## {doc_type} from {issuer}\n{data}")
        else:
            doc_summary_lines.append(f"## {doc_type} from {issuer}")

    documents_summary = "\n\n".join(doc_summary_lines)
    taxpayer_info = profile.to_string() if profile else "No profile configured"

    agent = get_compatible_agent()

    # Use streaming if SDK is available
    if agent.is_sdk_enabled:
        return "[Streaming analysis... please wait]"

    result = agent.analyze_tax_implications(documents_summary, taxpayer_info)
    return result


def cmd_optimize(args: list[str], context: dict) -> str:
    """Find deduction and credit optimization opportunities."""
    from tax_agent.agent_compat import get_compatible_agent
    from tax_agent.storage.database import get_database

    storage = get_database()
    docs = storage.get_documents()

    if not docs:
        return "No documents collected. Use `/collect <path>` to add tax documents first."

    agent = get_compatible_agent()

    # Use the deduction-finder subagent if SDK is enabled
    if agent.is_sdk_enabled and hasattr(agent, 'sdk_agent'):
        from tax_agent.subagents import get_subagent
        subagent = get_subagent("deduction-finder")
        if subagent:
            return f"[Invoking deduction-finder subagent... please wait]\n\n{subagent.description}"

    return "[Running optimization analysis... please wait]"


def cmd_subagents(args: list[str], context: dict) -> str:
    """List available specialized subagents."""
    from tax_agent.subagents import list_subagents

    subagents = list_subagents()

    lines = ["# Specialized Tax Subagents\n"]
    lines.append("Use `/subagent <name>` to invoke a subagent with a specific task.\n")

    for agent in subagents:
        lines.append(f"- **{agent['name']}** - {agent['description']}")

    lines.append("\n## Example")
    lines.append("```")
    lines.append("/subagent deduction-finder Find all missed deductions for my situation")
    lines.append("```")

    return "\n".join(lines)


def cmd_subagent(args: list[str], context: dict) -> str:
    """Invoke a specialized subagent."""
    if not args:
        return "Usage: /subagent <name> <prompt>\n\nUse `/subagents` to see available subagents."

    from tax_agent.subagents import get_subagent

    name = args[0]
    prompt = " ".join(args[1:]) if len(args) > 1 else ""

    subagent = get_subagent(name)
    if not subagent:
        return f"Unknown subagent: {name}. Use `/subagents` to see available subagents."

    if not prompt:
        return f"Please provide a task for the {name} subagent.\n\nExample: /subagent {name} Analyze my RSU transactions"

    return f"[Invoking {name} subagent: {subagent.description}]\n\nProcessing: {prompt}"


def cmd_validate(args: list[str], context: dict) -> str:
    """Cross-validate collected documents."""
    from tax_agent.agent_compat import get_compatible_agent
    from tax_agent.storage.database import get_database

    storage = get_database()
    docs = storage.get_documents()

    if len(docs) < 2:
        return "Need at least 2 documents for cross-validation."

    agent = get_compatible_agent()
    result = agent.validate_documents_cross_reference(docs)

    import json
    return f"# Document Validation\n\n```json\n{json.dumps(result, indent=2)}\n```"


def cmd_audit(args: list[str], context: dict) -> str:
    """Assess audit risk based on tax data."""
    from tax_agent.agent_compat import get_compatible_agent
    from tax_agent.storage.database import get_database

    storage = get_database()
    docs = storage.get_documents()

    if not docs:
        return "No documents collected for audit risk assessment."

    agent = get_compatible_agent()

    # Use compliance-auditor subagent if SDK is enabled
    if agent.is_sdk_enabled:
        return "[Using compliance-auditor subagent for detailed audit risk analysis...]"

    return "[Running audit risk assessment...]"


def cmd_plan(args: list[str], context: dict) -> str:
    """Generate tax planning recommendations."""
    from tax_agent.agent_compat import get_compatible_agent
    from tax_agent.storage.database import get_database
    from tax_agent.profile import get_profile

    storage = get_database()
    profile = get_profile()
    docs = storage.get_documents()

    if not docs:
        return "No documents collected for tax planning."

    if not profile:
        return "Please set up your profile first for personalized tax planning."

    return "[Generating tax planning recommendations...]"


def cmd_review(args: list[str], context: dict) -> str:
    """Review a completed tax return."""
    from tax_agent.session import get_session_manager
    from tax_agent.models.mode import AgentMode

    # Switch to REVIEW mode
    session = get_session_manager()
    was_different_mode = session.current_mode != AgentMode.REVIEW
    session.switch_mode(AgentMode.REVIEW, silent=True)

    if not args:
        lines = [
            "# ✓ REVIEW Mode\n",
            "_Reviewing completed tax returns_\n",
            "## Usage",
            "```",
            "/review ~/Documents/2024_1040.pdf",
            "/review ~/Documents/return.pdf --year 2023",
            "```\n",
            "## What I'll Check",
            "- Errors and miscalculations",
            "- Missed deductions and credits",
            "- Amounts vs source documents",
            "- Amendment opportunities\n",
            "Provide a tax return file to begin review."
        ]
        return "\n".join(lines)

    file_path = Path(args[0]).expanduser()

    if not file_path.exists():
        return f"✗ File not found: {file_path}"

    # Parse --year option
    from tax_agent.config import get_config
    config = get_config()
    year = config.tax_year

    if "--year" in args:
        idx = args.index("--year")
        if idx + 1 < len(args):
            try:
                year = int(args[idx + 1])
            except ValueError:
                return f"✗ Invalid year: {args[idx + 1]}"

    try:
        from tax_agent.reviewers.error_checker import ReturnReviewer

        reviewer = ReturnReviewer(year)
        review_result = reviewer.review_return(file_path)

        # Save review context to session for chat follow-up
        session.update_context("return_file", str(file_path))
        session.update_context("findings_count", len(review_result.findings))
        session.update_context("review_id", review_result.id)
        session.update_context("overall_assessment", review_result.overall_assessment)

        # Store the raw review text for chat context
        if reviewer._last_review_text:
            session.update_context("review_analysis", reviewer._last_review_text)

        # Store findings summary for quick reference
        findings_summary = []
        for f in review_result.findings:
            findings_summary.append({
                "severity": f.severity.value,
                "title": f.title,
                "description": f.description[:200],
            })
        session.update_context("findings_summary", findings_summary)

        # Build response
        mode_notice = "_Switched to REVIEW mode_\n\n" if was_different_mode else ""
        lines = [f"{mode_notice}# ✓ Tax Return Review Complete\n"]
        lines.append(f"**Tax Year:** {review_result.return_summary.tax_year}")
        lines.append(f"**Documents Checked:** {len(review_result.source_documents_checked)}")
        lines.append(f"**Findings:** {len(review_result.findings)}\n")

        if review_result.findings:
            # Group by severity
            errors = [f for f in review_result.findings if f.severity.value == "error"]
            warnings = [f for f in review_result.findings if f.severity.value == "warning"]
            suggestions = [f for f in review_result.findings if f.severity.value == "suggestion"]

            if errors:
                lines.append("## Errors (must fix)\n")
                for f in errors:
                    impact = f" (${f.potential_impact:,.0f})" if f.potential_impact else ""
                    lines.append(f"- **{f.title}**: {f.description}{impact}")

            if warnings:
                lines.append("\n## Warnings (should verify)\n")
                for f in warnings:
                    lines.append(f"- **{f.title}**: {f.description}")

            if suggestions:
                lines.append("\n## Suggestions\n")
                for f in suggestions[:5]:  # Limit to 5
                    lines.append(f"- {f.description}")
        else:
            lines.append("**No issues found!** Your return looks good.")

        return "\n".join(lines)

    except Exception as e:
        return f"✗ Error reviewing return: {e}"


def cmd_config(args: list[str], context: dict) -> str:
    """View or change configuration."""
    from tax_agent.config import get_config

    config = get_config()

    if not args:
        # Show current config
        import json
        return f"# Current Configuration\n\n```json\n{json.dumps(config.to_dict(), indent=2)}\n```"

    subcommand = args[0]

    if subcommand == "get" and len(args) > 1:
        key = args[1]
        value = config.get(key)
        return f"**{key}:** {value}"

    elif subcommand == "set" and len(args) > 2:
        key = args[1]
        value = args[2]

        # Type conversion for known keys
        try:
            if key in ("tax_year", "agent_sdk_max_turns"):
                value = int(value)
            elif key in ("use_agent_sdk", "agent_sdk_allow_web", "auto_redact_ssn"):
                value = value.lower() in ("true", "1", "yes")

            config.set(key, value)
            return f"✓ Set **{key}** to `{value}`"
        except (ValueError, TypeError) as e:
            return f"✗ Invalid value for {key}: {value}"

    else:
        return "Usage:\n- `/config` - Show all settings\n- `/config get <key>` - Get a value\n- `/config set <key> <value>` - Set a value"


def cmd_year(args: list[str], context: dict) -> str:
    """Set or show the tax year."""
    from tax_agent.config import get_config

    config = get_config()

    if not args:
        return f"Current tax year: **{config.tax_year}**"

    try:
        year = int(args[0])
        if year < 2000 or year > 2100:
            return f"✗ Invalid year: {args[0]} (use a year between 2000-2100)"
        config.tax_year = year
        return f"✓ Tax year set to **{year}**"
    except ValueError:
        return f"✗ Invalid year: {args[0]} (use a 4-digit year like 2024)"


def cmd_state(args: list[str], context: dict) -> str:
    """Set or show the state."""
    from tax_agent.config import get_config

    config = get_config()

    if not args:
        state_val = config.state or "Not set"
        return f"Current state: **{state_val}**"

    state = args[0].upper()
    if len(state) != 2:
        return f"✗ Invalid state code: {args[0]}. Use two-letter code like CA, NY, TX."

    # Validate it's a real US state code
    valid_states = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC", "PR", "VI", "GU", "AS", "MP"
    }
    if state not in valid_states:
        return f"✗ Unknown state code: {state}. Use a valid US state like CA, NY, TX."

    config.state = state
    return f"✓ State set to **{state}**"


def cmd_find(args: list[str], context: dict) -> str:
    """Find tax documents on your system."""
    from pathlib import Path

    search_dir = Path(args[0]).expanduser() if args else Path.home() / "Downloads"

    if not search_dir.exists():
        return f"Directory not found: {search_dir}"

    # Find PDFs and images
    extensions = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"]
    files = []

    for ext in extensions:
        files.extend(search_dir.glob(f"*{ext}"))
        files.extend(search_dir.glob(f"*{ext.upper()}"))

    # Limit results
    files = sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)[:20]

    if not files:
        return f"No tax documents found in {search_dir}"

    lines = [f"# Found Documents in {search_dir}\n"]
    for f in files:
        size_kb = f.stat().st_size / 1024
        lines.append(f"- `{f.name}` ({size_kb:.1f} KB)")

    lines.append(f"\nUse `/collect <path>` to import a document.")

    return "\n".join(lines)


def cmd_chat(args: list[str], context: dict) -> str:
    """Start an interactive chat about taxes."""
    if not args:
        return (
            "# Interactive Tax Chat\n\n"
            "Ask any tax question! For example:\n"
            "- What deductions can I claim as a remote worker?\n"
            "- How does the child tax credit work?\n"
            "- Should I itemize or take the standard deduction?\n\n"
            "Usage: /chat <your question>"
        )

    question = " ".join(args)
    return f"[Processing your question: {question}...]"


# ============================================================================
# Google Drive Commands
# ============================================================================

def cmd_drive(args: list[str], context: dict) -> str:
    """Google Drive integration commands."""
    from tax_agent.config import get_config

    config = get_config()

    if not args:
        # Show Drive status and help
        is_configured = config.has_google_drive_configured()

        if is_configured:
            return (
                "# Google Drive Integration\n\n"
                "**Status:** ✓ Connected\n\n"
                "## Commands\n"
                "- `/drive list` - List folders in your Drive\n"
                "- `/drive files <folder_id>` - List files in a folder\n"
                "- `/drive collect <folder_id>` - Import documents from a folder\n"
                "- `/drive auth --revoke` - Disconnect from Google Drive\n"
            )
        else:
            return (
                "# Google Drive Integration\n\n"
                "**Status:** ✗ Not connected\n\n"
                "## Setup Instructions\n"
                "1. Create a Google Cloud project at https://console.cloud.google.com\n"
                "2. Enable the Google Drive API\n"
                "3. Create OAuth credentials (Desktop app type)\n"
                "4. Download the credentials JSON file\n"
                "5. Run: `tax-agent drive auth --setup <path-to-credentials.json>`\n\n"
                "See docs/GOOGLE_DRIVE_SETUP.md for detailed instructions."
            )

    subcommand = args[0].lower()

    if subcommand == "list":
        return _drive_list_folders(args[1:])
    elif subcommand == "files":
        return _drive_list_files(args[1:])
    elif subcommand == "collect":
        return _drive_collect(args[1:])
    elif subcommand == "auth":
        return _drive_auth(args[1:])
    else:
        return f"✗ Unknown drive subcommand: {subcommand}\n\nUse `/drive` for help."


def _drive_auth(args: list[str]) -> str:
    """Handle drive auth subcommand."""
    from tax_agent.config import get_config

    config = get_config()

    if "--revoke" in args or "-r" in args:
        config.clear_google_credentials()
        return "✓ Google Drive credentials have been removed."

    # Check if already authenticated
    if config.has_google_drive_configured():
        return (
            "✓ Already connected to Google Drive.\n\n"
            "To re-authenticate, run: `tax-agent drive auth`\n"
            "To disconnect, use: `/drive auth --revoke`"
        )

    return (
        "To connect Google Drive, run this command in your terminal:\n\n"
        "```\ntax-agent drive auth --setup <path-to-credentials.json>\n```\n\n"
        "This will open a browser for authorization."
    )


def _drive_list_folders(args: list[str]) -> str:
    """List folders in Google Drive."""
    from tax_agent.config import get_config

    config = get_config()
    if not config.has_google_drive_configured():
        return "✗ Google Drive not connected. Use `/drive` for setup instructions."

    try:
        from tax_agent.collectors.google_drive import GoogleDriveCollector

        collector = GoogleDriveCollector()
        if not collector.is_authenticated():
            return "✗ Google Drive authentication expired. Run: `tax-agent drive auth`"

        parent_id = args[0] if args else "root"
        folders = collector.list_folders(parent_id)

        if not folders:
            return "No folders found."

        lines = ["# Google Drive Folders\n"]
        for folder in folders:
            lines.append(f"- **{folder.name}** `{folder.id}`")

        lines.append(f"\n[dim]Use `/drive files <folder_id>` to see files in a folder[/dim]")
        return "\n".join(lines)

    except Exception as e:
        return f"✗ Error listing folders: {e}"


def _drive_list_files(args: list[str]) -> str:
    """List files in a Google Drive folder."""
    if not args:
        return "Usage: `/drive files <folder_id>`\n\nUse `/drive list` to find folder IDs."

    from tax_agent.config import get_config

    config = get_config()
    if not config.has_google_drive_configured():
        return "✗ Google Drive not connected. Use `/drive` for setup instructions."

    try:
        from tax_agent.collectors.google_drive import GoogleDriveCollector

        collector = GoogleDriveCollector()
        if not collector.is_authenticated():
            return "✗ Google Drive authentication expired. Run: `tax-agent drive auth`"

        folder_id = args[0]
        files = collector.list_files(folder_id)

        if not files:
            return "No supported files found in this folder."

        lines = ["# Files in Folder\n"]
        for f in files:
            file_type = "Google Doc" if f.is_google_doc else f.mime_type.split("/")[-1].upper()
            lines.append(f"- **{f.name}** ({file_type}) `{f.id}`")

        lines.append(f"\n[dim]Use `/drive collect {folder_id}` to import these documents[/dim]")
        return "\n".join(lines)

    except Exception as e:
        return f"✗ Error listing files: {e}"


def _drive_collect(args: list[str]) -> str:
    """Collect documents from a Google Drive folder."""
    if not args:
        return (
            "Usage: `/drive collect <folder_id> [--year YEAR]`\n\n"
            "Use `/drive list` to find folder IDs."
        )

    from tax_agent.config import get_config

    config = get_config()
    if not config.has_google_drive_configured():
        return "✗ Google Drive not connected. Use `/drive` for setup instructions."

    folder_id = args[0]

    # Parse --year option
    year = None
    if "--year" in args:
        idx = args.index("--year")
        if idx + 1 < len(args):
            try:
                year = int(args[idx + 1])
            except ValueError:
                return f"✗ Invalid year: {args[idx + 1]}"

    return (
        f"[Collecting documents from Google Drive folder: {folder_id}]\n\n"
        f"For full progress output, run in terminal:\n"
        f"```\ntax-agent drive collect {folder_id}"
        f"{f' --year {year}' if year else ''}\n```"
    )


# ============================================================================
# Mode Commands
# ============================================================================

def cmd_mode(args: list[str], context: dict) -> str:
    """Switch or show current operating mode."""
    from tax_agent.session import get_session_manager
    from tax_agent.models.mode import AgentMode, MODE_INFO

    session = get_session_manager()

    if not args:
        # Show current mode
        return session.get_mode_summary()

    mode_arg = args[0].lower()

    mode_map = {
        "prep": AgentMode.PREP,
        "review": AgentMode.REVIEW,
        "planning": AgentMode.PLANNING,
        "plan": AgentMode.PLANNING,  # Alias
    }

    if mode_arg not in mode_map:
        modes_list = ", ".join(mode_map.keys())
        return f"✗ Unknown mode: {mode_arg}\n\nAvailable modes: {modes_list}"

    mode = mode_map[mode_arg]
    session.switch_mode(mode)
    msg = session.pop_switch_message()

    return f"✓ {msg}" if msg else f"✓ Switched to {mode.value} mode"


def cmd_prep(args: list[str], context: dict) -> str:
    """Enter PREP mode for preparing a new tax return."""
    from tax_agent.session import get_session_manager
    from tax_agent.models.mode import AgentMode
    from tax_agent.storage.database import get_database

    session = get_session_manager()
    session.switch_mode(AgentMode.PREP)

    db = get_database()
    docs = db.get_documents()
    doc_count = len(docs)

    lines = [
        "# ✓ PREP Mode\n",
        "_Preparing a new tax return_\n",
        "## Focus",
        "- Collect ALL relevant tax documents",
        "- Find every possible deduction and credit",
        "- Maximize your refund or minimize taxes owed\n",
        "## Commands",
        "- `/collect <file>` - Add a tax document",
        "- `/find [dir]` - Search for documents",
        "- `/analyze` - Analyze your tax situation",
        "- `/optimize` - Find missed deductions\n",
    ]

    if doc_count > 0:
        lines.append(f"**Documents collected:** {doc_count}")
        lines.append("\n**Next step:** `/analyze` to see your tax situation")
    else:
        lines.append("**Next step:** `/collect` to add your first document")

    return "\n".join(lines)


def cmd_planning(args: list[str], context: dict) -> str:
    """Enter PLANNING mode for long-term tax strategy."""
    from tax_agent.session import get_session_manager
    from tax_agent.models.mode import AgentMode

    session = get_session_manager()
    session.switch_mode(AgentMode.PLANNING)

    lines = [
        "# ✓ PLANNING Mode\n",
        "_Long-term tax planning and strategy_\n",
        "## Focus",
        "- Multi-year tax optimization",
        "- Retirement planning (Roth conversions, 401k, RMDs)",
        "- Scenario analysis (\"What if I...\")",
        "- Life event planning\n",
        "## Example Questions",
        "- \"What if I max out my 401k?\"",
        "- \"Should I convert to Roth IRA?\"",
        "- \"What's the tax impact of selling my RSUs?\"",
        "- \"How can I reduce taxes if I'm retiring next year?\"\n",
        "**Just ask** any tax planning question!"
    ]

    return "\n".join(lines)


# ============================================================================
# Memory Commands
# ============================================================================

def cmd_memory(args: list[str], context: dict) -> str:
    """View or manage stored memories."""
    from tax_agent.storage.database import get_database
    from tax_agent.memory import MemoryManager

    db = get_database()
    memory_mgr = MemoryManager(db)

    if not args:
        # Show all memories
        memories = memory_mgr.get_all_memories()

        if not memories:
            return (
                "# Stored Memories\n\n"
                "No memories stored yet. As we chat, I'll remember important facts about you.\n\n"
                "You can also manually add memories:\n"
                "- `/memory add I'm self-employed`\n"
                "- `/memory add I work from home`"
            )

        lines = ["# Stored Memories\n"]

        # Group by type
        from tax_agent.models.memory import MemoryType
        by_type: dict[str, list] = {}
        for mem in memories:
            t = mem.memory_type
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(mem)

        type_labels = {
            MemoryType.FACT: "Facts",
            MemoryType.PREFERENCE: "Preferences",
            MemoryType.INSIGHT: "Insights",
            MemoryType.DECISION: "Decisions",
        }

        for mem_type, label in type_labels.items():
            if mem_type in by_type:
                lines.append(f"\n## {label}\n")
                for mem in by_type[mem_type]:
                    source_tag = " (auto)" if mem.source == "auto" else ""
                    lines.append(f"- {mem.content} `{mem.id[:8]}`{source_tag}")

        lines.append("\n---")
        lines.append("Use `/forget <id>` to remove a memory")
        lines.append("Use `/memory clear` to reset all")

        return "\n".join(lines)

    subcommand = args[0].lower()

    if subcommand == "add":
        if len(args) < 2:
            return "Usage: `/memory add <fact to remember>`\n\nExample: `/memory add I'm self-employed`"

        content = " ".join(args[1:])
        memory = memory_mgr.add_memory(content)
        return f"✓ Remembered: {memory.content}"

    elif subcommand == "clear":
        # Require confirmation
        if "--force" in args or "-f" in args:
            count = memory_mgr.clear_all_memories()
            return f"✓ Cleared {count} memories"

        memories = memory_mgr.get_all_memories()
        count = len(memories)
        if count == 0:
            return "No memories to clear."

        return (
            f"⚠️ **Confirm clear**\n\n"
            f"This will delete **{count} memories**.\n\n"
            f"To confirm, run: `/memory clear --force`"
        )

    else:
        return f"Unknown subcommand: {subcommand}\n\nUse `/memory` to list, `/memory add` to add, `/memory clear` to reset."


def cmd_forget(args: list[str], context: dict) -> str:
    """Delete a specific memory."""
    if not args:
        return "Usage: `/forget <memory_id>`\n\nUse `/memory` to see memory IDs."

    from tax_agent.storage.database import get_database
    from tax_agent.memory import MemoryManager

    db = get_database()
    memory_mgr = MemoryManager(db)

    memory_id = args[0]

    # Try to find and show what will be deleted
    memory = db.get_memory(memory_id)
    if not memory:
        return f"✗ Memory not found: {memory_id}"

    if memory_mgr.delete_memory(memory_id):
        return f"✓ Forgot: {memory.content}"
    else:
        return f"✗ Failed to delete memory: {memory_id}"


# ============================================================================
# Register all commands
# ============================================================================

def _register_all_commands() -> None:
    """Register all slash commands."""
    register_command("help", "Show available commands", cmd_help, ["h", "?"], requires_init=False)
    register_command("start", "Get started - workflow guide", cmd_start, ["guide", "workflow"], requires_init=False)
    register_command("status", "Show current status", cmd_status, ["s"], requires_init=False)
    register_command("documents", "List or manage documents", cmd_documents, ["docs", "d", "doc"], usage="[list|show|delete|purge]")
    register_command("collect", "Collect a tax document", cmd_collect, ["c"], usage="<file_path>")
    register_command("find", "Find tax documents on your system", cmd_find, ["f"], usage="[directory]")
    register_command("analyze", "Analyze tax situation", cmd_analyze, ["a", "analyse", "analysis"])
    register_command("optimize", "Find optimization opportunities", cmd_optimize, ["opt", "o", "optimise"])
    register_command("subagents", "List available subagents", cmd_subagents, requires_init=False)
    register_command("subagent", "Invoke a specialized subagent", cmd_subagent, usage="<name> <prompt>")
    register_command("validate", "Cross-validate documents", cmd_validate, ["v"])
    register_command("audit", "Assess audit risk", cmd_audit, usage="[--thorough]")
    register_command("review", "Review a tax return", cmd_review, usage="[return_file]")
    register_command("config", "View or change settings", cmd_config, ["cfg", "settings"], usage="[get|set] [key] [value]")
    register_command("year", "Set or show tax year", cmd_year, usage="[YEAR]")
    register_command("state", "Set or show state", cmd_state, usage="[STATE]")
    register_command("chat", "Interactive tax chat", cmd_chat, usage="<question>")
    # Mode commands
    register_command("mode", "Show or switch operating mode", cmd_mode, usage="[prep|review|planning]")
    register_command("prep", "Enter PREP mode", cmd_prep, requires_init=False)
    register_command("planning", "Enter PLANNING mode", cmd_planning, ["plan"], requires_init=False)
    # Google Drive integration
    register_command("drive", "Google Drive integration", cmd_drive, ["gdrive"], usage="[list|files|collect|auth]")
    # Memory system
    register_command("memory", "View or manage memories", cmd_memory, ["mem", "remember"], usage="[add|clear]")
    register_command("forget", "Delete a specific memory", cmd_forget, usage="<memory_id>")


# Auto-register on import
_register_all_commands()

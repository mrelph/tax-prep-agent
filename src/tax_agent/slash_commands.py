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

def cmd_help(args: list[str], context: dict) -> str:
    """Show available slash commands."""
    commands = list_commands()

    lines = ["# Available Slash Commands\n"]

    # Group by category
    categories = {
        "General": ["help", "status"],
        "Documents": ["documents", "collect", "find"],
        "Analysis": ["analyze", "optimize", "chat"],
        "AI Features": ["subagent", "subagents", "validate", "audit", "plan", "review"],
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

    else:
        return f"Unknown subcommand: {subcommand}. Use 'list', 'show', or 'delete'."


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

    collector = get_document_collector()
    result = collector.process_file(file_path, tax_year=year)

    if isinstance(result, Exception):
        return f"✗ Error processing file: {result}"

    doc = result
    return (
        f"# ✓ Document Collected\n\n"
        f"- **Type:** {doc.document_type}\n"
        f"- **Issuer:** {doc.issuer_name}\n"
        f"- **Tax Year:** {doc.tax_year}\n"
        f"- **Confidence:** {doc.confidence:.0%}\n\n"
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
        doc_type = doc.get("document_type", "UNKNOWN")
        issuer = doc.get("issuer_name", "Unknown")
        if doc.get("extracted_data"):
            import json
            data = json.dumps(doc["extracted_data"], indent=2)
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
    if not args:
        return "Usage: /review <return_file_path>\n\nExample: /review ~/Documents/2024_1040.pdf"

    file_path = Path(args[0]).expanduser()

    if not file_path.exists():
        return f"File not found: {file_path}"

    return f"[Reviewing tax return: {file_path}...]"


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
# Register all commands
# ============================================================================

def _register_all_commands() -> None:
    """Register all slash commands."""
    register_command("help", "Show available commands", cmd_help, ["h", "?"], requires_init=False)
    register_command("status", "Show current status", cmd_status, ["s"], requires_init=False)
    register_command("documents", "List or manage documents", cmd_documents, ["docs", "d", "doc"], usage="[list|show|delete]")
    register_command("collect", "Collect a tax document", cmd_collect, ["c"], usage="<file_path>")
    register_command("find", "Find tax documents on your system", cmd_find, ["f"], usage="[directory]")
    register_command("analyze", "Analyze tax situation", cmd_analyze, ["a", "analyse", "analysis"])
    register_command("optimize", "Find optimization opportunities", cmd_optimize, ["opt", "o", "optimise"])
    register_command("subagents", "List available subagents", cmd_subagents, requires_init=False)
    register_command("subagent", "Invoke a specialized subagent", cmd_subagent, usage="<name> <prompt>")
    register_command("validate", "Cross-validate documents", cmd_validate, ["v"])
    register_command("audit", "Assess audit risk", cmd_audit, usage="[--thorough]")
    register_command("plan", "Tax planning recommendations", cmd_plan, usage="[--year YEAR]")
    register_command("review", "Review a tax return", cmd_review, usage="<return_file>")
    register_command("config", "View or change settings", cmd_config, ["cfg", "settings"], usage="[get|set] [key] [value]")
    register_command("year", "Set or show tax year", cmd_year, usage="[YEAR]")
    register_command("state", "Set or show state", cmd_state, usage="[STATE]")
    register_command("chat", "Interactive tax chat", cmd_chat, usage="<question>")


# Auto-register on import
_register_all_commands()

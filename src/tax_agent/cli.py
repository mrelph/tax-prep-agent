"""CLI commands for the tax prep agent."""

import asyncio
import sys
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from tax_agent.config import get_config
from tax_agent.env import load_env

# Load .env file early so all env vars are available
load_env()


def async_command(f):
    """Decorator to run async commands with asyncio.run()."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))
    return wrapper


def get_enum_value(value) -> str:
    """Get string value from an enum or return as-is if already a string."""
    if isinstance(value, Enum):
        return value.value
    return str(value) if value else ""


def prompt_export(content: str, default_filename: str, content_type: str = "report") -> None:
    """Prompt user to export content to MD or PDF after an operation."""
    from pathlib import Path
    from tax_agent.exporters import export_to_file

    if Confirm.ask(f"\n[cyan]Export {content_type} to file?[/cyan]", default=False):
        # Ask for format
        format_choice = Prompt.ask(
            "Format",
            choices=["md", "pdf"],
            default="md"
        )

        # Ask for filename
        default_with_ext = f"{default_filename}.{format_choice}"
        filename = Prompt.ask("Filename", default=default_with_ext)

        output_path = Path(filename)
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path

        try:
            result_path = export_to_file(content, output_path, format_choice)
            rprint(f"[green]Exported to: {result_path}[/green]")
        except Exception as e:
            rprint(f"[red]Export failed: {e}[/red]")


def masked_input(prompt: str, mask_char: str = "*") -> str:
    """
    Get password input showing masked characters.

    Args:
        prompt: The prompt to display
        mask_char: Character to show for each typed character

    Returns:
        The entered password
    """
    import termios
    import tty

    rprint(f"{prompt}: ", end="")
    sys.stdout.flush()

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    password = []

    try:
        tty.setraw(fd)
        while True:
            char = sys.stdin.read(1)
            if char in ('\r', '\n'):  # Enter pressed
                break
            elif char == '\x7f':  # Backspace
                if password:
                    password.pop()
                    # Move cursor back, overwrite with space, move back again
                    sys.stdout.write('\b \b')
                    sys.stdout.flush()
            elif char == '\x03':  # Ctrl+C
                raise KeyboardInterrupt
            elif char == '\x15':  # Ctrl+U - toggle visibility
                # Clear current display
                sys.stdout.write('\b' * len(password) + ' ' * len(password) + '\b' * len(password))
                # Show actual password briefly
                sys.stdout.write(''.join(password))
                sys.stdout.flush()
            elif ord(char) >= 32:  # Printable character
                password.append(char)
                sys.stdout.write(mask_char)
                sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    print()  # Newline after password
    return ''.join(password)


def resolve_file_path(file_path: Path, extensions: list[str] | None = None) -> tuple[Path | None, list[Path]]:
    """
    Resolve a file path with smart searching and expansion.

    Handles:
    - ~ expansion for home directory
    - Relative path resolution
    - Glob patterns (*.pdf)
    - Searching common directories if not found

    Args:
        file_path: The path to resolve
        extensions: File extensions to search for (e.g., ['.pdf', '.png'])

    Returns:
        Tuple of (resolved_path, list_of_suggestions)
        resolved_path is None if file not found
    """
    import glob as glob_module

    if extensions is None:
        extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']

    # Expand ~ to home directory
    expanded = Path(str(file_path).replace('~', str(Path.home())))

    # Make absolute
    if not expanded.is_absolute():
        expanded = Path.cwd() / expanded

    # Resolve symlinks and .. components
    try:
        expanded = expanded.resolve()
    except (OSError, RuntimeError):
        pass

    # If it exists, return it
    if expanded.exists():
        return expanded, []

    # Check if it's a glob pattern
    file_str = str(file_path)
    if '*' in file_str or '?' in file_str:
        # Expand ~ in glob pattern too
        glob_pattern = file_str.replace('~', str(Path.home()))
        matches = sorted(glob_module.glob(glob_pattern, recursive=True))
        valid_matches = [Path(m) for m in matches if Path(m).is_file()]
        if valid_matches:
            return valid_matches[0] if len(valid_matches) == 1 else None, valid_matches
        return None, []

    # File not found - search common locations
    suggestions = []
    filename = file_path.name

    # Common tax document locations
    search_dirs = [
        Path.cwd(),
        Path.home() / "Documents",
        Path.home() / "Downloads",
        Path.home() / "Desktop",
        Path.home() / "Documents" / "taxes",
        Path.home() / "Documents" / "Taxes",
        Path.home() / "Documents" / "Tax Documents",
        Path.home() / "Downloads" / "taxes",
    ]

    # Search for the filename in common directories
    for search_dir in search_dirs:
        if search_dir.exists():
            # Exact match
            potential = search_dir / filename
            if potential.exists() and potential not in suggestions:
                suggestions.append(potential)

            # Case-insensitive search
            try:
                for item in search_dir.iterdir():
                    if item.is_file() and item.name.lower() == filename.lower():
                        if item not in suggestions:
                            suggestions.append(item)
            except PermissionError:
                pass

    # Also search for similar files if filename has no extension
    if not file_path.suffix:
        for search_dir in search_dirs[:4]:  # Only search main dirs for partial matches
            if search_dir.exists():
                try:
                    for item in search_dir.iterdir():
                        if item.is_file() and item.suffix.lower() in extensions:
                            if filename.lower() in item.name.lower():
                                if item not in suggestions:
                                    suggestions.append(item)
                except PermissionError:
                    pass

    return None, suggestions[:10]  # Limit to 10 suggestions


def find_tax_documents(directory: Path | None = None, extensions: list[str] | None = None) -> list[Path]:
    """
    Find tax documents in a directory or common locations.

    Args:
        directory: Directory to search (None for common locations)
        extensions: File extensions to include

    Returns:
        List of found document paths
    """
    if extensions is None:
        extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']

    found = []

    if directory:
        search_dirs = [directory]
    else:
        search_dirs = [
            Path.cwd(),
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / "Desktop",
        ]

    for search_dir in search_dirs:
        if search_dir.exists():
            try:
                for item in search_dir.iterdir():
                    if item.is_file() and item.suffix.lower() in extensions:
                        found.append(item)
            except PermissionError:
                pass

    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def _run_agentic_analysis(analyzer, tax_year: int) -> str:
    """
    Run agentic analysis using the Agent SDK with streaming output.

    Args:
        analyzer: TaxAnalyzer instance
        tax_year: Tax year for analysis

    Returns:
        Complete analysis text
    """
    from tax_agent.agent_sdk import get_sdk_agent, sdk_available

    if not sdk_available():
        raise RuntimeError("Agent SDK not installed")

    sdk_agent = get_sdk_agent()
    if not sdk_agent.is_available:
        raise RuntimeError("Agent SDK not available")

    # Build document summary
    documents = analyzer.get_documents()
    doc_summaries = []
    source_dir = None

    for doc in documents:
        from tax_agent.utils import get_enum_value as _get_enum
        from tax_agent.models.documents import DocumentType

        summary = f"- {_get_enum(doc.document_type)} from {doc.issuer_name}"
        if doc.extracted_data:
            if doc.document_type == DocumentType.W2:
                wages = doc.extracted_data.get("box_1", 0)
                withheld = doc.extracted_data.get("box_2", 0)
                summary += f": Wages ${wages:,.2f}, Federal withheld ${withheld:,.2f}"
            elif doc.document_type == DocumentType.FORM_1099_INT:
                interest = doc.extracted_data.get("box_1", 0)
                summary += f": Interest income ${interest:,.2f}"
            elif doc.document_type == DocumentType.FORM_1099_DIV:
                dividends = doc.extracted_data.get("box_1a", 0)
                summary += f": Dividends ${dividends:,.2f}"
        doc_summaries.append(summary)

        if doc.file_path and source_dir is None:
            source_dir = Path(doc.file_path).parent

    documents_text = "\n".join(doc_summaries)
    config = get_config()

    taxpayer_text = f"""
Tax Year: {tax_year}
State: {config.state or 'Not specified'}
"""

    # Run with streaming output
    rprint("[dim]Agent is analyzing with tool access...[/dim]")
    response_parts = []

    async def run_analysis():
        async for chunk in sdk_agent.analyze_documents_async(
            documents_text,
            taxpayer_text,
            source_dir,
        ):
            response_parts.append(chunk)
            # Print chunks as they arrive for feedback
            rprint(f"[dim].[/dim]", end="")

    asyncio.run(run_analysis())
    rprint()  # Newline after progress dots

    return "".join(response_parts)


app = typer.Typer(
    name="tax-agent",
    help="A CLI agent for tax document collection, analysis, and return review.",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option("--version", "-v", help="Show version")] = False,
) -> None:
    """
    Tax Prep Agent - AI-powered tax document analysis.

    Run without arguments to start interactive mode.
    """
    if version:
        rprint("tax-agent version 0.1.0")
        raise typer.Exit()

    # If no command provided, start interactive mode
    if ctx.invoked_subcommand is None:
        _start_interactive_mode()


def _start_interactive_mode() -> None:
    """Start the interactive Agent SDK mode with Claude Code-style UI."""
    from tax_agent.chat import TaxAdvisorChat
    from tax_agent.slash_commands import get_all_command_names

    config = get_config()

    # Check if initialized
    if not config.is_initialized:
        rprint(Panel.fit(
            "[bold yellow]Welcome to Tax Prep Agent![/bold yellow]\n\n"
            "It looks like this is your first time running the agent.\n"
            "Let's get you set up first.",
            title="Setup Required"
        ))
        rprint("\nRun [cyan]tax-agent init[/cyan] to get started.\n")
        raise typer.Exit()

    tax_year = config.tax_year
    advisor = TaxAdvisorChat(tax_year)

    # Get document count for status
    def get_doc_count():
        try:
            from tax_agent.storage.database import get_database
            db = get_database()
            return len(db.get_documents())
        except Exception:
            return 0

    # Print welcome banner
    doc_count = get_doc_count()
    if doc_count == 0:
        welcome_text = (
            "[bold blue]Tax Prep Agent[/bold blue]\n\n"
            "[cyan]/start[/cyan] - Guided walkthrough (recommended)\n"
            "[cyan]/collect[/cyan] - Add tax documents\n"
            "[cyan]/review[/cyan] - Check a completed return\n"
            "[dim]Tab: autocomplete • ↑↓: history • Ctrl+C: exit[/dim]"
        )
    else:
        welcome_text = (
            "[bold blue]Tax Prep Agent[/bold blue]\n\n"
            f"[dim]{doc_count} document{'s' if doc_count != 1 else ''} collected[/dim]\n"
            "Ask a question, or try [cyan]/analyze[/cyan] • [cyan]/help[/cyan]\n"
            "[dim]Tab: autocomplete • ↑↓: history • Ctrl+C: exit[/dim]"
        )
    rprint(Panel.fit(welcome_text, title="Interactive Mode"))
    rprint("")

    # Set up prompt with Claude Code-style features
    try:
        from prompt_toolkit import PromptSession
        from prompt_toolkit.completion import Completer, Completion
        from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
        from prompt_toolkit.history import FileHistory
        from prompt_toolkit.styles import Style
        from prompt_toolkit.formatted_text import HTML

        # Ensure config dir exists for history file
        config.config_dir.mkdir(parents=True, exist_ok=True)
        history_file = config.config_dir / ".command_history"
        history = FileHistory(str(history_file))

        # Custom completer for slash commands
        commands = get_all_command_names()

        class SlashCommandCompleter(Completer):
            """Completer that triggers on / for slash commands."""

            def get_completions(self, document, complete_event):
                text = document.text_before_cursor.lstrip()

                # Only complete if line starts with / or is empty
                if not text or text.startswith('/'):
                    word = text.lstrip('/')
                    for cmd in commands:
                        cmd_name = cmd.lstrip('/')
                        if cmd_name.startswith(word) or not word:
                            # Calculate how much to replace
                            start_pos = -len(text) if text else 0
                            yield Completion(
                                cmd,
                                start_position=start_pos,
                                display=cmd,
                                display_meta=self._get_meta(cmd),
                            )

            def _get_meta(self, cmd):
                """Get command description for display."""
                from tax_agent.slash_commands import get_command
                command = get_command(cmd.lstrip('/'))
                if command:
                    return command.description[:30]
                return ""

        command_completer = SlashCommandCompleter()

        # Style matching Claude Code aesthetic
        style = Style.from_dict({
            'prompt': 'ansigreen bold',
            'bottom-toolbar': 'bg:#1a1a2e #aaaaaa',
            'bottom-toolbar.text': '#aaaaaa',
        })

        # Bottom toolbar showing status (like Claude Code)
        def get_toolbar():
            from tax_agent.session import get_session_manager
            from tax_agent.models.mode import MODE_INFO

            doc_count = get_doc_count()
            state = config.state or "—"

            # Get current agent mode with color
            try:
                session_mgr = get_session_manager(tax_year)
                agent_mode = session_mgr.current_mode
                mode_info = MODE_INFO[agent_mode]
                mode_name = mode_info["name"]
                mode_color = mode_info["color"]
            except Exception:
                mode_name = "PREP"
                mode_color = "#4CAF50"

            return HTML(
                f'<style bg="{mode_color}" fg="white"> {mode_name} </style> │ '
                f'<b>Year:</b> {tax_year} │ '
                f'<b>State:</b> {state} │ '
                f'<b>Docs:</b> {doc_count} │ '
                f'<style bg="#333355"> /help </style>'
            )

        # Create session with all features
        session = PromptSession(
            history=history,
            completer=command_completer,
            auto_suggest=AutoSuggestFromHistory(),
            style=style,
            bottom_toolbar=get_toolbar,
            complete_while_typing=True,
            enable_history_search=True,  # Ctrl+R for reverse search
            mouse_support=False,
        )

        def get_input():
            # Up/Down arrows navigate history, Ctrl+R for search
            return session.prompt("> ")

        has_autocomplete = True

    except ImportError:
        # Fall back to basic input if prompt_toolkit not available
        has_autocomplete = False
        rprint(f"[dim]Tax Year: {tax_year} | State: {config.state or 'Not set'}[/dim]\n")

        def get_input():
            return Prompt.ask("[bold green]>[/bold green]")

    # Main interaction loop
    while True:
        try:
            user_input = get_input()
        except (KeyboardInterrupt, EOFError):
            rprint("\n[dim]Goodbye![/dim]")
            break

        if not user_input.strip():
            continue

        if user_input.lower() in ("quit", "exit", "bye", "q"):
            rprint("[dim]Goodbye! Good luck with your taxes![/dim]")
            break

        if user_input.lower() == "suggest":
            suggestions = advisor.suggest_topics()
            rprint("\n[bold]Suggested topics:[/bold]")
            for s in suggestions:
                rprint(f"  [cyan]• {s}[/cyan]")
            continue

        if user_input.lower() == "reset":
            advisor.reset()
            rprint("[dim]Conversation reset.[/dim]")
            continue

        # Process the input (handles both slash commands and natural language)
        # Fun thinking spinner with tax-themed messages
        import random
        thinking_messages = [
            "Crunching numbers...",
            "Consulting the tax code...",
            "Finding deductions...",
            "Maximizing your refund...",
            "Reading IRS publications...",
            "Checking for credits...",
            "Analyzing your situation...",
            "Looking for savings...",
        ]
        spinner_msg = random.choice(thinking_messages)
        with console.status(f"[bold cyan]{spinner_msg}[/bold cyan]", spinner="dots12"):
            response = advisor.chat(user_input)

        # Render response as markdown for better formatting
        rprint("")
        rprint(Markdown(response))


# Subcommands
documents_app = typer.Typer(help="Manage collected tax documents")
config_app = typer.Typer(help="Manage configuration")
research_app = typer.Typer(help="Research current tax code and rules")
drive_app = typer.Typer(help="Google Drive integration")
ai_app = typer.Typer(help="Advanced AI-powered tax analysis")
context_app = typer.Typer(help="Manage tax context steering document")
app.add_typer(documents_app, name="documents")
app.add_typer(config_app, name="config")
app.add_typer(research_app, name="research")
app.add_typer(drive_app, name="drive")
app.add_typer(ai_app, name="ai")
app.add_typer(context_app, name="context")


@app.command()
def init() -> None:
    """Initialize the tax agent with encryption and API key."""
    from tax_agent.config import AI_PROVIDER_ANTHROPIC, AI_PROVIDER_AWS_BEDROCK

    config = get_config()

    if config.is_initialized:
        if not Confirm.ask(
            "[yellow]Tax agent is already initialized. Re-initialize?[/yellow]"
        ):
            raise typer.Exit()

    rprint(Panel.fit(
        "[bold blue]Tax Prep Agent Setup[/bold blue]\n\n"
        "This will set up encrypted storage for your tax documents.\n"
        "You'll need:\n"
        "  1. A password for encrypting your data\n"
        "  2. API credentials (Anthropic API or AWS Bedrock)",
        title="Welcome"
    ))

    # Get encryption password
    rprint("\n[bold]Enter a password for encrypting your tax data[/bold]")
    rprint("[dim](Ctrl+U to briefly show password)[/dim]")
    password = masked_input("Password")
    password_confirm = masked_input("Confirm password")

    if password != password_confirm:
        rprint("[red]Passwords do not match. Please try again.[/red]")
        raise typer.Exit(1)

    # Choose AI provider
    rprint("\n[bold]Choose your AI provider:[/bold]")
    rprint("  1. Anthropic API (direct)")
    rprint("  2. AWS Bedrock")
    provider_choice = Prompt.ask("Enter choice", choices=["1", "2"], default="1")

    if provider_choice == "2":
        # AWS Bedrock setup
        ai_provider = AI_PROVIDER_AWS_BEDROCK

        rprint("\n[bold]AWS Bedrock Configuration[/bold]")
        rprint("[dim]You can either enter credentials now, or leave blank to use "
               "environment variables / IAM role / AWS CLI profile.[/dim]\n")

        use_explicit_creds = Confirm.ask("Enter AWS credentials manually?", default=False)

        if use_explicit_creds:
            aws_access_key = Prompt.ask("AWS Access Key ID")
            rprint("[dim](Ctrl+U to briefly show key)[/dim]")
            aws_secret_key = masked_input("AWS Secret Access Key")
        else:
            aws_access_key = None
            aws_secret_key = None
            rprint("[dim]Using default AWS credential chain (env vars, IAM role, ~/.aws/credentials)[/dim]")

        aws_region = Prompt.ask("AWS Region", default="us-east-1")

        # Initialize (no spinner - keyring may prompt for password)
        rprint("[cyan]Initializing...[/cyan]")
        config.initialize(password)
        config.set("ai_provider", ai_provider)
        config.set("aws_region", aws_region)
        if aws_access_key and aws_secret_key:
            config.set_aws_credentials(aws_access_key, aws_secret_key)

        rprint("[green]Tax agent initialized with AWS Bedrock![/green]")

    else:
        # Anthropic API setup
        ai_provider = AI_PROVIDER_ANTHROPIC

        rprint("\n[bold]Enter your Anthropic API key[/bold]")
        rprint("[dim](Ctrl+U to briefly show key)[/dim]")
        api_key = masked_input("API Key")

        if not api_key.startswith("sk-"):
            rprint("[yellow]Warning: API key doesn't look like a valid Anthropic key[/yellow]")
            if not Confirm.ask("Continue anyway?"):
                raise typer.Exit(1)

        # Initialize (no spinner - keyring may prompt for password)
        rprint("[cyan]Initializing...[/cyan]")
        config.initialize(password)
        config.set("ai_provider", ai_provider)
        config.set_api_key(api_key)

        rprint("[green]Tax agent initialized with Anthropic API![/green]")

    # Ask for state
    rprint("\n[bold]State Configuration[/bold]")
    rprint("[dim]Your state affects tax calculations and optimization suggestions.[/dim]")

    state_input = Prompt.ask(
        "Enter your state code (e.g., CA, NY, TX) or 'skip' to set later",
        default="skip"
    )

    if state_input.lower() != "skip" and len(state_input) == 2:
        config.set("state", state_input.upper())
        rprint(f"[green]State set to {state_input.upper()}[/green]")
    else:
        rprint("[dim]State not set. You can set it later with: tax-agent config set state XX[/dim]")

    # Ask for tax year
    from datetime import datetime
    current_year = datetime.now().year
    default_tax_year = current_year - 1 if datetime.now().month < 4 else current_year

    tax_year_input = Prompt.ask(
        f"Tax year you're preparing for",
        default=str(default_tax_year)
    )

    try:
        tax_year = int(tax_year_input)
        config.set("tax_year", tax_year)
        rprint(f"[green]Tax year set to {tax_year}[/green]")
    except ValueError:
        rprint(f"[yellow]Invalid year, defaulting to {default_tax_year}[/yellow]")
        config.set("tax_year", default_tax_year)

    rprint(f"\n[bold green]Setup Complete![/bold green]")
    rprint(f"Data directory: {config.data_dir}")
    rprint(f"AI Provider: {ai_provider}")
    rprint(f"Model: {config.get('model', 'claude-sonnet-4-5')}")
    rprint(f"Tax Year: {config.tax_year}")
    rprint(f"State: {config.state or 'Not set'}")
    rprint("\nNext steps:")
    rprint("  1. Collect documents: [cyan]tax-agent collect <file>[/cyan]")
    rprint("  2. Run optimization: [cyan]tax-agent optimize[/cyan]")


@app.command()
def status() -> None:
    """Show the current status of the tax agent."""
    import os
    from tax_agent.config import AI_PROVIDER_AWS_BEDROCK

    config = get_config()

    table = Table(title="Tax Agent Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Initialized", "Yes" if config.is_initialized else "No")
    table.add_row("Tax Year", str(config.tax_year))
    table.add_row("State", config.state or "[dim]Not set[/dim]")

    # AI Provider info
    ai_provider = config.ai_provider
    table.add_row("AI Provider", ai_provider)
    table.add_row("Model", config.get("model", "claude-3-5-sonnet"))

    if ai_provider == AI_PROVIDER_AWS_BEDROCK:
        table.add_row("AWS Region", config.aws_region)
        # Check if credentials are from environment
        if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
            table.add_row("AWS Credentials", "Configured [dim](from env)[/dim]")
        else:
            aws_access, _ = config.get_aws_credentials()
            if aws_access:
                table.add_row("AWS Credentials", "Configured [dim](from keyring)[/dim]")
            else:
                table.add_row("AWS Credentials", "Using default chain")
    else:
        # Check if API key is from environment
        if os.environ.get("ANTHROPIC_API_KEY"):
            table.add_row("API Key", "Configured [dim](from env)[/dim]")
        elif config.get_api_key():
            table.add_row("API Key", "Configured [dim](from keyring)[/dim]")
        else:
            table.add_row("API Key", "[red]Not set[/red]")

    table.add_row("Data Directory", str(config.data_dir))

    console.print(table)

    if not config.is_initialized:
        rprint("\n[yellow]Run 'tax-agent init' to get started.[/yellow]")


@app.command(name="find")
def find_docs(
    directory: Annotated[Optional[Path], typer.Argument(help="Directory to search (default: common locations)")] = None,
    pattern: Annotated[Optional[str], typer.Option("--pattern", "-p", help="Filename pattern to match")] = None,
    limit: Annotated[int, typer.Option("--limit", "-n", help="Maximum files to show")] = 20,
) -> None:
    """Find tax documents (PDFs, images) on your system.

    Searches common locations like Documents, Downloads, and Desktop.
    Use --pattern to filter by filename.

    Examples:
        tax-agent find                    # Search common locations
        tax-agent find ~/taxes            # Search specific directory
        tax-agent find -p w2              # Find files containing 'w2'
        tax-agent find -p "2024"          # Find files with '2024' in name
    """
    import glob as glob_module

    extensions = ['.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.tif']

    # Determine search directories
    if directory:
        resolved_dir = Path(str(directory).replace('~', str(Path.home())))
        if not resolved_dir.is_absolute():
            resolved_dir = Path.cwd() / resolved_dir
        resolved_dir = resolved_dir.resolve()

        if not resolved_dir.exists():
            rprint(f"[red]Directory not found: {directory}[/red]")
            raise typer.Exit(1)

        search_dirs = [resolved_dir]
        rprint(f"[cyan]Searching in: {resolved_dir}[/cyan]\n")
    else:
        search_dirs = [
            Path.cwd(),
            Path.home() / "Documents",
            Path.home() / "Downloads",
            Path.home() / "Desktop",
        ]
        rprint("[cyan]Searching common locations...[/cyan]\n")

    found_files = []
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue

        try:
            for item in search_dir.rglob("*"):
                if item.is_file() and item.suffix.lower() in extensions:
                    # Apply pattern filter if specified
                    if pattern:
                        if pattern.lower() not in item.name.lower():
                            continue
                    found_files.append(item)
        except PermissionError:
            continue

    if not found_files:
        rprint("[yellow]No tax documents found.[/yellow]")
        if pattern:
            rprint(f"[dim]No files matching '{pattern}' with extensions: {', '.join(extensions)}[/dim]")
        else:
            rprint(f"[dim]Looking for files with extensions: {', '.join(extensions)}[/dim]")
        raise typer.Exit(0)

    # Sort by modification time (newest first)
    found_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    # Limit results
    if len(found_files) > limit:
        rprint(f"[dim]Showing {limit} of {len(found_files)} files (use --limit to show more)[/dim]\n")
        found_files = found_files[:limit]

    # Display results
    table = Table(title=f"Found {len(found_files)} Document(s)")
    table.add_column("#", style="dim", width=3)
    table.add_column("Filename", style="cyan")
    table.add_column("Location", style="dim")
    table.add_column("Size", justify="right", style="green")

    for i, f in enumerate(found_files, 1):
        size = f.stat().st_size
        if size >= 1024 * 1024:
            size_str = f"{size / (1024*1024):.1f} MB"
        elif size >= 1024:
            size_str = f"{size / 1024:.1f} KB"
        else:
            size_str = f"{size} B"

        # Show path relative to home if possible
        try:
            rel_path = f.parent.relative_to(Path.home())
            location = f"~/{rel_path}"
        except ValueError:
            location = str(f.parent)

        table.add_row(str(i), f.name, location, size_str)

    console.print(table)

    rprint("\n[dim]To process a file:[/dim]")
    if found_files:
        rprint(f"  tax-agent collect \"{found_files[0]}\"")


@app.command()
def chat(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Start an interactive chat session to explore tax strategies."""
    from tax_agent.chat import TaxAdvisorChat

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    advisor = TaxAdvisorChat(tax_year)

    rprint(Panel.fit(
        f"[bold blue]Tax Advisor Chat[/bold blue]\n\n"
        f"Tax Year: {tax_year}\n"
        f"State: {config.state or 'Not set'}\n\n"
        "Ask me anything about your taxes! I'll help you find deductions,\n"
        "understand tax implications, and explore strategies to save money.\n\n"
        "Type 'quit' or 'exit' to end the session.\n"
        "Type 'suggest' for topic suggestions.",
        title="Interactive Tax Advisor"
    ))

    # Show suggestions
    suggestions = advisor.suggest_topics()
    rprint("\n[dim]Try asking:[/dim]")
    for s in suggestions[:3]:
        rprint(f"  [cyan]• {s}[/cyan]")
    rprint("")

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]")
        except KeyboardInterrupt:
            rprint("\n[dim]Session ended.[/dim]")
            break

        if not user_input.strip():
            continue

        if user_input.lower() in ("quit", "exit", "bye", "q"):
            rprint("[dim]Session ended. Good luck with your taxes![/dim]")
            break

        if user_input.lower() == "suggest":
            suggestions = advisor.suggest_topics()
            rprint("\n[bold]Suggested topics:[/bold]")
            for s in suggestions:
                rprint(f"  [cyan]• {s}[/cyan]")
            continue

        if user_input.lower() == "reset":
            advisor.reset()
            rprint("[dim]Conversation reset.[/dim]")
            continue

        with console.status("[bold green]Thinking..."):
            response = advisor.chat(user_input)

        rprint(f"\n[bold blue]Advisor[/bold blue]: {response}")


@app.command()
def collect(
    file: Annotated[Path, typer.Argument(help="Path to tax document (PDF or image)")],
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
    directory: Annotated[Optional[Path], typer.Option("--dir", "-d", help="Process all files in directory")] = None,
    replace: Annotated[bool, typer.Option("--replace", "-r", help="Replace existing document if duplicate")] = False,
) -> None:
    """Collect and process a tax document."""
    from tax_agent.collectors.document_classifier import DocumentCollector

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    collector = DocumentCollector()

    if directory:
        # Process directory - resolve path first
        resolved_dir = Path(str(directory).replace('~', str(Path.home())))
        if not resolved_dir.is_absolute():
            resolved_dir = Path.cwd() / resolved_dir
        resolved_dir = resolved_dir.resolve()

        if not resolved_dir.is_dir():
            rprint(f"[red]Not a directory: {directory}[/red]")
            rprint(f"[dim]Resolved path: {resolved_dir}[/dim]")
            raise typer.Exit(1)

        rprint(f"[cyan]Processing documents in {resolved_dir} for tax year {tax_year}...[/cyan]")

        with console.status("[bold green]Processing files..."):
            results = collector.process_directory(resolved_dir, tax_year)

        for file_path, result in results:
            if isinstance(result, Exception):
                rprint(f"[red]  {file_path.name}: {result}[/red]")
            else:
                confidence = "high" if result.confidence_score >= 0.8 else "low"
                review_flag = " [yellow](needs review)[/yellow]" if result.needs_review else ""
                rprint(f"[green]  {file_path.name}: {get_enum_value(result.document_type)} from {result.issuer_name} ({confidence} confidence){review_flag}[/green]")

        success_count = sum(1 for _, r in results if not isinstance(r, Exception))
        rprint(f"\n[cyan]Processed {success_count}/{len(results)} files successfully.[/cyan]")
    else:
        # Process single file - use smart path resolution
        resolved_file, suggestions = resolve_file_path(file)

        # Check for glob patterns that returned multiple files
        if suggestions and resolved_file is None and ('*' in str(file) or '?' in str(file)):
            rprint(f"[cyan]Found {len(suggestions)} files matching pattern:[/cyan]")
            for i, s in enumerate(suggestions, 1):
                rprint(f"  {i}. {s}")

            if Confirm.ask("\n[yellow]Process all matching files?[/yellow]"):
                rprint(f"\n[cyan]Processing {len(suggestions)} files for tax year {tax_year}...[/cyan]")
                for match in suggestions:
                    try:
                        with console.status(f"[bold green]Processing {match.name}..."):
                            doc = collector.process_file(match, tax_year, replace=replace)
                        rprint(f"[green]  ✓ {match.name}: {get_enum_value(doc.document_type)}[/green]")
                    except Exception as e:
                        rprint(f"[red]  ✗ {match.name}: {e}[/red]")
                raise typer.Exit(0)
            raise typer.Exit(0)

        if resolved_file is None:
            rprint(f"[red]File not found: {file}[/red]")

            if suggestions:
                rprint(f"\n[yellow]Did you mean one of these?[/yellow]")
                for i, s in enumerate(suggestions, 1):
                    rprint(f"  {i}. {s}")
                rprint(f"\n[dim]Tip: Use the full path or navigate to the file's directory first.[/dim]")
            else:
                rprint(f"\n[dim]Searched in: current directory, ~/Documents, ~/Downloads, ~/Desktop[/dim]")
                rprint(f"[dim]Tip: Use 'tax-agent collect \"*.pdf\"' to find PDF files in current directory.[/dim]")
            raise typer.Exit(1)

        file = resolved_file
        rprint(f"[cyan]Processing {file.name} for tax year {tax_year}...[/cyan]")
        if resolved_file != Path(str(file).replace('~', str(Path.home()))).resolve():
            rprint(f"[dim]Found at: {file}[/dim]")

        try:
            with console.status("[bold green]Extracting and analyzing document..."):
                doc = collector.process_file(file, tax_year, replace=replace)

            rprint(f"\n[green]Document processed successfully![/green]")

            # Show document details
            table = Table(title="Document Details")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("ID", doc.id[:8] + "...")
            table.add_row("Type", get_enum_value(doc.document_type))
            table.add_row("Issuer", doc.issuer_name)
            if doc.issuer_ein:
                table.add_row("EIN", doc.issuer_ein)
            table.add_row("Tax Year", str(doc.tax_year))
            table.add_row("Confidence", f"{doc.confidence_score:.0%}")

            if doc.needs_review:
                table.add_row("Status", "[yellow]Needs Review[/yellow]")
            else:
                table.add_row("Status", "[green]Ready[/green]")

            # Show key financial data
            if doc.extracted_data:
                if get_enum_value(doc.document_type) == "W2":
                    if "box_1" in doc.extracted_data:
                        table.add_row("Wages (Box 1)", f"${doc.extracted_data['box_1']:,.2f}")
                    if "box_2" in doc.extracted_data:
                        table.add_row("Fed Tax Withheld", f"${doc.extracted_data['box_2']:,.2f}")
                elif "1099_INT" in get_enum_value(doc.document_type):
                    if "box_1" in doc.extracted_data:
                        table.add_row("Interest Income", f"${doc.extracted_data['box_1']:,.2f}")
                elif "1099_DIV" in get_enum_value(doc.document_type):
                    if "box_1a" in doc.extracted_data:
                        table.add_row("Dividends", f"${doc.extracted_data['box_1a']:,.2f}")

            console.print(table)

        except Exception as e:
            rprint(f"[red]Error processing document: {e}[/red]")
            raise typer.Exit(1)


@app.command()
def analyze(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
    summary: Annotated[bool, typer.Option("--summary", "-s", help="Brief summary only")] = False,
    ai: Annotated[bool, typer.Option("--ai", help="Include AI-powered analysis")] = True,
    legacy: Annotated[bool, typer.Option("--legacy", help="Use legacy agent instead of Agent SDK")] = False,
) -> None:
    """Analyze collected documents for tax implications.

    By default, uses the Agent SDK with agentic tool access for verification
    and web research. Use --legacy to fall back to the standard agent.
    """
    from tax_agent.analyzers.implications import TaxAnalyzer

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    # Determine if we should use agentic mode (SDK is default, legacy is opt-in)
    use_agentic = config.use_agent_sdk and not legacy

    # Check if SDK is available when we want to use it
    if use_agentic:
        from tax_agent.agent_sdk import sdk_available
        if not sdk_available():
            rprint("[dim]Agent SDK not available, using standard agent...[/dim]\n")
            use_agentic = False

    tax_year = year or config.tax_year

    with console.status(f"[bold green]Analyzing tax documents for {tax_year}..."):
        analyzer = TaxAnalyzer(tax_year)
        analysis = analyzer.generate_analysis()

    if "error" in analysis:
        rprint(f"[red]{analysis['error']}[/red]")
        raise typer.Exit(1)

    # Income Summary
    rprint(Panel.fit(f"[bold]Tax Analysis for {tax_year}[/bold]", title="Summary"))

    income = analysis["income_summary"]
    income_table = Table(title="Income Summary")
    income_table.add_column("Source", style="cyan")
    income_table.add_column("Amount", style="green", justify="right")

    income_table.add_row("Wages", f"${income['wages']:,.2f}")
    income_table.add_row("Interest", f"${income['interest']:,.2f}")
    income_table.add_row("Ordinary Dividends", f"${income['dividends_ordinary']:,.2f}")
    income_table.add_row("Qualified Dividends", f"${income['dividends_qualified']:,.2f}")
    income_table.add_row("Short-term Capital Gains", f"${income['capital_gains_short']:,.2f}")
    income_table.add_row("Long-term Capital Gains", f"${income['capital_gains_long']:,.2f}")
    income_table.add_row("Other Income", f"${income['other']:,.2f}")
    income_table.add_row("", "")
    income_table.add_row("[bold]Total Income[/bold]", f"[bold]${analysis['total_income']:,.2f}[/bold]")

    console.print(income_table)

    # Tax Estimate
    tax = analysis["tax_estimate"]
    tax_table = Table(title="Tax Estimate")
    tax_table.add_column("Item", style="cyan")
    tax_table.add_column("Amount", style="white", justify="right")

    tax_table.add_row("Standard Deduction", f"${tax['standard_deduction']:,.2f}")
    tax_table.add_row("Taxable Ordinary Income", f"${tax['taxable_ordinary_income']:,.2f}")
    tax_table.add_row("Ordinary Income Tax", f"${tax['ordinary_income_tax']:,.2f}")
    tax_table.add_row("Capital Gains Tax", f"${tax['capital_gains_tax']:,.2f}")
    tax_table.add_row("[bold]Estimated Total Tax[/bold]", f"[bold]${tax['total_tax']:,.2f}[/bold]")

    console.print(tax_table)

    # Withholding
    withholding = analysis["withholding_summary"]
    with_table = Table(title="Withholding Summary")
    with_table.add_column("Type", style="cyan")
    with_table.add_column("Amount", style="green", justify="right")

    with_table.add_row("Federal Income Tax", f"${withholding['federal']:,.2f}")
    with_table.add_row("State Income Tax", f"${withholding['state']:,.2f}")
    with_table.add_row("Social Security", f"${withholding['social_security']:,.2f}")
    with_table.add_row("Medicare", f"${withholding['medicare']:,.2f}")

    console.print(with_table)

    # Result
    rprint("")
    if analysis["refund_or_owed"] > 0:
        rprint(f"[bold green]Estimated Refund: ${analysis['estimated_refund']:,.2f}[/bold green]")
    elif analysis["refund_or_owed"] < 0:
        rprint(f"[bold red]Estimated Amount Owed: ${analysis['estimated_owed']:,.2f}[/bold red]")
    else:
        rprint("[bold yellow]Estimated: Break even[/bold yellow]")

    # AI Analysis
    if ai and not summary:
        rprint("\n")
        if use_agentic:
            # Use Agent SDK with streaming (default behavior)
            rprint("[dim]Using Agent SDK with agentic analysis...[/dim]\n")
            try:
                ai_analysis = _run_agentic_analysis(analyzer, tax_year)
            except Exception as e:
                rprint(f"[yellow]Agent SDK error: {e}[/yellow]")
                rprint("[dim]Falling back to standard AI analysis...[/dim]")
                with console.status("[bold green]Generating AI analysis..."):
                    ai_analysis = analyzer.generate_ai_analysis()
        else:
            with console.status("[bold green]Generating AI analysis..."):
                ai_analysis = analyzer.generate_ai_analysis()

        rprint(Panel(ai_analysis, title="AI Tax Analysis", border_style="blue"))

    # Generate analysis markdown for export
    analysis_md = f"""# Tax Analysis - {tax_year}

## Income Summary
- **Total Income:** ${analysis.get('total_income', 0):,.2f}
- **Taxable Income:** ${analysis.get('taxable_income', 0):,.2f}

## Tax Calculation
- **Federal Tax:** ${analysis.get('federal_tax', 0):,.2f}
- **State Tax:** ${analysis.get('state_tax', 0):,.2f}
- **Total Tax:** ${analysis.get('total_tax', 0):,.2f}

## Withholdings
- **Federal Withholding:** ${analysis.get('federal_withholding', 0):,.2f}
- **State Withholding:** ${analysis.get('state_withholding', 0):,.2f}

## Result
{"**Estimated Refund:** $" + f"{analysis.get('estimated_refund', 0):,.2f}" if analysis.get('refund_or_owed', 0) > 0 else "**Estimated Owed:** $" + f"{analysis.get('estimated_owed', 0):,.2f}"}

---
*Generated by Tax Prep Agent*
"""
    prompt_export(analysis_md, f"analysis-{tax_year}", "analysis")


@app.command()
def optimize(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
    interview: Annotated[bool, typer.Option("--interview", "-i", help="Run interactive interview")] = True,
) -> None:
    """Find tax-saving opportunities through AI-powered analysis and interview."""
    from tax_agent.analyzers.deductions import TaxOptimizer

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    optimizer = TaxOptimizer(tax_year)

    rprint(Panel.fit(
        "[bold blue]Tax Optimization Advisor[/bold blue]\n\n"
        "This tool will analyze your tax situation and ask questions to identify\n"
        "tax-saving opportunities, including deductions, credits, and strategies\n"
        "for complex situations like stock compensation (RSUs, ISOs, ESPP).",
        title="Tax Optimizer"
    ))

    answers: dict = {}

    if interview:
        # Get and ask interview questions
        with console.status("[bold green]Generating personalized questions..."):
            questions = optimizer.get_interview_questions()

        rprint("\n[bold]Please answer these questions to help identify savings opportunities:[/bold]\n")

        for i, q in enumerate(questions, 1):
            rprint(f"\n[cyan]{i}. {q['question']}[/cyan]")
            if "relevance" in q:
                rprint(f"   [dim]({q['relevance']})[/dim]")

            q_type = q.get("type", "text")

            if q_type == "yes_no":
                answer = Prompt.ask("   Answer", choices=["y", "n"], default="n")
                answers[q["id"]] = answer.lower() == "y"

            elif q_type == "number":
                answer = Prompt.ask("   Amount ($)", default="0")
                try:
                    answers[q["id"]] = float(answer.replace(",", "").replace("$", ""))
                except ValueError:
                    answers[q["id"]] = 0

            elif q_type == "select":
                options = q.get("options", [])
                rprint("   Options:")
                for j, opt in enumerate(options, 1):
                    rprint(f"     {j}. {opt}")
                answer = Prompt.ask("   Enter number", default="1")
                try:
                    idx = int(answer) - 1
                    answers[q["id"]] = options[idx] if 0 <= idx < len(options) else None
                except ValueError:
                    answers[q["id"]] = None

            elif q_type == "multi_select":
                options = q.get("options", [])
                rprint("   Options (enter numbers separated by commas, or 'none'):")
                for j, opt in enumerate(options, 1):
                    rprint(f"     {j}. {opt}")
                answer = Prompt.ask("   Enter numbers", default="none")
                if answer.lower() == "none":
                    answers[q["id"]] = []
                else:
                    try:
                        indices = [int(x.strip()) - 1 for x in answer.split(",")]
                        answers[q["id"]] = [options[i] for i in indices if 0 <= i < len(options)]
                    except ValueError:
                        answers[q["id"]] = []

            else:  # text
                answers[q["id"]] = Prompt.ask("   Answer", default="")

        # Check for stock compensation
        stock_comp = answers.get("stock_compensation", [])
        if stock_comp and stock_comp != ["None"]:
            rprint("\n[bold yellow]Stock Compensation Detected[/bold yellow]")
            rprint("Let me analyze your equity compensation situation...\n")

            for comp_type in stock_comp:
                if comp_type == "None":
                    continue

                rprint(f"\n[cyan]Analyzing {comp_type}...[/cyan]")

                # Ask follow-up questions about the stock comp
                details = {}
                if "RSU" in comp_type:
                    details["shares_vested"] = Prompt.ask("   How many shares vested this year?", default="0")
                    details["vesting_price"] = Prompt.ask("   Average price at vesting ($)?", default="0")
                    details["shares_sold"] = Prompt.ask("   How many shares did you sell?", default="0")
                    details["sale_price"] = Prompt.ask("   Average sale price ($)?", default="0")
                    details["company"] = Prompt.ask("   Company name?", default="")

                with console.status(f"[bold green]Analyzing {comp_type} tax implications..."):
                    analysis = optimizer.analyze_stock_compensation(comp_type, details)

                if "error" not in analysis:
                    rprint(Panel(
                        f"[bold]Tax Treatment:[/bold]\n{analysis.get('tax_treatment', 'N/A')}\n\n"
                        f"[bold]Immediate Actions:[/bold]\n{analysis.get('immediate_actions', 'N/A')}\n\n"
                        f"[bold]Optimization Tips:[/bold]\n{analysis.get('optimization_tips', 'N/A')}\n\n"
                        f"[bold yellow]Warnings:[/bold yellow]\n{analysis.get('warnings', 'None')}",
                        title=f"{comp_type} Analysis",
                        border_style="yellow"
                    ))

    # Find deductions
    rprint("\n")
    with console.status("[bold green]Finding deductions and credits..."):
        deductions = optimizer.find_deductions(interview_answers=answers)

    if "error" not in deductions:
        # Standard vs Itemized
        std_vs_item = deductions.get("standard_vs_itemized", {})
        if isinstance(std_vs_item, dict):
            recommendation = std_vs_item.get("recommendation", "standard")
            reasoning = std_vs_item.get("reasoning", "")
        else:
            recommendation = str(std_vs_item)
            reasoning = ""

        rprint(Panel(
            f"[bold]Recommendation:[/bold] {recommendation.upper()} deduction\n"
            f"[dim]{reasoning}[/dim]",
            title="Standard vs. Itemized",
            border_style="green"
        ))

        # Recommended deductions
        rec_deductions = deductions.get("recommended_deductions", [])
        if rec_deductions:
            ded_table = Table(title="Recommended Deductions")
            ded_table.add_column("Deduction", style="cyan")
            ded_table.add_column("Est. Value", style="green", justify="right")
            ded_table.add_column("Action Needed", style="white")

            for ded in rec_deductions:
                if isinstance(ded, dict):
                    name = ded.get("name", "Unknown")
                    value = ded.get("estimated_value", 0)
                    action = ded.get("action_needed", "")
                    value_str = f"${value:,.0f}" if isinstance(value, (int, float)) else str(value)
                    ded_table.add_row(name, value_str, action[:50])

            console.print(ded_table)

        # Recommended credits
        rec_credits = deductions.get("recommended_credits", [])
        if rec_credits:
            credit_table = Table(title="Recommended Credits")
            credit_table.add_column("Credit", style="cyan")
            credit_table.add_column("Est. Value", style="green", justify="right")

            for credit in rec_credits:
                if isinstance(credit, dict):
                    name = credit.get("name", "Unknown")
                    value = credit.get("estimated_value", 0)
                    value_str = f"${value:,.0f}" if isinstance(value, (int, float)) else str(value)
                    credit_table.add_row(name, value_str)

            console.print(credit_table)

        # Estimated savings
        savings = deductions.get("estimated_total_savings", 0)
        if savings:
            rprint(f"\n[bold green]Estimated Total Tax Savings: ${savings:,.0f}[/bold green]")

        # Action items
        action_items = deductions.get("action_items", [])
        if action_items:
            rprint("\n[bold]Action Items:[/bold]")
            for item in action_items:
                rprint(f"  - {item}")

        # Warnings
        warnings = deductions.get("warnings", [])
        if warnings:
            rprint("\n[bold yellow]Warnings:[/bold yellow]")
            for warn in warnings:
                rprint(f"  [yellow]- {warn}[/yellow]")

    else:
        rprint(f"[red]Error finding deductions: {deductions.get('error')}[/red]")

    # Generate optimization report for export
    optimization_md_parts = [f"# Tax Optimization Report - {tax_year}\n"]

    if "error" not in deductions:
        std_vs_item = deductions.get("standard_vs_itemized", {})
        if isinstance(std_vs_item, dict):
            recommendation = std_vs_item.get("recommendation", "standard")
            reasoning = std_vs_item.get("reasoning", "")
        else:
            recommendation = str(std_vs_item)
            reasoning = ""

        optimization_md_parts.append(f"## Deduction Strategy\n**Recommendation:** {recommendation.upper()}\n{reasoning}\n")

        rec_deductions = deductions.get("recommended_deductions", [])
        if rec_deductions:
            optimization_md_parts.append("## Recommended Deductions\n")
            for ded in rec_deductions:
                if isinstance(ded, dict):
                    name = ded.get("name", "Unknown")
                    value = ded.get("estimated_value", 0)
                    action = ded.get("action_needed", "")
                    optimization_md_parts.append(f"- **{name}:** ${value:,.0f}\n  - Action: {action}\n")

        rec_credits = deductions.get("recommended_credits", [])
        if rec_credits:
            optimization_md_parts.append("\n## Recommended Credits\n")
            for credit in rec_credits:
                if isinstance(credit, dict):
                    name = credit.get("name", "Unknown")
                    value = credit.get("estimated_value", 0)
                    optimization_md_parts.append(f"- **{name}:** ${value:,.0f}\n")

        savings = deductions.get("estimated_total_savings", 0)
        if savings:
            optimization_md_parts.append(f"\n## Estimated Savings\n**Total Tax Savings:** ${savings:,.0f}\n")

        action_items = deductions.get("action_items", [])
        if action_items:
            optimization_md_parts.append("\n## Action Items\n")
            for item in action_items:
                optimization_md_parts.append(f"- {item}\n")

    optimization_md_parts.append("\n---\n*Generated by Tax Prep Agent*\n")
    prompt_export("".join(optimization_md_parts), f"optimization-{tax_year}", "optimization report")


@app.command()
def review(
    return_file: Annotated[Path, typer.Argument(help="Path to completed tax return PDF")],
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Review a completed tax return for errors and enhancements."""
    from tax_agent.reviewers.error_checker import ReturnReviewer
    from tax_agent.models.returns import ReviewSeverity

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    if not return_file.exists():
        rprint(f"[red]File not found: {return_file}[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year

    with console.status(f"[bold green]Reviewing tax return for {tax_year}..."):
        reviewer = ReturnReviewer(tax_year)
        review_result = reviewer.review_return(return_file)

    # Display results
    rprint(Panel.fit(
        f"[bold]Tax Return Review[/bold]\n"
        f"Tax Year: {review_result.return_summary.tax_year}\n"
        f"Documents Checked: {len(review_result.source_documents_checked)}",
        title="Review Complete"
    ))

    # Summary
    summary_style = "green" if review_result.errors_count == 0 else "red"
    rprint(f"\n[{summary_style}]{review_result.overall_assessment}[/{summary_style}]")

    # Findings table
    if review_result.findings:
        rprint("\n")
        findings_table = Table(title="Findings")
        findings_table.add_column("Severity", style="white", width=10)
        findings_table.add_column("Category", style="cyan", width=12)
        findings_table.add_column("Issue", style="white")
        findings_table.add_column("Impact", style="yellow", justify="right", width=12)

        severity_colors = {
            ReviewSeverity.ERROR: "red",
            ReviewSeverity.WARNING: "yellow",
            ReviewSeverity.SUGGESTION: "blue",
            ReviewSeverity.INFO: "dim",
        }

        for finding in review_result.findings:
            color = severity_colors.get(finding.severity, "white")
            impact_str = f"${finding.potential_impact:,.0f}" if finding.potential_impact else "-"

            findings_table.add_row(
                f"[{color}]{get_enum_value(finding.severity).upper()}[/{color}]",
                finding.category,
                finding.title,
                impact_str,
            )

        console.print(findings_table)

        # Detailed findings
        rprint("\n[bold]Detailed Findings:[/bold]\n")
        for i, finding in enumerate(review_result.findings, 1):
            color = severity_colors.get(finding.severity, "white")
            rprint(f"[{color}]{i}. {get_enum_value(finding.severity).upper()}: {finding.title}[/{color}]")
            rprint(f"   [cyan]Category:[/cyan] {finding.category}")
            rprint(f"   {finding.description}")
            if finding.line_reference:
                rprint(f"   [dim]Form Reference:[/dim] {finding.line_reference}")
            if finding.expected_value:
                rprint(f"   [green]Expected:[/green] {finding.expected_value}")
            if finding.actual_value:
                rprint(f"   [red]Actual:[/red] {finding.actual_value}")
            if finding.potential_impact:
                rprint(f"   [yellow]Potential Tax Impact:[/yellow] ${finding.potential_impact:,.2f}")
            if finding.recommendation:
                rprint(f"   [bold]Recommendation:[/bold] {finding.recommendation}")
            if finding.source_document_id:
                rprint(f"   [dim]Related Document:[/dim] {finding.source_document_id}")
            rprint("")
    else:
        rprint("\n[green]No issues found in the tax return.[/green]")

    # Save the review to database
    from tax_agent.storage.database import get_database
    from tax_agent.exporters import export_review_markdown
    db = get_database()
    db.save_review(review_result)
    rprint(f"\n[dim]Review saved (ID: {review_result.id[:8]}...)[/dim]")

    # Prompt for export
    review_dict = {
        "id": review_result.id,
        "tax_year": review_result.return_summary.tax_year,
        "return_type": get_enum_value(review_result.return_summary.return_type),
        "overall_assessment": review_result.overall_assessment,
        "summary": review_result.return_summary.model_dump(),
        "findings": [f.model_dump() for f in review_result.findings],
        "created_at": review_result.reviewed_at.isoformat(),
    }
    markdown_content = export_review_markdown(review_dict)
    prompt_export(markdown_content, f"review-{tax_year}", "review")


@app.command()
def reviews(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Filter by tax year")] = None,
) -> None:
    """List saved tax return reviews."""
    from tax_agent.storage.database import get_database

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    db = get_database()
    saved_reviews = db.get_reviews(tax_year=year)

    if not saved_reviews:
        rprint(f"[yellow]No saved reviews{f' for tax year {year}' if year else ''}.[/yellow]")
        return

    table = Table(title="Saved Reviews")
    table.add_column("ID", style="dim")
    table.add_column("Tax Year", style="cyan")
    table.add_column("Type", style="white")
    table.add_column("Findings", justify="right")
    table.add_column("Date", style="dim")

    for rev in saved_reviews:
        table.add_row(
            rev["id"][:8] + "...",
            str(rev["tax_year"]),
            rev["return_type"],
            str(len(rev["findings"])),
            rev["created_at"][:10],
        )

    console.print(table)
    rprint("\n[dim]Use 'tax-agent review-show <id>' to view details[/dim]")


@app.command("review-show")
def review_show(
    review_id: Annotated[str, typer.Argument(help="Review ID (can be partial)")],
) -> None:
    """Show details of a saved review."""
    from tax_agent.storage.database import get_database
    from tax_agent.models.returns import ReviewSeverity
    import json

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    db = get_database()
    review = db.get_review(review_id)

    if not review:
        rprint(f"[red]Review not found: {review_id}[/red]")
        raise typer.Exit(1)

    # Display summary
    summary = review["summary"]
    rprint(Panel.fit(
        f"[bold]Tax Return Review[/bold]\n"
        f"Tax Year: {review['tax_year']}\n"
        f"Return Type: {review['return_type']}\n"
        f"Reviewed: {review['created_at'][:10]}",
        title=f"Review {review['id'][:8]}..."
    ))

    # Display overall assessment
    if summary.get("overall_assessment"):
        rprint(f"\n[bold]Overall Assessment:[/bold] {summary['overall_assessment']}")

    # Display return summary if available
    if summary:
        rprint("\n[bold]Return Summary:[/bold]")
        if summary.get("filing_status"):
            rprint(f"  Filing Status: {summary['filing_status']}")
        if summary.get("total_income"):
            rprint(f"  Total Income: ${summary['total_income']:,.2f}")
        if summary.get("taxable_income"):
            rprint(f"  Taxable Income: ${summary['taxable_income']:,.2f}")
        if summary.get("total_tax"):
            rprint(f"  Total Tax: ${summary['total_tax']:,.2f}")
        if summary.get("refund_amount"):
            rprint(f"  [green]Refund Due: ${summary['refund_amount']:,.2f}[/green]")
        if summary.get("amount_owed"):
            rprint(f"  [yellow]Tax Owed: ${summary['amount_owed']:,.2f}[/yellow]")

    # Display findings
    findings = review["findings"]
    if findings:
        rprint(f"\n[bold]{len(findings)} Finding(s):[/bold]\n")

        # Use lowercase keys to match enum values
        severity_colors = {
            "error": "red",
            "warning": "yellow",
            "suggestion": "blue",
            "info": "dim",
        }

        for i, finding in enumerate(findings, 1):
            severity = str(finding.get("severity", "info")).lower()
            color = severity_colors.get(severity, "white")
            rprint(f"[{color}]{i}. {severity.upper()}: {finding.get('title', 'N/A')}[/{color}]")
            if finding.get("category"):
                rprint(f"   [cyan]Category:[/cyan] {finding['category']}")
            rprint(f"   {finding.get('description', '')}")
            if finding.get("line_reference"):
                rprint(f"   [dim]Form Reference:[/dim] {finding['line_reference']}")
            if finding.get("expected_value"):
                rprint(f"   [green]Expected:[/green] {finding['expected_value']}")
            if finding.get("actual_value"):
                rprint(f"   [red]Actual:[/red] {finding['actual_value']}")
            if finding.get("potential_impact"):
                rprint(f"   [yellow]Potential Tax Impact:[/yellow] ${finding['potential_impact']:,.2f}")
            if finding.get("recommendation"):
                rprint(f"   [bold]Recommendation:[/bold] {finding['recommendation']}")
            if finding.get("source_document_id"):
                rprint(f"   [dim]Related Document:[/dim] {finding['source_document_id']}")
            rprint("")
    else:
        rprint("\n[green]No issues found in this review.[/green]")


@app.command()
def export(
    output: Annotated[Path, typer.Argument(help="Output file path")],
    format: Annotated[str, typer.Option("--format", "-f", help="Output format: md or pdf")] = "md",
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
    review_id: Annotated[Optional[str], typer.Option("--review", "-r", help="Export specific review")] = None,
    documents_only: Annotated[bool, typer.Option("--documents", "-d", help="Export only documents")] = False,
) -> None:
    """Export tax data to Markdown or PDF format.

    Examples:
        tax-agent export report.md                    # Full report as markdown
        tax-agent export report.pdf -f pdf            # Full report as PDF
        tax-agent export docs.md --documents          # Documents only
        tax-agent export review.pdf -r abc123 -f pdf  # Specific review as PDF
    """
    from tax_agent.exporters import (
        export_review_markdown,
        export_documents_markdown,
        export_full_report_markdown,
        export_to_file,
    )
    from tax_agent.storage.database import get_database

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    db = get_database()

    # Validate format
    format = format.lower()
    if format not in ("md", "pdf", "markdown"):
        rprint(f"[red]Invalid format: {format}. Use 'md' or 'pdf'.[/red]")
        raise typer.Exit(1)

    if format == "markdown":
        format = "md"

    with console.status(f"[bold green]Generating {format.upper()} export..."):
        if review_id:
            # Export specific review
            review = db.get_review(review_id)
            if not review:
                rprint(f"[red]Review not found: {review_id}[/red]")
                raise typer.Exit(1)
            content = export_review_markdown(review)
        elif documents_only:
            # Export documents only
            documents = db.get_documents(tax_year=tax_year)
            if not documents:
                rprint(f"[yellow]No documents found for tax year {tax_year}.[/yellow]")
                raise typer.Exit(1)
            content = export_documents_markdown(documents, tax_year)
        else:
            # Export full report
            content = export_full_report_markdown(tax_year)

        # Write to file
        output_path = export_to_file(content, output, format)

    rprint(f"[green]Exported to: {output_path}[/green]")
    rprint(f"[dim]Format: {format.upper()}, Tax Year: {tax_year}[/dim]")


@app.command()
def report(
    output: Annotated[Path, typer.Argument(help="Output file path (e.g., summary.pdf)")] = Path("tax-summary.pdf"),
    format: Annotated[str, typer.Option("--format", "-f", help="Output format: md or pdf")] = "pdf",
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Generate a comprehensive tax preparation summary report.

    Combines income analysis, tax estimates, withholding, document inventory,
    and review findings into one report. Defaults to PDF output.

    Examples:
        tax-agent report                         # PDF summary to tax-summary.pdf
        tax-agent report my-taxes.pdf            # PDF to custom filename
        tax-agent report summary.md -f md        # Markdown format
        tax-agent report -y 2023                 # Specific tax year
    """
    from tax_agent.analyzers.implications import TaxAnalyzer
    from tax_agent.reports import generate_tax_summary, generate_tax_summary_pdf
    from tax_agent.storage.database import get_database

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    db = get_database()

    format = format.lower()
    if format not in ("md", "pdf", "markdown"):
        rprint(f"[red]Invalid format: {format}. Use 'md' or 'pdf'.[/red]")
        raise typer.Exit(1)
    if format == "markdown":
        format = "md"

    with console.status(f"[bold green]Generating tax summary report for {tax_year}..."):
        # Run the analysis
        analyzer = TaxAnalyzer(tax_year)
        analysis = analyzer.generate_analysis()

        if "error" in analysis:
            rprint(f"[yellow]{analysis['error']}[/yellow]")
            rprint("[dim]Collect documents first with: tax-agent add <file>[/dim]")
            raise typer.Exit(1)

        # Gather supporting data
        documents = db.get_documents(tax_year=tax_year)
        reviews = db.get_reviews(tax_year=tax_year)
        profile = db.get_taxpayer_profile(tax_year)
        taxpayer_info = None
        if profile:
            taxpayer_info = {
                "state": profile.state,
                "dependents": profile.num_dependents,
            }

        if format == "pdf":
            if not str(output).endswith(".pdf"):
                output = output.with_suffix(".pdf")
            output_path = generate_tax_summary_pdf(
                analysis, output,
                documents=documents, reviews=reviews, taxpayer_info=taxpayer_info,
            )
        else:
            if not str(output).endswith(".md"):
                output = output.with_suffix(".md")
            content = generate_tax_summary(
                analysis,
                documents=documents, reviews=reviews, taxpayer_info=taxpayer_info,
            )
            output.write_text(content)
            output_path = output

    rprint(f"\n[green]Tax summary report generated: {output_path}[/green]")
    rprint(f"[dim]Tax Year: {tax_year}, Format: {format.upper()}[/dim]")

    # Print quick summary to console
    income = analysis.get("income_summary", {})
    tax_est = analysis.get("tax_estimate", {})
    refund = analysis.get("refund_or_owed", 0)

    rprint("")
    rprint(Panel.fit(
        f"[bold]Total Income:[/bold] ${sum(income.values()):,.2f}\n"
        f"[bold]Federal Tax:[/bold]  ${tax_est.get('total_tax', 0):,.2f}\n"
        f"[bold]{'Refund' if refund >= 0 else 'Owed'}:[/bold]       "
        f"{'$' + f'{refund:,.2f}' if refund >= 0 else '$' + f'{-refund:,.2f}'}",
        title=f"Tax Year {tax_year} Summary",
        border_style="green" if refund >= 0 else "red",
    ))


# =============================================================================
# AI Analysis Commands
# =============================================================================


@ai_app.command("validate")
def ai_validate(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Cross-validate all collected documents for consistency."""
    from tax_agent.agent import get_agent
    from tax_agent.storage.database import get_database

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    db = get_database()
    documents = db.get_documents(tax_year=tax_year)

    if not documents:
        rprint(f"[yellow]No documents collected for tax year {tax_year}.[/yellow]")
        raise typer.Exit(1)

    # Prepare document data for validation
    docs_data = []
    for doc in documents:
        docs_data.append({
            "id": doc.id[:8],
            "type": get_enum_value(doc.document_type),
            "issuer": doc.issuer_name,
            "extracted_data": doc.extracted_data,
        })

    rprint(f"[cyan]Validating {len(documents)} documents for tax year {tax_year}...[/cyan]")

    agent = get_agent()
    with console.status("[bold green]Running AI cross-validation analysis..."):
        result = agent.validate_documents_cross_reference(docs_data)

    # Display results
    status_colors = {
        "pass": "green",
        "warnings": "yellow",
        "errors": "red",
    }
    status_color = status_colors.get(result.get("validation_status", ""), "white")

    rprint(Panel.fit(
        f"[bold]Validation Status: [{status_color}]{result.get('validation_status', 'unknown').upper()}[/{status_color}][/bold]\n"
        f"Consistency Score: {result.get('consistency_score', 0):.0%}",
        title="Cross-Document Validation"
    ))

    # Show summary
    summary = result.get("summary", {})
    if summary:
        sum_table = Table(title="Document Summary")
        sum_table.add_column("Metric", style="cyan")
        sum_table.add_column("Amount", style="green", justify="right")

        if summary.get("total_wages"):
            sum_table.add_row("Total Wages", f"${summary['total_wages']:,.2f}")
        if summary.get("total_federal_withholding"):
            sum_table.add_row("Federal Withholding", f"${summary['total_federal_withholding']:,.2f}")
        if summary.get("total_interest_income"):
            sum_table.add_row("Interest Income", f"${summary['total_interest_income']:,.2f}")
        if summary.get("total_dividend_income"):
            sum_table.add_row("Dividend Income", f"${summary['total_dividend_income']:,.2f}")
        if summary.get("total_capital_gains"):
            sum_table.add_row("Capital Gains", f"${summary['total_capital_gains']:,.2f}")

        console.print(sum_table)

    # Show issues
    issues = result.get("issues", [])
    if issues:
        rprint("\n[bold]Issues Found:[/bold]")
        for issue in issues:
            severity = issue.get("severity", "info")
            color = {"error": "red", "warning": "yellow", "info": "blue"}.get(severity, "white")
            rprint(f"  [{color}]{severity.upper()}[/{color}]: {issue.get('description', '')}")
            if issue.get("recommended_action"):
                rprint(f"    [dim]Action: {issue['recommended_action']}[/dim]")

    # Show missing documents
    missing = result.get("missing_documents", [])
    if missing:
        rprint("\n[bold yellow]Potentially Missing Documents:[/bold yellow]")
        for doc in missing:
            importance_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(
                doc.get("importance", ""), "white"
            )
            rprint(f"  [{importance_color}]{doc.get('document_type', '')}[/{importance_color}]: {doc.get('reason', '')}")


@ai_app.command("audit-risk")
def ai_audit_risk(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Assess audit risk based on collected documents."""
    from tax_agent.agent import get_agent
    from tax_agent.storage.database import get_database
    from tax_agent.analyzers.implications import TaxAnalyzer

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    db = get_database()
    documents = db.get_documents(tax_year=tax_year)

    if not documents:
        rprint(f"[yellow]No documents collected for tax year {tax_year}.[/yellow]")
        raise typer.Exit(1)

    # Build summaries
    analyzer = TaxAnalyzer(tax_year)
    income_summary = analyzer.calculate_income_summary(documents)

    docs_summary = []
    for doc in documents:
        docs_summary.append({
            "type": get_enum_value(doc.document_type),
            "issuer": doc.issuer_name,
            "data": doc.extracted_data,
        })

    return_summary = {
        "tax_year": tax_year,
        "income": income_summary,
        "filing_status": config.get("filing_status", "single"),
        "state": config.state,
    }

    rprint(f"[cyan]Assessing audit risk for tax year {tax_year}...[/cyan]")

    agent = get_agent()
    with console.status("[bold green]Running AI audit risk assessment..."):
        result = agent.assess_audit_risk(return_summary, {"documents": docs_summary})

    # Display results
    risk_level = result.get("risk_level", "unknown")
    risk_score = result.get("overall_risk_score", 5)
    risk_colors = {
        "low": "green",
        "moderate": "yellow",
        "elevated": "yellow",
        "high": "red",
    }
    color = risk_colors.get(risk_level, "white")

    # Visual risk meter
    risk_bar = "█" * risk_score + "░" * (10 - risk_score)

    rprint(Panel.fit(
        f"[bold]Audit Risk Level: [{color}]{risk_level.upper()}[/{color}][/bold]\n\n"
        f"Risk Score: [{color}]{risk_bar}[/{color}] {risk_score}/10\n\n"
        f"{result.get('audit_probability_estimate', '')}",
        title="Audit Risk Assessment"
    ))

    # Risk factors
    risk_factors = result.get("risk_factors", [])
    if risk_factors:
        rprint("\n[bold red]Risk Factors:[/bold red]")
        for factor in sorted(risk_factors, key=lambda x: x.get("risk_contribution", 0), reverse=True):
            contribution = factor.get("risk_contribution", 0)
            bar = "▓" * contribution + "░" * (10 - contribution)
            rprint(f"  [{bar}] {factor.get('factor', '')}")
            rprint(f"    [dim]{factor.get('explanation', '')}[/dim]")
            if factor.get("mitigation"):
                rprint(f"    [green]Mitigation: {factor['mitigation']}[/green]")

    # Protective factors
    protective = result.get("protective_factors", [])
    if protective:
        rprint("\n[bold green]Protective Factors:[/bold green]")
        for factor in protective:
            rprint(f"  [green]✓[/green] {factor.get('factor', '')}")

    # Documentation recommendations
    doc_recs = result.get("documentation_recommendations", [])
    if doc_recs:
        rprint("\n[bold cyan]Documentation Recommendations:[/bold cyan]")
        for rec in doc_recs:
            priority_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(
                rec.get("priority", ""), "white"
            )
            rprint(f"  [{priority_color}]●[/{priority_color}] {rec.get('item', '')}")
            rprint(f"    [dim]{rec.get('reason', '')}[/dim]")

    # Summary
    if result.get("summary"):
        rprint(f"\n[bold]Assessment:[/bold] {result['summary']}")


@ai_app.command("scenarios")
def ai_scenarios(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Compare different filing scenarios to find optimal strategy."""
    from tax_agent.agent import get_agent
    from tax_agent.storage.database import get_database
    from tax_agent.analyzers.implications import TaxAnalyzer

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    db = get_database()
    documents = db.get_documents(tax_year=tax_year)

    if not documents:
        rprint(f"[yellow]No documents collected for tax year {tax_year}.[/yellow]")
        raise typer.Exit(1)

    # Calculate income and deductions
    analyzer = TaxAnalyzer(tax_year)
    income_data = analyzer.calculate_income_summary(documents)
    income_data["total"] = sum(income_data.values())

    # Get profile deduction info
    deductions_data = {
        "state_taxes_paid": 0,
        "mortgage_interest": 0,
        "charitable_contributions": 0,
        "medical_expenses": 0,
        "salt_cap": 10000,
    }

    rprint(f"[cyan]Comparing filing scenarios for tax year {tax_year}...[/cyan]")

    agent = get_agent()
    with console.status("[bold green]Running AI scenario comparison..."):
        result = agent.compare_filing_scenarios(income_data, deductions_data, tax_year)

    # Display optimal strategy
    optimal = result.get("optimal_strategy", {})
    if optimal:
        rprint(Panel.fit(
            f"[bold green]Recommended: {optimal.get('filing_status', 'N/A')}[/bold green]\n"
            f"Deduction Method: {optimal.get('deduction_method', 'N/A').title()}\n"
            f"Estimated Tax: ${optimal.get('estimated_tax', 0):,.2f}\n\n"
            f"[bold]Key Reasons:[/bold]\n" +
            "\n".join(f"  • {r}" for r in optimal.get("key_reasons", [])),
            title="Optimal Strategy"
        ))

    # Scenario comparison table
    scenarios = result.get("scenario_comparison", [])
    if scenarios:
        table = Table(title="Scenario Comparison")
        table.add_column("Scenario", style="cyan")
        table.add_column("Est. Tax", style="white", justify="right")
        table.add_column("Eff. Rate", style="white", justify="right")
        table.add_column("vs Optimal", style="white", justify="right")

        for scenario in scenarios:
            diff = scenario.get("vs_optimal_difference", 0)
            diff_str = f"+${diff:,.0f}" if diff > 0 else f"-${abs(diff):,.0f}" if diff < 0 else "BEST"
            diff_color = "red" if diff > 0 else "green" if diff < 0 else "bold green"

            table.add_row(
                scenario.get("scenario_name", ""),
                f"${scenario.get('estimated_tax', 0):,.2f}",
                scenario.get("effective_rate", "N/A"),
                f"[{diff_color}]{diff_str}[/{diff_color}]",
            )

        console.print(table)

    # Timing recommendations
    timing = result.get("timing_recommendations", [])
    if timing:
        rprint("\n[bold]Timing Recommendations:[/bold]")
        for rec in timing:
            priority_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(
                rec.get("priority", ""), "white"
            )
            impact = rec.get("tax_impact", 0)
            impact_str = f"[green]saves ${abs(impact):,.0f}[/green]" if impact < 0 else f"[yellow]costs ${impact:,.0f}[/yellow]"
            rprint(f"  [{priority_color}]●[/{priority_color}] {rec.get('action', '')} - {impact_str}")
            if rec.get("deadline"):
                rprint(f"    [dim]Deadline: {rec['deadline']}[/dim]")

    # Summary
    if result.get("summary"):
        rprint(f"\n[bold]Summary:[/bold] {result['summary']}")


@ai_app.command("missing")
def ai_missing(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Identify potentially missing tax documents."""
    from tax_agent.agent import get_agent
    from tax_agent.storage.database import get_database

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    db = get_database()
    documents = db.get_documents(tax_year=tax_year)

    # Build document summary
    docs_summary = []
    for doc in documents:
        docs_summary.append({
            "type": get_enum_value(doc.document_type),
            "issuer": doc.issuer_name,
            "data_keys": list(doc.extracted_data.keys()) if doc.extracted_data else [],
        })

    # Build profile
    profile = {
        "tax_year": tax_year,
        "state": config.state,
        "filing_status": config.get("filing_status"),
        "documents_collected": len(documents),
    }

    rprint(f"[cyan]Analyzing document collection for tax year {tax_year}...[/cyan]")

    agent = get_agent()
    with console.status("[bold green]Running AI missing document analysis..."):
        result = agent.identify_missing_documents(docs_summary, profile)

    # Display completeness score
    score = result.get("collection_completeness_score", 0)
    score_color = "green" if score >= 0.8 else "yellow" if score >= 0.5 else "red"
    ready = result.get("ready_to_file", False)

    rprint(Panel.fit(
        f"[bold]Collection Completeness: [{score_color}]{score:.0%}[/{score_color}][/bold]\n"
        f"Ready to File: {'[green]Yes[/green]' if ready else '[red]No[/red]'}",
        title="Document Collection Status"
    ))

    # Missing documents
    missing = result.get("likely_missing", [])
    if missing:
        rprint("\n[bold yellow]Potentially Missing Documents:[/bold yellow]")
        for doc in missing:
            importance = doc.get("importance", "medium")
            color = {"critical": "red", "high": "red", "medium": "yellow", "low": "blue"}.get(importance, "white")
            irs_risk = "[red]⚠ IRS Match[/red]" if doc.get("irs_matching_risk") else ""

            rprint(f"\n  [{color}]{doc.get('document_type', '')}[/{color}] {irs_risk}")
            rprint(f"    [dim]Reason: {doc.get('reason', '')}[/dim]")
            rprint(f"    [dim]Source: {doc.get('typical_source', '')}[/dim]")
            if doc.get("deadline_concern"):
                rprint(f"    [yellow]⏰ {doc['deadline_concern']}[/yellow]")
    else:
        rprint("\n[green]No obviously missing documents detected![/green]")

    # Blocking documents
    blocking = result.get("blocking_documents", [])
    if blocking:
        rprint("\n[bold red]Blocking Documents (needed before filing):[/bold red]")
        for doc in blocking:
            rprint(f"  [red]✗[/red] {doc}")

    # Nice to have
    nice = result.get("nice_to_have_documents", [])
    if nice:
        rprint("\n[bold blue]Nice to Have:[/bold blue]")
        for doc in nice:
            rprint(f"  [blue]○[/blue] {doc}")

    # Verification suggestions
    verifications = result.get("verification_suggestions", [])
    if verifications:
        rprint("\n[bold]Verification Steps:[/bold]")
        for v in verifications:
            rprint(f"  • {v.get('check', '')}")
            rprint(f"    [dim]{v.get('how', '')}[/dim]")

    # Summary
    if result.get("summary"):
        rprint(f"\n[bold]Assessment:[/bold] {result['summary']}")


@ai_app.command("investments")
def ai_investments(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Deep AI analysis of investment taxes (capital gains, wash sales, harvesting)."""
    from tax_agent.agent import get_agent
    from tax_agent.storage.database import get_database
    from tax_agent.models.documents import DocumentType

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    db = get_database()
    documents = db.get_documents(tax_year=tax_year)

    # Find 1099-B documents
    brokerage_docs = [d for d in documents if d.document_type == DocumentType.FORM_1099_B]

    if not brokerage_docs:
        rprint(f"[yellow]No 1099-B documents found for tax year {tax_year}.[/yellow]")
        rprint("[dim]Collect brokerage statements first using 'tax-agent collect'[/dim]")
        raise typer.Exit(1)

    # Extract transactions
    all_transactions = []
    for doc in brokerage_docs:
        if doc.extracted_data and "transactions" in doc.extracted_data:
            for txn in doc.extracted_data["transactions"]:
                txn["broker"] = doc.issuer_name
                all_transactions.append(txn)

    if not all_transactions:
        rprint("[yellow]No transactions found in 1099-B documents.[/yellow]")
        raise typer.Exit(1)

    rprint(f"[cyan]Analyzing {len(all_transactions)} investment transactions for tax year {tax_year}...[/cyan]")

    agent = get_agent()
    with console.status("[bold green]Running AI investment tax analysis..."):
        result = agent.analyze_investment_taxes(all_transactions)

    # Capital gains summary
    cg = result.get("capital_gains_summary", {})
    if cg:
        rprint(Panel.fit(
            f"[bold]Capital Gains Summary[/bold]\n\n"
            f"Short-term Gains:  [green]${cg.get('short_term_gains', 0):,.2f}[/green]\n"
            f"Short-term Losses: [red]${cg.get('short_term_losses', 0):,.2f}[/red]\n"
            f"[bold]Net Short-term:    ${cg.get('net_short_term', 0):,.2f}[/bold]\n\n"
            f"Long-term Gains:   [green]${cg.get('long_term_gains', 0):,.2f}[/green]\n"
            f"Long-term Losses:  [red]${cg.get('long_term_losses', 0):,.2f}[/red]\n"
            f"[bold]Net Long-term:     ${cg.get('net_long_term', 0):,.2f}[/bold]\n\n"
            f"[bold cyan]Total Net Gain/Loss: ${cg.get('total_net_gain_loss', 0):,.2f}[/bold cyan]",
            title="Investment Summary"
        ))

    # Wash sales
    wash_sales = result.get("wash_sales", [])
    if wash_sales:
        rprint("\n[bold red]⚠ Wash Sale Violations Detected:[/bold red]")
        for ws in wash_sales:
            rprint(f"\n  [red]{ws.get('security', '')}[/red]")
            rprint(f"    Sold: {ws.get('sale_date', '')} | Repurchased: {ws.get('repurchase_date', '')}")
            rprint(f"    [red]Disallowed Loss: ${ws.get('disallowed_loss', 0):,.2f}[/red]")
            rprint(f"    [dim]{ws.get('action_required', '')}[/dim]")
    else:
        rprint("\n[green]✓ No wash sale violations detected[/green]")

    # Tax-loss harvesting opportunities
    harvesting = result.get("harvesting_opportunities", [])
    if harvesting:
        rprint("\n[bold green]Tax-Loss Harvesting Opportunities:[/bold green]")
        for opp in harvesting:
            rprint(f"\n  [cyan]{opp.get('security', '')}[/cyan]")
            rprint(f"    Current Loss: [red]${opp.get('current_loss', 0):,.2f}[/red]")
            rprint(f"    [green]Potential Tax Savings: ${opp.get('tax_savings_estimate', 0):,.2f}[/green]")
            if opp.get("replacement_suggestions"):
                rprint(f"    [dim]Replacements: {', '.join(opp['replacement_suggestions'])}[/dim]")

    # NIIT Analysis
    niit = result.get("niit_analysis", {})
    if niit.get("applies"):
        rprint(f"\n[yellow]⚠ Net Investment Income Tax (3.8%) Applies[/yellow]")
        rprint(f"   Estimated NIIT: ${niit.get('estimated_niit', 0):,.2f}")
        if niit.get("mitigation_strategies"):
            rprint(f"   [dim]Strategies: {', '.join(niit['mitigation_strategies'])}[/dim]")

    # Estimated tax
    est_tax = result.get("estimated_tax", {})
    if est_tax:
        rprint(Panel.fit(
            f"[bold]Estimated Investment Taxes[/bold]\n\n"
            f"Short-term Tax (ordinary rates): ${est_tax.get('short_term_tax', 0):,.2f}\n"
            f"Long-term Tax (0/15/20%):        ${est_tax.get('long_term_tax', 0):,.2f}\n"
            f"NIIT (3.8%):                     ${est_tax.get('niit', 0):,.2f}\n"
            f"[bold]Total Federal:                   ${est_tax.get('total_federal', 0):,.2f}[/bold]\n\n"
            f"Effective Rate: {est_tax.get('effective_rate', 'N/A')}",
            title="Tax Estimate"
        ))

    # Optimization actions
    actions = result.get("optimization_actions", [])
    if actions:
        rprint("\n[bold]Optimization Actions:[/bold]")
        for action in actions:
            priority_color = {"high": "red", "medium": "yellow", "low": "blue"}.get(
                action.get("priority", ""), "white"
            )
            rprint(f"\n  [{priority_color}]●[/{priority_color}] {action.get('action', '')}")
            rprint(f"    [green]Potential Savings: ${action.get('potential_savings', 0):,.2f}[/green]")
            if action.get("deadline"):
                rprint(f"    [dim]Deadline: {action['deadline']}[/dim]")

    # Summary
    if result.get("summary"):
        rprint(f"\n[bold]Summary:[/bold] {result['summary']}")


@ai_app.command("plan")
def ai_plan(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Generate forward-looking tax planning recommendations."""
    from tax_agent.agent import get_agent
    from tax_agent.storage.database import get_database
    from tax_agent.analyzers.implications import TaxAnalyzer

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    db = get_database()
    documents = db.get_documents(tax_year=tax_year)

    # Build current year data
    analyzer = TaxAnalyzer(tax_year)
    income_summary = analyzer.calculate_income_summary(documents) if documents else {}

    current_year_data = {
        "tax_year": tax_year,
        "income": income_summary,
        "total_income": sum(income_summary.values()) if income_summary else 0,
        "documents_count": len(documents),
    }

    profile = {
        "state": config.state,
        "filing_status": config.get("filing_status", "single"),
    }

    rprint(f"[cyan]Generating tax planning recommendations for {tax_year} and beyond...[/cyan]")

    agent = get_agent()
    with console.status("[bold green]Running AI tax planning analysis..."):
        result = agent.generate_tax_planning_recommendations(current_year_data, profile)

    # Immediate actions
    immediate = result.get("immediate_actions", [])
    if immediate:
        rprint(Panel.fit(
            "[bold]Immediate Actions Required[/bold]\n\n" +
            "\n".join(
                f"[{'red' if a.get('priority') == 'critical' else 'yellow'}]● {a.get('action', '')}[/{'red' if a.get('priority') == 'critical' else 'yellow'}]\n"
                f"   Deadline: {a.get('deadline', 'N/A')} | Benefit: [green]${a.get('estimated_benefit', 0):,.0f}[/green]"
                for a in immediate[:5]
            ),
            title="⚡ Action Items"
        ))

    # Quarterly estimated taxes
    quarterly = result.get("quarterly_estimated_taxes", {})
    if quarterly.get("required"):
        rprint(Panel.fit(
            f"[bold yellow]Quarterly Estimated Taxes Required[/bold yellow]\n\n"
            f"Next Payment Due: {quarterly.get('next_payment_due', 'N/A')}\n"
            f"Recommended Amount: [bold]${quarterly.get('recommended_amount', 0):,.2f}[/bold]\n\n"
            f"[dim]{quarterly.get('safe_harbor_method', '')}[/dim]",
            title="Estimated Taxes"
        ))

    # Retirement strategy
    retirement = result.get("retirement_strategy", {})
    if retirement:
        rprint("\n[bold cyan]Retirement Contribution Strategy:[/bold cyan]")
        if retirement.get("recommended_401k_contribution"):
            rprint(f"  401(k): [green]${retirement['recommended_401k_contribution']:,.0f}[/green]")
        if retirement.get("recommended_ira_contribution"):
            ira_type = retirement.get("ira_type_recommendation", "")
            rprint(f"  IRA ({ira_type}): [green]${retirement['recommended_ira_contribution']:,.0f}[/green]")
        if retirement.get("backdoor_roth_eligible"):
            rprint("  [yellow]✓ Backdoor Roth eligible - consider this strategy[/yellow]")
        for rec in retirement.get("additional_recommendations", []):
            rprint(f"  • {rec}")

    # Investment strategy
    investment = result.get("investment_strategy", [])
    if investment:
        rprint("\n[bold]Investment Tax Strategy:[/bold]")
        for rec in investment:
            rprint(f"  • {rec.get('recommendation', '')}")
            rprint(f"    [dim]{rec.get('rationale', '')}[/dim]")
            if rec.get("estimated_annual_benefit"):
                rprint(f"    [green]Annual Benefit: ${rec['estimated_annual_benefit']:,.0f}[/green]")

    # Next year projections
    projections = result.get("next_year_projections", {})
    if projections:
        rprint(Panel.fit(
            f"[bold]Projected for Next Year[/bold]\n\n"
            f"Estimated Income: ${projections.get('estimated_income', 0):,.0f}\n"
            f"Estimated Tax: ${projections.get('estimated_tax', 0):,.0f}\n\n"
            f"[bold]Key Opportunities:[/bold]\n" +
            "\n".join(f"  • {o}" for o in projections.get("key_planning_opportunities", [])),
            title="📈 Next Year"
        ))

    # Long-term strategies
    long_term = result.get("long_term_strategies", [])
    if long_term:
        rprint("\n[bold]Long-Term Tax Strategies:[/bold]")
        for strategy in long_term:
            rprint(f"\n  [cyan]{strategy.get('strategy', '')}[/cyan]")
            rprint(f"    Timeline: {strategy.get('timeline', 'N/A')}")
            rprint(f"    [green]Cumulative Benefit: {strategy.get('cumulative_benefit', 'N/A')}[/green]")

    # Warnings
    warnings = result.get("warnings", [])
    if warnings:
        rprint("\n[bold yellow]⚠ Important Considerations:[/bold yellow]")
        for warn in warnings:
            rprint(f"  [yellow]• {warn}[/yellow]")

    # Summary
    if result.get("summary"):
        rprint(f"\n[bold]Planning Summary:[/bold] {result['summary']}")


@ai_app.command("subagents")
def ai_subagents_list() -> None:
    """List available specialized AI subagents."""
    from tax_agent.subagents import list_subagents

    subagents = list_subagents()

    rprint(Panel.fit(
        "[bold]Specialized Tax Subagents[/bold]\n\n"
        "These subagents can be invoked for specific tax analysis tasks.\n"
        "Use 'tax-agent ai invoke <name>' to run a subagent.",
        title="Available Subagents"
    ))

    table = Table()
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")

    for agent in subagents:
        table.add_row(agent["name"], agent["description"])

    console.print(table)

    rprint("\n[dim]Example: tax-agent ai invoke deduction-finder --prompt \"Find all deductions for my W-2 income\"[/dim]")


@ai_app.command("invoke")
def ai_invoke_subagent(
    name: Annotated[str, typer.Argument(help="Subagent name (e.g., deduction-finder)")],
    prompt: Annotated[Optional[str], typer.Option("--prompt", "-p", help="Task prompt for the subagent")] = None,
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Invoke a specialized subagent for targeted tax analysis."""
    from tax_agent.subagents import get_subagent, list_subagents

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    # Check if SDK is enabled
    if not config.use_agent_sdk:
        rprint("[yellow]Agent SDK not enabled. Subagents require the SDK.[/yellow]")
        rprint("[dim]Enable with: tax-agent config set use_agent_sdk true[/dim]")
        raise typer.Exit(1)

    # Validate subagent name
    subagent = get_subagent(name)
    if not subagent:
        rprint(f"[red]Unknown subagent: {name}[/red]")
        rprint("\n[dim]Available subagents:[/dim]")
        for agent in list_subagents():
            rprint(f"  • {agent['name']}: {agent['description']}")
        raise typer.Exit(1)

    # Get prompt if not provided
    if not prompt:
        rprint(f"[bold]{subagent.name}[/bold]: {subagent.description}\n")
        prompt = Prompt.ask("[cyan]Enter your task for this subagent[/cyan]")
        if not prompt.strip():
            rprint("[red]No prompt provided.[/red]")
            raise typer.Exit(1)

    tax_year = year or config.tax_year

    # Get source directory from documents
    from tax_agent.storage.database import get_database
    db = get_database()
    documents = db.get_documents(tax_year=tax_year)
    source_dir = None
    if documents:
        for doc in documents:
            if doc.file_path:
                source_dir = Path(doc.file_path).parent
                break

    rprint(f"\n[cyan]Invoking {subagent.name} for tax year {tax_year}...[/cyan]")
    rprint(f"[dim]Task: {prompt[:100]}{'...' if len(prompt) > 100 else ''}[/dim]\n")

    # Import and run SDK
    from tax_agent.agent_sdk import get_sdk_agent, sdk_available

    if not sdk_available():
        rprint("[red]Agent SDK not installed. Install claude-code-sdk package.[/red]")
        raise typer.Exit(1)

    sdk_agent = get_sdk_agent()

    # Build context prompt
    context_prompt = f"""Tax Year: {tax_year}
State: {config.state or 'Not specified'}
Documents collected: {len(documents)}

Task: {prompt}"""

    # Run with streaming output
    with console.status(f"[bold green]{subagent.name} is working..."):
        result = sdk_agent.invoke_subagent(name, context_prompt, source_dir)

    rprint(Panel(result, title=f"{subagent.name} Analysis", border_style="blue"))


@ai_app.command("review-return")
def ai_review_return(
    return_file: Annotated[Path, typer.Argument(help="Path to completed tax return PDF")],
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
    thorough: Annotated[bool, typer.Option("--thorough", "-t", help="Extra thorough review with web research")] = False,
) -> None:
    """
    AI-powered review of a completed tax return.

    This enhanced review uses the Agent SDK to:
    - Cross-reference all amounts against source documents
    - Verify calculations match IRS requirements
    - Search for missed deductions and credits
    - Check for common filing errors
    - Look up current tax rules when needed

    More thorough than the basic 'review' command.
    """
    from tax_agent.collectors.ocr import extract_text_with_ocr
    from tax_agent.storage.database import get_database
    from tax_agent.utils import get_enum_value as _get_enum

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    # Resolve file path
    resolved_file, suggestions = resolve_file_path(return_file)
    if resolved_file is None:
        rprint(f"[red]File not found: {return_file}[/red]")
        if suggestions:
            rprint("\n[dim]Did you mean one of these?[/dim]")
            for s in suggestions[:5]:
                rprint(f"  • {s}")
        raise typer.Exit(1)

    return_file = resolved_file
    tax_year = year or config.tax_year

    rprint(Panel.fit(
        f"[bold]AI-Powered Tax Return Review[/bold]\n\n"
        f"File: {return_file.name}\n"
        f"Tax Year: {tax_year}\n"
        f"Mode: {'Thorough (with web research)' if thorough else 'Standard'}",
        title="Review Setup"
    ))

    # Extract return text
    rprint("\n[cyan]Extracting return content...[/cyan]")
    with console.status("[bold green]Processing tax return..."):
        return_text = extract_text_with_ocr(return_file)

    if not return_text or len(return_text.strip()) < 100:
        rprint("[red]Could not extract sufficient text from the return.[/red]")
        raise typer.Exit(1)

    rprint(f"[dim]Extracted {len(return_text):,} characters from return[/dim]")

    # Get source documents
    db = get_database()
    documents = db.get_documents(tax_year=tax_year)

    if not documents:
        rprint(f"[yellow]Warning: No source documents collected for {tax_year}.[/yellow]")
        rprint("[dim]Review will be limited without source documents to cross-reference.[/dim]\n")

    # Build source document summary
    source_summaries = []
    source_dir = None
    for doc in documents:
        summary = f"- {_get_enum(doc.document_type)} from {doc.issuer_name}"
        if doc.extracted_data:
            # Add key amounts for cross-reference
            if _get_enum(doc.document_type) == "W2":
                wages = doc.extracted_data.get("box_1", 0)
                withheld = doc.extracted_data.get("box_2", 0)
                summary += f": Wages ${wages:,.2f}, Fed withheld ${withheld:,.2f}"
            elif "1099_INT" in _get_enum(doc.document_type):
                interest = doc.extracted_data.get("box_1", 0)
                summary += f": Interest ${interest:,.2f}"
            elif "1099_DIV" in _get_enum(doc.document_type):
                div = doc.extracted_data.get("box_1a", 0)
                summary += f": Dividends ${div:,.2f}"
            elif "1099_B" in _get_enum(doc.document_type):
                proceeds = doc.extracted_data.get("summary", {}).get("total_proceeds", 0)
                summary += f": Proceeds ${proceeds:,.2f}"
        source_summaries.append(summary)

        if doc.file_path and source_dir is None:
            source_dir = Path(doc.file_path).parent

    source_docs_text = "\n".join(source_summaries) if source_summaries else "No source documents available"

    # Check if SDK is available for enhanced review
    use_sdk = config.use_agent_sdk
    if use_sdk:
        from tax_agent.agent_sdk import sdk_available
        use_sdk = sdk_available()

    if use_sdk:
        rprint("\n[cyan]Running AI-powered review with Agent SDK...[/cyan]")
        rprint("[dim]The agent will cross-reference source documents and verify calculations.[/dim]\n")

        from tax_agent.agent_sdk import get_sdk_agent

        sdk_agent = get_sdk_agent()

        # Build comprehensive review prompt
        review_prompt = f"""You are an EXPERT IRS auditor reviewing a completed tax return.

## YOUR TASK
Perform a thorough review of this tax return. Cross-reference EVERY amount against the source documents.

## SOURCE DOCUMENTS FOR {tax_year}:
{source_docs_text}

## TAX RETURN CONTENT:
{return_text[:15000]}

## REVIEW CHECKLIST - Check ALL of these:

### 1. INCOME VERIFICATION (IRS matches these!)
- [ ] W-2 wages match Line 1
- [ ] 1099-INT interest on Schedule B
- [ ] 1099-DIV dividends on Schedule B
- [ ] 1099-B capital gains on Schedule D
- [ ] Any missing income sources?

### 2. DEDUCTION REVIEW
- [ ] Standard vs itemized - is the choice optimal?
- [ ] SALT deduction capped at $10,000?
- [ ] Charitable contributions reasonable?
- [ ] Above-the-line deductions claimed?

### 3. CREDIT VERIFICATION
- [ ] Child Tax Credit calculated correctly?
- [ ] Education credits eligible?
- [ ] Any missed credits?

### 4. MATHEMATICAL ACCURACY
- [ ] AGI calculation correct
- [ ] Tax from tables matches income
- [ ] Refund/owed arithmetic correct

### 5. OPTIMIZATION OPPORTUNITIES
- [ ] Could different filing status save money?
- [ ] Retirement contributions maximized?
- [ ] Tax-loss harvesting opportunities?

## OUTPUT FORMAT
For each finding, provide:
- **SEVERITY**: ERROR (must fix) / WARNING (investigate) / OPPORTUNITY (money left on table)
- **ISSUE**: Clear description with specific amounts
- **EXPECTED vs ACTUAL**: What numbers should be
- **TAX IMPACT**: Dollar amount at stake
- **ACTION**: Specific fix or optimization

Be AGGRESSIVE in finding issues. Cross-reference everything."""

        if thorough:
            review_prompt += """

## ADDITIONAL THOROUGH CHECKS
Since thorough mode is enabled:
- Use WebSearch to verify current IRS limits and rules
- Look up any uncertain tax treatments
- Check for recent tax law changes that might apply
- Verify state-specific rules if applicable"""

        # Run the SDK review
        response_parts = []

        async def run_review():
            include_web = thorough and config.agent_sdk_allow_web
            async for chunk in sdk_agent.review_return_async(
                return_text[:15000],
                source_docs_text,
                source_dir,
            ):
                response_parts.append(chunk)
                rprint("[dim].[/dim]", end="")

        with console.status("[bold green]AI agent is reviewing..."):
            asyncio.run(run_review())

        rprint()  # Newline after progress
        review_result = "".join(response_parts)

    else:
        # Fall back to legacy agent
        rprint("\n[yellow]Agent SDK not enabled. Using standard AI review.[/yellow]")
        rprint("[dim]Enable SDK for enhanced review: tax-agent config set use_agent_sdk true[/dim]\n")

        from tax_agent.agent import get_agent

        agent = get_agent()
        with console.status("[bold green]Running AI review..."):
            review_result = agent.review_tax_return(return_text[:15000], source_docs_text)

    # Display results
    rprint(Panel(
        review_result,
        title="AI Tax Return Review",
        border_style="blue",
        padding=(1, 2),
    ))

    # Summary stats
    errors = review_result.lower().count("error")
    warnings = review_result.lower().count("warning")
    opportunities = review_result.lower().count("opportunity")

    rprint(f"\n[bold]Review Summary:[/bold]")
    if errors > 0:
        rprint(f"  [red]● {errors} potential error(s) found[/red]")
    if warnings > 0:
        rprint(f"  [yellow]● {warnings} warning(s) to investigate[/yellow]")
    if opportunities > 0:
        rprint(f"  [green]● {opportunities} optimization opportunity(ies)[/green]")

    if errors == 0 and warnings == 0:
        rprint("  [green]✓ No major issues detected[/green]")

    # Export option
    review_md = f"""# AI Tax Return Review - {tax_year}

**File:** {return_file.name}
**Review Date:** {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}
**Mode:** {'Thorough' if thorough else 'Standard'}
**Source Documents:** {len(documents)}

---

{review_result}

---
*Generated by Tax Prep Agent AI Review*
"""
    prompt_export(review_md, f"ai-review-{tax_year}", "AI review report")


# Document subcommands
@documents_app.command("list")
def documents_list(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Filter by tax year")] = None,
    folder: Annotated[bool, typer.Option("--folder", "-f", help="Show folder tree view")] = False,
    tag: Annotated[Optional[str], typer.Option("--tag", "-t", help="Filter by tag")] = None,
) -> None:
    """List all collected tax documents."""
    from rich.tree import Tree
    from tax_agent.storage.database import get_database

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    db = get_database()

    # Build filter
    tag_filter = [tag] if tag else None
    documents = db.get_documents(tax_year=tax_year, tags=tag_filter)

    if not documents:
        if tag:
            rprint(f"[yellow]No documents with tag '{tag}' for tax year {tax_year}.[/yellow]")
        else:
            rprint(f"[yellow]No documents collected for tax year {tax_year}.[/yellow]")
        return

    if folder:
        # Folder tree view
        from tax_agent.models.documents import group_documents_by_folder
        by_folder = group_documents_by_folder(documents)

        tree = Tree(f"[bold blue]{tax_year}[/bold blue]")
        for folder_name in sorted(by_folder.keys()):
            folder_branch = tree.add(f"[bold cyan]{folder_name}[/bold cyan]")
            for doc in by_folder[folder_name]:
                tags_str = f" [magenta][{', '.join(doc.tags)}][/magenta]" if doc.tags else ""
                status = "[yellow]*[/yellow]" if doc.needs_review else ""
                folder_branch.add(
                    f"{get_enum_value(doc.document_type)} from {doc.issuer_name} "
                    f"[dim]({doc.id[:8]})[/dim]{tags_str}{status}"
                )
        console.print(tree)
    else:
        # Table view
        table = Table(title=f"Tax Documents - {tax_year}")
        table.add_column("ID", style="dim")
        table.add_column("Type", style="cyan")
        table.add_column("Issuer", style="white")
        table.add_column("Tags", style="magenta")
        table.add_column("Status", style="green")

        for doc in documents:
            status = "[yellow]Review[/yellow]" if doc.needs_review else "[green]Ready[/green]"
            tags_str = ", ".join(doc.tags) if doc.tags else "-"
            table.add_row(
                doc.id[:8] + "...",
                get_enum_value(doc.document_type),
                doc.issuer_name[:30],
                tags_str[:20],
                status,
            )
        console.print(table)

    # Show summary
    all_tags = db.get_all_tags(tax_year=tax_year)
    tags_msg = f" | Tags: {', '.join(all_tags)}" if all_tags else ""
    rprint(f"\n[dim]{len(documents)} document(s) total{tags_msg}[/dim]")


@documents_app.command("show")
def documents_show(
    doc_id: Annotated[str, typer.Argument(help="Document ID (can be partial)")],
) -> None:
    """Show details of a specific document."""
    from tax_agent.storage.database import get_database
    import json

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    db = get_database()

    # Try exact match first, then partial match
    doc = db.get_document(doc_id)
    if not doc:
        # Search for partial match
        all_docs = db.get_documents()
        matches = [d for d in all_docs if d.id.startswith(doc_id)]
        if len(matches) == 1:
            doc = matches[0]
        elif len(matches) > 1:
            rprint(f"[yellow]Multiple documents match '{doc_id}':[/yellow]")
            for d in matches:
                rprint(f"  {d.id[:8]}... - {get_enum_value(d.document_type)} from {d.issuer_name}")
            return
        else:
            rprint(f"[red]Document not found: {doc_id}[/red]")
            raise typer.Exit(1)

    # Display document details
    rprint(Panel.fit(f"[bold]{get_enum_value(doc.document_type)}[/bold] from [cyan]{doc.issuer_name}[/cyan]", title="Document"))

    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("ID", doc.id)
    table.add_row("Tax Year", str(doc.tax_year))
    table.add_row("Document Type", get_enum_value(doc.document_type))
    table.add_row("Issuer", doc.issuer_name)
    if doc.issuer_ein:
        table.add_row("EIN", doc.issuer_ein)
    table.add_row("Confidence", f"{doc.confidence_score:.0%}")
    table.add_row("Needs Review", "Yes" if doc.needs_review else "No")
    table.add_row("Tags", ", ".join(doc.tags) if doc.tags else "(none)")
    table.add_row("Created", doc.created_at.strftime("%Y-%m-%d %H:%M"))
    if doc.file_path:
        table.add_row("Source File", doc.file_path)

    console.print(table)

    if doc.extracted_data:
        rprint("\n[bold]Extracted Data:[/bold]")
        rprint(json.dumps(doc.extracted_data, indent=2))


@documents_app.command("delete")
def documents_delete(
    doc_id: Annotated[str, typer.Argument(help="Document ID (can be partial, or 'all' to delete all)")],
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year (required with 'all')")] = None,
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Delete a document by ID, or all documents for a tax year."""
    from tax_agent.storage.database import get_database

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    db = get_database()

    if doc_id.lower() == "all":
        tax_year = year or config.tax_year
        documents = db.get_documents(tax_year=tax_year)

        if not documents:
            rprint(f"[yellow]No documents to delete for tax year {tax_year}.[/yellow]")
            return

        if not force:
            if not Confirm.ask(f"[yellow]Delete all {len(documents)} documents for tax year {tax_year}?[/yellow]"):
                rprint("[dim]Cancelled.[/dim]")
                return

        deleted = 0
        for doc in documents:
            if db.delete_document(doc.id):
                deleted += 1

        rprint(f"[green]Deleted {deleted} document(s).[/green]")
    else:
        # Find the document
        doc = db.get_document(doc_id)
        if not doc:
            # Try partial match
            all_docs = db.get_documents()
            matches = [d for d in all_docs if d.id.startswith(doc_id)]
            if len(matches) == 1:
                doc = matches[0]
            elif len(matches) > 1:
                rprint(f"[yellow]Multiple documents match '{doc_id}':[/yellow]")
                for d in matches:
                    rprint(f"  {d.id[:8]}... - {get_enum_value(d.document_type)} from {d.issuer_name}")
                rprint("\n[dim]Please provide a more specific ID.[/dim]")
                return
            else:
                rprint(f"[red]Document not found: {doc_id}[/red]")
                raise typer.Exit(1)

        if not force:
            if not Confirm.ask(f"[yellow]Delete {get_enum_value(doc.document_type)} from {doc.issuer_name}?[/yellow]"):
                rprint("[dim]Cancelled.[/dim]")
                return

        if db.delete_document(doc.id):
            rprint(f"[green]Document deleted.[/green]")
        else:
            rprint(f"[red]Failed to delete document.[/red]")
            raise typer.Exit(1)


@documents_app.command("tag")
def documents_tag(
    doc_id: Annotated[str, typer.Argument(help="Document ID (can be partial)")],
    tags: Annotated[list[str], typer.Argument(help="Tags to add")],
) -> None:
    """Add tags to a document."""
    from tax_agent.storage.database import get_database

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    db = get_database()

    if db.add_tags(doc_id, tags):
        rprint(f"[green]Added tags: {', '.join(tags)}[/green]")
    else:
        rprint(f"[red]Document not found: {doc_id}[/red]")
        raise typer.Exit(1)


@documents_app.command("untag")
def documents_untag(
    doc_id: Annotated[str, typer.Argument(help="Document ID (can be partial)")],
    tags: Annotated[list[str], typer.Argument(help="Tags to remove")],
) -> None:
    """Remove tags from a document."""
    from tax_agent.storage.database import get_database

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    db = get_database()

    if db.remove_tags(doc_id, tags):
        rprint(f"[green]Removed tags: {', '.join(tags)}[/green]")
    else:
        rprint(f"[red]Document not found: {doc_id}[/red]")
        raise typer.Exit(1)


@documents_app.command("tags")
def documents_tags(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Filter by tax year")] = None,
) -> None:
    """List all tags in use."""
    from tax_agent.storage.database import get_database

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    db = get_database()
    tag_counts = db.get_tag_counts(tax_year=tax_year)  # Single query for all tag counts

    if not tag_counts:
        rprint(f"[yellow]No tags in use for tax year {tax_year}.[/yellow]")
        rprint("[dim]Add tags with: tax-agent documents tag <doc_id> <tag1> [tag2] ...[/dim]")
        return

    table = Table(title=f"Tags - {tax_year}")
    table.add_column("Tag", style="magenta")
    table.add_column("Documents", style="cyan")

    for tag in sorted(tag_counts.keys()):
        table.add_row(tag, str(tag_counts[tag]))

    console.print(table)


@documents_app.command("folders")
def documents_folders(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Filter by tax year")] = None,
) -> None:
    """Show documents organized by folder."""
    from rich.tree import Tree
    from tax_agent.models.documents import group_documents_by_folder
    from tax_agent.storage.database import get_database

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    db = get_database()
    documents = db.get_documents(tax_year=tax_year)

    if not documents:
        rprint(f"[yellow]No documents collected for tax year {tax_year}.[/yellow]")
        return

    by_folder = group_documents_by_folder(documents)

    tree = Tree(f"[bold blue]{tax_year}[/bold blue]")
    for folder_name in sorted(by_folder.keys()):
        folder_branch = tree.add(f"[bold cyan]{folder_name}[/bold cyan]")
        for doc in by_folder[folder_name]:
            tags_str = f" [magenta][{', '.join(doc.tags)}][/magenta]" if doc.tags else ""
            status = "[yellow]*[/yellow]" if doc.needs_review else ""
            folder_branch.add(
                f"{get_enum_value(doc.document_type)} from {doc.issuer_name} "
                f"[dim]({doc.id[:8]})[/dim]{tags_str}{status}"
            )

    console.print(tree)
    rprint(f"\n[dim]{len(documents)} document(s) total[/dim]")


# Context subcommands
@context_app.command("show")
def context_show() -> None:
    """Display the TAX_CONTEXT.md steering document."""
    from tax_agent.context import get_tax_context

    ctx = get_tax_context()

    if not ctx.exists():
        rprint("[yellow]No TAX_CONTEXT.md file found.[/yellow]")
        rprint(f"[dim]Create one with: tax-agent context create[/dim]")
        rprint(f"[dim]Location: {ctx.context_path}[/dim]")
        return

    content = ctx.load()
    summary = ctx.get_summary()
    modified = summary["modified"].strftime("%Y-%m-%d %H:%M") if summary["modified"] else "unknown"

    rprint(Panel.fit(f"[bold]TAX_CONTEXT.md[/bold]", subtitle=f"Modified: {modified}"))
    rprint(f"[dim]Path: {ctx.context_path}[/dim]\n")
    rprint(Markdown(content))


@context_app.command("create")
def context_create() -> None:
    """Create a new TAX_CONTEXT.md from template."""
    from tax_agent.context import get_tax_context

    ctx = get_tax_context()

    if ctx.exists():
        rprint(f"[yellow]TAX_CONTEXT.md already exists at {ctx.context_path}[/yellow]")
        rprint("[dim]Use 'tax-agent context edit' to modify, or 'tax-agent context reset' to replace.[/dim]")
        return

    ctx.create_from_template()
    rprint(f"[green]Created TAX_CONTEXT.md at {ctx.context_path}[/green]")
    rprint("\n[dim]Edit this file to describe your tax situation.[/dim]")
    rprint("[dim]Use 'tax-agent context edit' to open in your editor.[/dim]")


@context_app.command("edit")
def context_edit() -> None:
    """Open TAX_CONTEXT.md in your default editor."""
    from tax_agent.context import get_tax_context

    ctx = get_tax_context()

    if not ctx.exists():
        ctx.create_from_template()
        rprint(f"[green]Created TAX_CONTEXT.md at {ctx.context_path}[/green]")

    if ctx.open_in_editor():
        rprint(f"[green]Opening {ctx.context_path} in editor...[/green]")
    else:
        rprint("[yellow]Could not open editor automatically.[/yellow]")
        rprint(f"Please edit manually: {ctx.context_path}")
        rprint("\n[dim]Tip: Set the EDITOR environment variable to specify your preferred editor.[/dim]")


@context_app.command("reset")
def context_reset(
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Reset TAX_CONTEXT.md to the default template."""
    from tax_agent.context import get_tax_context

    ctx = get_tax_context()

    if ctx.exists() and not force:
        if not Confirm.ask("[yellow]Replace existing TAX_CONTEXT.md with fresh template?[/yellow]"):
            rprint("[dim]Cancelled.[/dim]")
            return

    ctx.create_from_template()
    rprint(f"[green]Reset TAX_CONTEXT.md to default template.[/green]")


@context_app.command("path")
def context_path() -> None:
    """Show the path to TAX_CONTEXT.md."""
    from tax_agent.context import get_tax_context

    ctx = get_tax_context()
    exists = "[green](exists)[/green]" if ctx.exists() else "[yellow](not created)[/yellow]"
    rprint(f"TAX_CONTEXT.md path: {ctx.context_path} {exists}")


@context_app.command("info")
def context_info() -> None:
    """Show information about the tax context file."""
    from tax_agent.context import get_tax_context

    ctx = get_tax_context()
    summary = ctx.get_summary()

    if not summary["exists"]:
        rprint("[yellow]TAX_CONTEXT.md does not exist.[/yellow]")
        rprint(f"[dim]Create with: tax-agent context create[/dim]")
        return

    table = Table(title="Tax Context Info")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Path", str(summary["path"]))
    table.add_row("Size", f"{summary['size']} bytes")
    table.add_row("Sections", str(summary["sections"]))
    table.add_row("Modified", summary["modified"].strftime("%Y-%m-%d %H:%M") if summary["modified"] else "N/A")
    table.add_row("Has Content", "Yes" if summary["has_content"] else "No (still template)")

    console.print(table)

    # Show extracted info
    info = ctx.extract_key_info()
    if info:
        rprint("\n[bold]Extracted Information:[/bold]")
        for key, value in info.items():
            if isinstance(value, list):
                rprint(f"  [cyan]{key}:[/cyan] {', '.join(value)}")
            else:
                rprint(f"  [cyan]{key}:[/cyan] {value}")


# Config subcommands
@config_app.command("set")
def config_set(
    key: Annotated[str, typer.Argument(help="Configuration key")],
    value: Annotated[str, typer.Argument(help="Configuration value")],
) -> None:
    """Set a configuration value."""
    config = get_config()

    key_lower = key.lower()
    valid_keys = ["state", "tax_year", "filing_status", "model", "auto_redact_ssn"]

    if key_lower not in valid_keys:
        rprint(f"[red]Unknown configuration key: {key}[/red]")
        rprint(f"Valid keys: {', '.join(valid_keys)}")
        raise typer.Exit(1)

    # Type conversion
    if key_lower == "tax_year":
        value = int(value)  # type: ignore
    elif key_lower == "auto_redact_ssn":
        value = value.lower() in ("true", "1", "yes")  # type: ignore
    elif key_lower == "state":
        value = value.upper()

    config.set(key_lower, value)
    rprint(f"[green]Set {key_lower} = {value}[/green]")


@config_app.command("get")
def config_get(
    key: Annotated[Optional[str], typer.Argument(help="Configuration key")] = None,
) -> None:
    """Get configuration value(s)."""
    config = get_config()

    if key:
        value = config.get(key.lower())
        if value is None:
            rprint(f"[yellow]{key} is not set[/yellow]")
        else:
            rprint(f"{key} = {value}")
    else:
        # Show all config
        table = Table(title="Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")

        for k, v in config.to_dict().items():
            table.add_row(k, str(v) if v is not None else "[dim]Not set[/dim]")

        console.print(table)


@config_app.command("api-key")
def config_api_key() -> None:
    """Update the Anthropic API key."""
    config = get_config()

    api_key = Prompt.ask(
        "[bold]Enter your Anthropic API key[/bold]",
        password=True
    )

    config.set_api_key(api_key)
    rprint("[green]API key updated successfully.[/green]")


@config_app.command("brave-key")
def config_brave_key() -> None:
    """Set up Brave Search API key for web research.

    Get a free API key at https://brave.com/search/api/
    Saves the key to .env in the project root.
    """
    from tax_agent.env import get_env_path, write_env_key

    rprint("[cyan]Brave Search enables real-time tax research (IRS rules, law changes, state rules).[/cyan]")
    rprint("[dim]Get a free API key at: https://brave.com/search/api/[/dim]\n")

    api_key = Prompt.ask(
        "[bold]Enter your Brave Search API key[/bold]",
        password=True,
    )

    if not api_key.strip():
        rprint("[yellow]No key entered. Brave Search not configured.[/yellow]")
        return

    env_path = get_env_path()
    write_env_key(env_path, "BRAVE_API_KEY", api_key.strip())
    rprint(f"[green]Brave Search API key saved to {env_path}[/green]")
    rprint("[green]Web research is now enabled.[/green]")


# Research subcommands
@research_app.command("topic")
def research_topic(
    topic: Annotated[str, typer.Argument(help="Tax topic to research")],
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Research a specific tax topic with current IRS guidance."""
    from tax_agent.research import TaxResearcher

    config = get_config()
    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    researcher = TaxResearcher(tax_year)

    rprint(f"[cyan]Researching: {topic} (Tax Year {tax_year})...[/cyan]\n")

    with console.status("[bold green]Searching for current tax guidance..."):
        result = researcher.research_topic(topic)

    rprint(Panel(result, title=f"Research: {topic}", border_style="blue"))


@research_app.command("limits")
def research_limits(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Verify current IRS contribution limits and thresholds."""
    from tax_agent.research import TaxResearcher

    config = get_config()
    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    researcher = TaxResearcher(tax_year)

    with console.status(f"[bold green]Verifying {tax_year} IRS limits..."):
        result = researcher.research_current_limits()

    if "error" in result:
        rprint(f"[red]Error: {result['error']}[/red]")
        return

    rprint(Panel.fit(f"[bold]IRS Limits for Tax Year {tax_year}[/bold]", title="Verified Limits"))

    limits = result.get("limits", {})
    if limits:
        table = Table(title="Contribution & Deduction Limits")
        table.add_column("Item", style="cyan")
        table.add_column("Amount", style="green", justify="right")
        table.add_column("Source", style="dim")

        for key, info in limits.items():
            if isinstance(info, dict):
                amount = info.get("amount", "N/A")
                source = info.get("source", "")
                amount_str = f"${amount:,}" if isinstance(amount, (int, float)) else str(amount)
                table.add_row(key.replace("_", " ").title(), amount_str, source)

        console.print(table)

    changes = result.get("recent_changes", [])
    if changes:
        rprint("\n[bold yellow]Recent Changes:[/bold yellow]")
        for change in changes:
            rprint(f"  - {change}")


@research_app.command("changes")
def research_changes(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Check for recent tax law changes affecting this tax year."""
    from tax_agent.research import TaxResearcher

    config = get_config()
    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    researcher = TaxResearcher(tax_year)

    with console.status(f"[bold green]Checking for {tax_year} tax law changes..."):
        result = researcher.check_for_law_changes()

    rprint(Panel(result, title=f"Tax Law Changes for {tax_year}", border_style="yellow"))


@research_app.command("state")
def research_state(
    state: Annotated[str, typer.Argument(help="State code (e.g., CA, NY, TX)")],
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
) -> None:
    """Research state-specific tax rules."""
    from tax_agent.research import TaxResearcher
    import json

    config = get_config()
    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    researcher = TaxResearcher(tax_year)

    with console.status(f"[bold green]Researching {state.upper()} tax rules..."):
        result = researcher.verify_state_rules(state.upper())

    if "error" in result:
        rprint(f"[red]Error: {result['error']}[/red]")
        return

    rprint(Panel.fit(f"[bold]{state.upper()} Tax Rules - {tax_year}[/bold]", title="State Tax Info"))

    if result.get("has_income_tax") is False:
        rprint(f"[green]{state.upper()} has NO state income tax![/green]")
    else:
        table = Table(show_header=False, box=None)
        table.add_column("Field", style="cyan", width=25)
        table.add_column("Value", style="white")

        table.add_row("Top Marginal Rate", f"{result.get('top_rate', 0)*100:.2f}%")
        table.add_row("Capital Gains", result.get("capital_gains_treatment", "Unknown"))
        table.add_row("Federal Conformity", result.get("federal_conformity", "Unknown"))

        console.print(table)

        if result.get("notable_credits"):
            rprint("\n[bold]Notable Credits:[/bold]")
            for credit in result["notable_credits"]:
                rprint(f"  - {credit}")

        if result.get("recent_changes"):
            rprint("\n[bold yellow]Recent Changes:[/bold yellow]")
            for change in result["recent_changes"]:
                rprint(f"  - {change}")


# =============================================================================
# Google Drive Commands
# =============================================================================


@drive_app.command(name="auth")
def drive_auth(
    setup: Annotated[
        Optional[Path],
        typer.Option(
            "--setup",
            "-s",
            help="Path to Google OAuth client_secrets.json file for initial setup",
        ),
    ] = None,
    revoke: Annotated[
        bool, typer.Option("--revoke", "-r", help="Revoke stored Google credentials")
    ] = False,
) -> None:
    """Authenticate with Google Drive."""
    from tax_agent.collectors.google_drive import GoogleDriveCollector

    config = get_config()

    if revoke:
        config.clear_google_credentials()
        rprint("[green]Google Drive credentials have been removed.[/green]")
        return

    collector = GoogleDriveCollector()

    if setup:
        # Initial setup with client secrets file
        if not setup.exists():
            rprint(f"[red]File not found: {setup}[/red]")
            raise typer.Exit(1)

        rprint("[cyan]Setting up Google Drive integration...[/cyan]")
        rprint(
            "[dim]This will open a browser window for you to authorize access.[/dim]"
        )

        try:
            collector.authenticate_with_client_file(setup)
            rprint("[green]Google Drive authentication successful![/green]")
            rprint(
                "\n[cyan]You can now use:[/cyan]"
                "\n  tax-agent drive collect <folder-id>  - Process documents from a folder"
                "\n  tax-agent drive list                 - List your folders"
            )
        except Exception as e:
            rprint(f"[red]Authentication failed: {e}[/red]")
            raise typer.Exit(1)
    else:
        # Re-authenticate using stored client config
        if collector.is_authenticated():
            rprint("[green]Already authenticated with Google Drive.[/green]")
            if Confirm.ask("Re-authenticate?", default=False):
                try:
                    collector.authenticate_interactive()
                    rprint("[green]Re-authentication successful![/green]")
                except Exception as e:
                    rprint(f"[red]Authentication failed: {e}[/red]")
                    raise typer.Exit(1)
        else:
            try:
                collector.authenticate_interactive()
                rprint("[green]Google Drive authentication successful![/green]")
            except ValueError as e:
                rprint(f"[red]{e}[/red]")
                rprint(
                    "\n[yellow]To set up Google Drive integration:[/yellow]"
                    "\n1. Go to Google Cloud Console"
                    "\n2. Create a project and enable Drive API"
                    "\n3. Create OAuth credentials (Desktop app type)"
                    "\n4. Download the credentials JSON file"
                    "\n5. Run: tax-agent drive auth --setup <path-to-credentials.json>"
                )
                raise typer.Exit(1)
            except Exception as e:
                rprint(f"[red]Authentication failed: {e}[/red]")
                raise typer.Exit(1)


@drive_app.command(name="list")
def drive_list(
    folder_id: Annotated[
        Optional[str],
        typer.Argument(help="Folder ID to list contents of (default: root)"),
    ] = None,
    files: Annotated[
        bool, typer.Option("--files", "-f", help="Show files instead of folders")
    ] = False,
) -> None:
    """List folders or files in Google Drive."""
    from tax_agent.collectors.google_drive import GoogleDriveCollector

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    collector = GoogleDriveCollector()

    if not collector.is_authenticated():
        rprint(
            "[red]Not authenticated with Google Drive. Run 'tax-agent drive auth' first.[/red]"
        )
        raise typer.Exit(1)

    parent = folder_id or "root"
    parent_name = "Root" if parent == "root" else parent

    try:
        if files:
            # List files
            with console.status(f"[bold green]Listing files in {parent_name}..."):
                items = collector.list_files(parent)

            if not items:
                rprint(f"[yellow]No supported files found in folder.[/yellow]")
                return

            table = Table(title=f"Files in {parent_name}")
            table.add_column("Name", style="cyan")
            table.add_column("Type", style="white")
            table.add_column("ID", style="dim")

            for item in items:
                file_type = "Google Doc" if item.is_google_doc else item.mime_type.split("/")[-1].upper()
                table.add_row(item.name, file_type, item.id)

            console.print(table)
            rprint(f"\n[dim]Found {len(items)} supported file(s)[/dim]")
        else:
            # List folders
            with console.status(f"[bold green]Listing folders in {parent_name}..."):
                items = collector.list_folders(parent)

            if not items:
                rprint(f"[yellow]No folders found in {parent_name}.[/yellow]")
                return

            table = Table(title=f"Folders in {parent_name}")
            table.add_column("Name", style="cyan")
            table.add_column("ID", style="dim")

            for item in items:
                table.add_row(item.name, item.id)

            console.print(table)
            rprint(f"\n[dim]Found {len(items)} folder(s)[/dim]")
            rprint(
                "\n[cyan]To see files in a folder:[/cyan] tax-agent drive list <folder-id> --files"
            )

    except Exception as e:
        rprint(f"[red]Error listing Drive contents: {e}[/red]")
        raise typer.Exit(1)


@drive_app.command(name="collect")
def drive_collect(
    folder_id: Annotated[str, typer.Argument(help="Google Drive folder ID")],
    year: Annotated[
        Optional[int], typer.Option("--year", "-y", help="Tax year")
    ] = None,
    recursive: Annotated[
        bool, typer.Option("--recursive", "-r", help="Include subfolders")
    ] = False,
) -> None:
    """Collect and process tax documents from a Google Drive folder."""
    from tax_agent.collectors.document_classifier import DocumentCollector
    from tax_agent.collectors.google_drive import GoogleDriveCollector

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    drive_collector = GoogleDriveCollector()

    if not drive_collector.is_authenticated():
        rprint(
            "[red]Not authenticated with Google Drive. Run 'tax-agent drive auth' first.[/red]"
        )
        raise typer.Exit(1)

    tax_year = year or config.tax_year

    # Get folder info for display
    folder_info = drive_collector.get_folder_info(folder_id)
    folder_name = folder_info.name if folder_info else folder_id

    rprint(f"[cyan]Processing documents from '{folder_name}' for tax year {tax_year}...[/cyan]")
    if recursive:
        rprint("[dim]Including subfolders[/dim]")

    collector = DocumentCollector()

    try:
        with console.status("[bold green]Downloading and processing files..."):
            results = collector.process_google_drive_folder(
                folder_id, tax_year, recursive=recursive
            )

        if not results:
            rprint("[yellow]No supported files found in folder.[/yellow]")
            return

        rprint(f"\n[bold]Processed {len(results)} file(s):[/bold]")

        success_count = 0
        for filename, result in results:
            if isinstance(result, Exception):
                rprint(f"[red]  {filename}: {result}[/red]")
            else:
                confidence = "high" if result.confidence_score >= 0.8 else "low"
                review_flag = (
                    " [yellow](needs review)[/yellow]" if result.needs_review else ""
                )
                rprint(
                    f"[green]  {filename}: {get_enum_value(result.document_type)} from "
                    f"{result.issuer_name} ({confidence} confidence){review_flag}[/green]"
                )
                success_count += 1

        rprint(f"\n[cyan]Successfully processed {success_count}/{len(results)} files.[/cyan]")

    except Exception as e:
        rprint(f"[red]Error processing Drive folder: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

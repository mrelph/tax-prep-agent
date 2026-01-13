"""CLI commands for the tax prep agent."""

import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from tax_agent.config import get_config


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

app = typer.Typer(
    name="tax-agent",
    help="A CLI agent for tax document collection, analysis, and return review.",
    no_args_is_help=True,
)
console = Console()

# Subcommands
documents_app = typer.Typer(help="Manage collected tax documents")
config_app = typer.Typer(help="Manage configuration")
research_app = typer.Typer(help="Research current tax code and rules")
drive_app = typer.Typer(help="Google Drive integration")
ai_app = typer.Typer(help="Advanced AI-powered tax analysis")
app.add_typer(documents_app, name="documents")
app.add_typer(config_app, name="config")
app.add_typer(research_app, name="research")
app.add_typer(drive_app, name="drive")
app.add_typer(ai_app, name="ai")


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
    rprint(f"Model: claude-sonnet-4-5-20250514")
    rprint(f"Tax Year: {config.tax_year}")
    rprint(f"State: {config.state or 'Not set'}")
    rprint("\nNext steps:")
    rprint("  1. Collect documents: [cyan]tax-agent collect <file>[/cyan]")
    rprint("  2. Run optimization: [cyan]tax-agent optimize[/cyan]")


@app.command()
def status() -> None:
    """Show the current status of the tax agent."""
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
    table.add_row("Model", config.get("model", "claude-sonnet-4-5-20250514"))

    if ai_provider == AI_PROVIDER_AWS_BEDROCK:
        table.add_row("AWS Region", config.aws_region)
        aws_access, _ = config.get_aws_credentials()
        if aws_access:
            table.add_row("AWS Credentials", "Configured (explicit)")
        else:
            table.add_row("AWS Credentials", "Using default chain")
    else:
        table.add_row("API Key", "Configured" if config.get_api_key() else "[red]Not set[/red]")

    table.add_row("Data Directory", str(config.data_dir))

    console.print(table)

    if not config.is_initialized:
        rprint("\n[yellow]Run 'tax-agent init' to get started.[/yellow]")


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
        # Process directory
        if not directory.is_dir():
            rprint(f"[red]Not a directory: {directory}[/red]")
            raise typer.Exit(1)

        rprint(f"[cyan]Processing documents in {directory} for tax year {tax_year}...[/cyan]")

        with console.status("[bold green]Processing files..."):
            results = collector.process_directory(directory, tax_year)

        for file_path, result in results:
            if isinstance(result, Exception):
                rprint(f"[red]  {file_path.name}: {result}[/red]")
            else:
                confidence = "high" if result.confidence_score >= 0.8 else "low"
                review_flag = " [yellow](needs review)[/yellow]" if result.needs_review else ""
                rprint(f"[green]  {file_path.name}: {result.document_type.value} from {result.issuer_name} ({confidence} confidence){review_flag}[/green]")

        success_count = sum(1 for _, r in results if not isinstance(r, Exception))
        rprint(f"\n[cyan]Processed {success_count}/{len(results)} files successfully.[/cyan]")
    else:
        # Process single file
        if not file.exists():
            rprint(f"[red]File not found: {file}[/red]")
            raise typer.Exit(1)

        rprint(f"[cyan]Processing {file.name} for tax year {tax_year}...[/cyan]")

        try:
            with console.status("[bold green]Extracting and analyzing document..."):
                doc = collector.process_file(file, tax_year)

            rprint(f"\n[green]Document processed successfully![/green]")

            # Show document details
            table = Table(title="Document Details")
            table.add_column("Field", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("ID", doc.id[:8] + "...")
            table.add_row("Type", doc.document_type.value)
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
                if doc.document_type.value == "W2":
                    if "box_1" in doc.extracted_data:
                        table.add_row("Wages (Box 1)", f"${doc.extracted_data['box_1']:,.2f}")
                    if "box_2" in doc.extracted_data:
                        table.add_row("Fed Tax Withheld", f"${doc.extracted_data['box_2']:,.2f}")
                elif "1099_INT" in doc.document_type.value:
                    if "box_1" in doc.extracted_data:
                        table.add_row("Interest Income", f"${doc.extracted_data['box_1']:,.2f}")
                elif "1099_DIV" in doc.document_type.value:
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
) -> None:
    """Analyze collected documents for tax implications."""
    from tax_agent.analyzers.implications import TaxAnalyzer

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

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
        with console.status("[bold green]Generating AI analysis..."):
            ai_analysis = analyzer.generate_ai_analysis()

        rprint(Panel(ai_analysis, title="AI Tax Analysis", border_style="blue"))


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
                f"[{color}]{finding.severity.value.upper()}[/{color}]",
                finding.category,
                finding.title,
                impact_str,
            )

        console.print(findings_table)

        # Detailed findings
        rprint("\n[bold]Detailed Findings:[/bold]\n")
        for i, finding in enumerate(review_result.findings, 1):
            color = severity_colors.get(finding.severity, "white")
            rprint(f"[{color}]{i}. {finding.severity.value.upper()}: {finding.title}[/{color}]")
            rprint(f"   {finding.description}")
            if finding.recommendation:
                rprint(f"   [dim]Recommendation: {finding.recommendation}[/dim]")
            rprint("")
    else:
        rprint("\n[green]No issues found in the tax return.[/green]")


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
            "type": doc.document_type.value,
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
            "type": doc.document_type.value,
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
            "type": doc.document_type.value,
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


# Document subcommands
@documents_app.command("list")
def documents_list(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Filter by tax year")] = None,
) -> None:
    """List all collected tax documents."""
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

    table = Table(title=f"Tax Documents - {tax_year}")
    table.add_column("ID", style="dim")
    table.add_column("Type", style="cyan")
    table.add_column("Issuer", style="white")
    table.add_column("Status", style="green")

    for doc in documents:
        status = "[yellow]Review[/yellow]" if doc.needs_review else "[green]Ready[/green]"
        table.add_row(
            doc.id[:8] + "...",
            doc.document_type.value,
            doc.issuer_name[:30],
            status,
        )

    console.print(table)
    rprint(f"\n[dim]{len(documents)} document(s) total[/dim]")


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
                rprint(f"  {d.id[:8]}... - {d.document_type.value} from {d.issuer_name}")
            return
        else:
            rprint(f"[red]Document not found: {doc_id}[/red]")
            raise typer.Exit(1)

    # Display document details
    rprint(Panel.fit(f"[bold]{doc.document_type.value}[/bold] from [cyan]{doc.issuer_name}[/cyan]", title="Document"))

    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("ID", doc.id)
    table.add_row("Tax Year", str(doc.tax_year))
    table.add_row("Document Type", doc.document_type.value)
    table.add_row("Issuer", doc.issuer_name)
    if doc.issuer_ein:
        table.add_row("EIN", doc.issuer_ein)
    table.add_row("Confidence", f"{doc.confidence_score:.0%}")
    table.add_row("Needs Review", "Yes" if doc.needs_review else "No")
    table.add_row("Created", doc.created_at.strftime("%Y-%m-%d %H:%M"))
    if doc.file_path:
        table.add_row("Source File", doc.file_path)

    console.print(table)

    if doc.extracted_data:
        rprint("\n[bold]Extracted Data:[/bold]")
        rprint(json.dumps(doc.extracted_data, indent=2))


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
                    f"[green]  {filename}: {result.document_type.value} from "
                    f"{result.issuer_name} ({confidence} confidence){review_flag}[/green]"
                )
                success_count += 1

        rprint(f"\n[cyan]Successfully processed {success_count}/{len(results)} files.[/cyan]")

    except Exception as e:
        rprint(f"[red]Error processing Drive folder: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

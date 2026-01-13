"""CLI commands for the tax prep agent."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from tax_agent.config import get_config

app = typer.Typer(
    name="tax-agent",
    help="A CLI agent for tax document collection, analysis, and return review.",
    no_args_is_help=True,
)
console = Console()

# Subcommands
documents_app = typer.Typer(help="Manage collected tax documents")
config_app = typer.Typer(help="Manage configuration")
app.add_typer(documents_app, name="documents")
app.add_typer(config_app, name="config")


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
    password = Prompt.ask(
        "\n[bold]Enter a password for encrypting your tax data[/bold]",
        password=True
    )
    password_confirm = Prompt.ask(
        "[bold]Confirm password[/bold]",
        password=True
    )

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
        rprint("[dim]You can either enter credentials now, or leave blank to use")
        rprint("environment variables / IAM role / AWS CLI profile.[/dim]\n")

        use_explicit_creds = Confirm.ask("Enter AWS credentials manually?", default=False)

        if use_explicit_creds:
            aws_access_key = Prompt.ask("AWS Access Key ID")
            aws_secret_key = Prompt.ask("AWS Secret Access Key", password=True)
        else:
            aws_access_key = None
            aws_secret_key = None
            rprint("[dim]Using default AWS credential chain (env vars, IAM role, ~/.aws/credentials)[/dim]")

        aws_region = Prompt.ask("AWS Region", default="us-east-1")

        # Initialize
        with console.status("[bold green]Initializing..."):
            config.initialize(password)
            config.set("ai_provider", ai_provider)
            config.set("aws_region", aws_region)
            if aws_access_key and aws_secret_key:
                config.set_aws_credentials(aws_access_key, aws_secret_key)

        rprint("\n[green]Tax agent initialized with AWS Bedrock![/green]")

    else:
        # Anthropic API setup
        ai_provider = AI_PROVIDER_ANTHROPIC

        api_key = Prompt.ask(
            "\n[bold]Enter your Anthropic API key[/bold]",
            password=True
        )

        if not api_key.startswith("sk-"):
            rprint("[yellow]Warning: API key doesn't look like a valid Anthropic key[/yellow]")
            if not Confirm.ask("Continue anyway?"):
                raise typer.Exit(1)

        # Initialize
        with console.status("[bold green]Initializing..."):
            config.initialize(password)
            config.set("ai_provider", ai_provider)
            config.set_api_key(api_key)

        rprint("\n[green]Tax agent initialized with Anthropic API![/green]")

    rprint(f"Data directory: {config.data_dir}")
    rprint(f"AI Provider: {ai_provider}")
    rprint(f"Model: claude-sonnet-4-5-20250514")
    rprint("\nNext steps:")
    rprint("  1. Set your state: [cyan]tax-agent config set state CA[/cyan]")
    rprint("  2. Collect documents: [cyan]tax-agent collect <file>[/cyan]")


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


if __name__ == "__main__":
    app()

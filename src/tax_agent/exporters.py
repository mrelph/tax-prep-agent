"""Export tax data to various formats (Markdown, PDF)."""

from datetime import datetime
from pathlib import Path
from typing import Any

from tax_agent.storage.database import get_database
from tax_agent.utils import get_enum_value


def export_review_markdown(review: dict) -> str:
    """Export a single review to markdown format."""
    lines = []

    # Header
    lines.append(f"# Tax Return Review - {review['tax_year']}")
    lines.append("")
    lines.append(f"**Review ID:** {review['id']}")
    lines.append(f"**Return Type:** {review['return_type']}")
    lines.append(f"**Review Date:** {review['created_at'][:10]}")
    lines.append("")

    # Overall Assessment
    summary = review.get("summary", {})
    if review.get("overall_assessment") or summary.get("overall_assessment"):
        assessment = review.get("overall_assessment") or summary.get("overall_assessment")
        lines.append("## Overall Assessment")
        lines.append("")
        lines.append(assessment)
        lines.append("")

    # Counts summary
    errors = sum(1 for f in review.get("findings", []) if str(f.get("severity", "")).lower() == "error")
    warnings = sum(1 for f in review.get("findings", []) if str(f.get("severity", "")).lower() == "warning")
    suggestions = sum(1 for f in review.get("findings", []) if str(f.get("severity", "")).lower() == "suggestion")
    if errors or warnings or suggestions:
        lines.append(f"**Summary:** {errors} error(s), {warnings} warning(s), {suggestions} suggestion(s)")
        lines.append("")

    # Summary
    summary = review.get("summary", {})
    if summary:
        lines.append("## Return Summary")
        lines.append("")
        if summary.get("filing_status"):
            lines.append(f"- **Filing Status:** {summary['filing_status']}")
        if summary.get("total_income"):
            lines.append(f"- **Total Income:** ${summary['total_income']:,.2f}")
        if summary.get("wages"):
            lines.append(f"- **Wages:** ${summary['wages']:,.2f}")
        if summary.get("interest_income"):
            lines.append(f"- **Interest Income:** ${summary['interest_income']:,.2f}")
        if summary.get("dividend_income"):
            lines.append(f"- **Dividend Income:** ${summary['dividend_income']:,.2f}")
        if summary.get("capital_gains"):
            lines.append(f"- **Capital Gains:** ${summary['capital_gains']:,.2f}")
        if summary.get("agi"):
            lines.append(f"- **Adjusted Gross Income:** ${summary['agi']:,.2f}")
        if summary.get("standard_deduction"):
            lines.append(f"- **Standard Deduction:** ${summary['standard_deduction']:,.2f}")
        if summary.get("itemized_deductions"):
            lines.append(f"- **Itemized Deductions:** ${summary['itemized_deductions']:,.2f}")
        if summary.get("taxable_income"):
            lines.append(f"- **Taxable Income:** ${summary['taxable_income']:,.2f}")
        if summary.get("total_tax"):
            lines.append(f"- **Total Tax:** ${summary['total_tax']:,.2f}")
        if summary.get("total_credits"):
            lines.append(f"- **Total Credits:** ${summary['total_credits']:,.2f}")
        if summary.get("federal_withholding"):
            lines.append(f"- **Federal Withholding:** ${summary['federal_withholding']:,.2f}")
        if summary.get("refund_amount"):
            lines.append(f"- **Refund Due:** ${summary['refund_amount']:,.2f}")
        if summary.get("amount_owed"):
            lines.append(f"- **Tax Owed:** ${summary['amount_owed']:,.2f}")
        lines.append("")

    # Findings
    findings = review.get("findings", [])
    if findings:
        lines.append("## Findings")
        lines.append("")

        # Group by severity (enum values are lowercase)
        severity_order = [
            ("error", "ERRORS"),
            ("warning", "WARNINGS"),
            ("suggestion", "SUGGESTIONS"),
            ("info", "INFORMATIONAL"),
        ]
        for severity_value, severity_label in severity_order:
            severity_findings = [
                f for f in findings
                if str(f.get("severity", "")).lower() == severity_value
            ]
            if severity_findings:
                lines.append(f"### {severity_label}")
                lines.append("")
                for i, finding in enumerate(severity_findings, 1):
                    lines.append(f"#### {i}. {finding.get('title', 'N/A')}")
                    lines.append("")
                    if finding.get("category"):
                        lines.append(f"**Category:** {finding['category']}")
                        lines.append("")
                    lines.append(finding.get("description", ""))
                    lines.append("")
                    if finding.get("line_reference"):
                        lines.append(f"**Form Reference:** {finding['line_reference']}")
                        lines.append("")
                    if finding.get("expected_value"):
                        lines.append(f"**Expected Value:** {finding['expected_value']}")
                    if finding.get("actual_value"):
                        lines.append(f"**Actual Value:** {finding['actual_value']}")
                    if finding.get("expected_value") or finding.get("actual_value"):
                        lines.append("")
                    if finding.get("recommendation"):
                        lines.append(f"**Recommendation:** {finding['recommendation']}")
                        lines.append("")
                    if finding.get("potential_impact"):
                        lines.append(f"**Potential Tax Impact:** ${finding['potential_impact']:,.2f}")
                        lines.append("")
                    if finding.get("source_document_id"):
                        lines.append(f"**Related Document:** {finding['source_document_id']}")
                        lines.append("")
    else:
        lines.append("## Findings")
        lines.append("")
        lines.append("No issues found.")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Generated by Tax Prep Agent on {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)


def export_documents_markdown(documents: list, tax_year: int) -> str:
    """Export documents summary to markdown format."""
    lines = []

    lines.append(f"# Tax Documents - {tax_year}")
    lines.append("")
    lines.append(f"**Total Documents:** {len(documents)}")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # Group by document type
    doc_types: dict[str, list] = {}
    for doc in documents:
        doc_type = get_enum_value(doc.document_type)
        if doc_type not in doc_types:
            doc_types[doc_type] = []
        doc_types[doc_type].append(doc)

    for doc_type, docs in sorted(doc_types.items()):
        lines.append(f"## {doc_type}")
        lines.append("")
        lines.append("| Issuer | Tax Year | Confidence | Status |")
        lines.append("|--------|----------|------------|--------|")

        for doc in docs:
            status = "Needs Review" if doc.needs_review else "Ready"
            lines.append(f"| {doc.issuer_name} | {doc.tax_year} | {doc.confidence_score:.0%} | {status} |")

        lines.append("")

        # Show extracted data summary for each
        for doc in docs:
            if doc.extracted_data:
                lines.append(f"### {doc.issuer_name}")
                lines.append("")
                for key, value in doc.extracted_data.items():
                    if value is not None:
                        if isinstance(value, (int, float)) and ("amount" in key.lower() or "box" in key.lower()):
                            lines.append(f"- **{key}:** ${value:,.2f}")
                        else:
                            lines.append(f"- **{key}:** {value}")
                lines.append("")

    lines.append("---")
    lines.append(f"*Generated by Tax Prep Agent on {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)


def export_full_report_markdown(tax_year: int) -> str:
    """Export a full tax report for a year to markdown."""
    db = get_database()
    documents = db.get_documents(tax_year=tax_year)
    reviews = db.get_reviews(tax_year=tax_year)

    lines = []

    lines.append(f"# Tax Report - {tax_year}")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Documents section
    lines.append("# Part 1: Collected Documents")
    lines.append("")
    if documents:
        lines.append(export_documents_markdown(documents, tax_year))
    else:
        lines.append("No documents collected for this tax year.")
    lines.append("")

    # Reviews section
    lines.append("# Part 2: Return Reviews")
    lines.append("")
    if reviews:
        for review in reviews:
            lines.append(export_review_markdown(review))
            lines.append("")
    else:
        lines.append("No reviews completed for this tax year.")

    return "\n".join(lines)


def markdown_to_pdf(markdown_content: str, output_path: Path) -> None:
    """Convert markdown content to PDF."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)

    # Process markdown line by line
    lines = markdown_content.split("\n")

    for line in lines:
        line = line.rstrip()

        if not line:
            pdf.ln(4)
            continue

        # Clean markdown syntax
        clean_line = line.replace("**", "").replace("*", "")

        # Reset x position to left margin before each cell
        pdf.set_x(pdf.l_margin)

        # Headers
        if line.startswith("# "):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 16)
            pdf.multi_cell(w=0, h=8, text=clean_line[2:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
        elif line.startswith("## "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(w=0, h=7, text=clean_line[3:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(2)
        elif line.startswith("### "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(w=0, h=6, text=clean_line[4:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.ln(1)
        elif line.startswith("#### "):
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(w=0, h=6, text=clean_line[5:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        # Horizontal rule
        elif line.startswith("---"):
            pdf.ln(4)
            y = pdf.get_y()
            pdf.line(20, y, 190, y)
            pdf.ln(4)
        # List items
        elif line.startswith("- "):
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(w=0, h=5, text="  * " + clean_line[2:], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        # Skip table formatting
        elif line.startswith("|") and "---" in line:
            continue
        # Table rows
        elif line.startswith("|"):
            pdf.set_font("Courier", "", 9)
            cells = [c.strip() for c in line.split("|") if c.strip() and "---" not in c]
            if cells:
                pdf.multi_cell(w=0, h=5, text="  ".join(cells), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 10)
        # Regular text
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(w=0, h=5, text=clean_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.output(output_path)


def export_to_file(
    content: str,
    output_path: Path,
    format: str = "md"
) -> Path:
    """Export content to a file in the specified format."""
    if format.lower() == "pdf":
        if not output_path.suffix.lower() == ".pdf":
            output_path = output_path.with_suffix(".pdf")
        markdown_to_pdf(content, output_path)
    else:
        if not output_path.suffix.lower() == ".md":
            output_path = output_path.with_suffix(".md")
        output_path.write_text(content)

    return output_path

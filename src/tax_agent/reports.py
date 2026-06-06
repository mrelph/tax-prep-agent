"""Comprehensive tax summary report generation."""

from datetime import datetime
from pathlib import Path
from typing import Any

from tax_agent.utils import get_enum_value


def _fmt(amount: float) -> str:
    """Format a dollar amount."""
    if amount < 0:
        return f"-${abs(amount):,.2f}"
    return f"${amount:,.2f}"


def _pct(rate: float) -> str:
    """Format a percentage."""
    return f"{rate:.1f}%"


def generate_tax_summary(
    analysis: dict[str, Any],
    documents: list | None = None,
    reviews: list | None = None,
    taxpayer_info: dict | None = None,
) -> str:
    """
    Generate a comprehensive tax summary report in Markdown.

    Args:
        analysis: Output from TaxAnalyzer.generate_analysis()
        documents: List of TaxDocument objects (optional, for document inventory)
        reviews: List of review dicts (optional, for findings)
        taxpayer_info: Dict with taxpayer profile info (optional)

    Returns:
        Complete Markdown report
    """
    tax_year = analysis.get("tax_year", 2024)
    filing_status = analysis.get("filing_status", "single")
    income = analysis.get("income_summary", {})
    withholding = analysis.get("withholding_summary", {})
    tax_est = analysis.get("tax_estimate", {})
    refund_or_owed = analysis.get("refund_or_owed", 0)

    lines: list[str] = []

    # ── Title ──
    lines.append(f"# Tax Preparation Summary — {tax_year}")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
    lines.append(f"**Filing Status:** {filing_status.replace('_', ' ').title()}")
    if taxpayer_info:
        if taxpayer_info.get("state"):
            lines.append(f"**State:** {taxpayer_info['state']}")
        if taxpayer_info.get("dependents"):
            lines.append(f"**Dependents:** {taxpayer_info['dependents']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Bottom Line ──
    lines.append("## Bottom Line")
    lines.append("")
    if refund_or_owed > 0:
        lines.append(f"**Estimated Federal Refund: {_fmt(refund_or_owed)}**")
    elif refund_or_owed < 0:
        lines.append(f"**Estimated Federal Tax Owed: {_fmt(-refund_or_owed)}**")
    else:
        lines.append("**Estimated Federal Balance: $0.00 (break even)**")
    lines.append("")

    total_income = tax_est.get("total_income", 0)
    total_tax = tax_est.get("total_tax", 0)
    if total_income > 0:
        effective_rate = (total_tax / total_income) * 100
        lines.append(f"Effective Federal Tax Rate: {_pct(effective_rate)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── Income Summary ──
    lines.append("## Income Summary")
    lines.append("")
    lines.append("| Source | Amount |")
    lines.append("|--------|-------:|")

    wages = income.get("wages", 0)
    interest = income.get("interest", 0)
    div_ord = income.get("dividends_ordinary", 0)
    div_qual = income.get("dividends_qualified", 0)
    cg_short = income.get("capital_gains_short", 0)
    cg_long = income.get("capital_gains_long", 0)
    other = income.get("other", 0)

    if wages:
        lines.append(f"| Wages & Salary | {_fmt(wages)} |")
    if interest:
        lines.append(f"| Interest Income | {_fmt(interest)} |")
    if div_ord:
        lines.append(f"| Ordinary Dividends | {_fmt(div_ord)} |")
    if div_qual:
        lines.append(f"| *(Qualified Dividends)* | *({_fmt(div_qual)})* |")
    if cg_short:
        lines.append(f"| Short-Term Capital Gains | {_fmt(cg_short)} |")
    if cg_long:
        lines.append(f"| Long-Term Capital Gains | {_fmt(cg_long)} |")
    if other:
        lines.append(f"| Other Income | {_fmt(other)} |")

    lines.append(f"| **Total Income** | **{_fmt(total_income)}** |")
    lines.append("")

    # ── Tax Calculation ──
    lines.append("## Federal Tax Calculation")
    lines.append("")
    lines.append("| Item | Amount |")
    lines.append("|------|-------:|")
    lines.append(f"| Total Income | {_fmt(total_income)} |")

    std_ded = tax_est.get("standard_deduction", 0)
    taxable = tax_est.get("taxable_income", 0)
    ord_tax = tax_est.get("ordinary_income_tax", 0)
    cg_tax = tax_est.get("capital_gains_tax", 0)

    lines.append(f"| Standard Deduction | -({_fmt(std_ded)}) |")
    lines.append(f"| **Taxable Income** | **{_fmt(taxable)}** |")
    lines.append(f"| Ordinary Income Tax | {_fmt(ord_tax)} |")
    if cg_tax > 0:
        lines.append(f"| Capital Gains Tax | {_fmt(cg_tax)} |")
    lines.append(f"| **Total Federal Tax** | **{_fmt(total_tax)}** |")
    lines.append("")

    # ── Withholding & Payments ──
    lines.append("## Withholding & Payments")
    lines.append("")
    lines.append("| Source | Amount |")
    lines.append("|--------|-------:|")

    fed_wh = withholding.get("federal", 0)
    state_wh = withholding.get("state", 0)
    ss_wh = withholding.get("social_security", 0)
    med_wh = withholding.get("medicare", 0)

    if fed_wh:
        lines.append(f"| Federal Income Tax Withheld | {_fmt(fed_wh)} |")
    if ss_wh:
        lines.append(f"| Social Security Tax | {_fmt(ss_wh)} |")
    if med_wh:
        lines.append(f"| Medicare Tax | {_fmt(med_wh)} |")
    if state_wh:
        lines.append(f"| State Income Tax Withheld | {_fmt(state_wh)} |")

    total_wh = fed_wh + ss_wh + med_wh + state_wh
    lines.append(f"| **Total Withheld** | **{_fmt(total_wh)}** |")
    lines.append("")

    # Refund/owed breakdown
    lines.append("### Federal Refund/Balance Due")
    lines.append("")
    lines.append("| Item | Amount |")
    lines.append("|------|-------:|")
    lines.append(f"| Total Federal Tax | {_fmt(total_tax)} |")
    lines.append(f"| Federal Withholding | -({_fmt(fed_wh)}) |")
    if refund_or_owed > 0:
        lines.append(f"| **Refund Due** | **{_fmt(refund_or_owed)}** |")
    elif refund_or_owed < 0:
        lines.append(f"| **Amount Owed** | **{_fmt(-refund_or_owed)}** |")
    else:
        lines.append("| **Balance** | **$0.00** |")
    lines.append("")

    # ── Document Inventory ──
    doc_count = analysis.get("documents_count", 0)
    docs_by_type = analysis.get("documents_by_type", {})

    lines.append("---")
    lines.append("")
    lines.append("## Document Inventory")
    lines.append("")
    lines.append(f"**Total Documents Collected:** {doc_count}")
    lines.append("")

    if docs_by_type:
        lines.append("| Document Type | Count |")
        lines.append("|---------------|------:|")
        for doc_type, count in sorted(docs_by_type.items()):
            lines.append(f"| {doc_type} | {count} |")
        lines.append("")

    # Detailed document list if available
    if documents:
        lines.append("### Document Details")
        lines.append("")
        for doc in documents:
            doc_type = get_enum_value(doc.document_type)
            status = "Needs Review" if doc.needs_review else "OK"
            conf = f"{doc.confidence_score:.0%}" if doc.confidence_score else "N/A"
            lines.append(f"- **{doc_type}** from {doc.issuer_name} — Confidence: {conf}, Status: {status}")
        lines.append("")

    # ── Checklist ──
    lines.append("---")
    lines.append("")
    lines.append("## Preparation Checklist")
    lines.append("")

    checklist_items = _generate_checklist(analysis, documents, reviews)
    for item in checklist_items:
        lines.append(item)
    lines.append("")

    # ── Review Findings ──
    if reviews:
        lines.append("---")
        lines.append("")
        lines.append("## Review Findings")
        lines.append("")
        for review in reviews:
            findings = review.get("findings", [])
            if not findings:
                lines.append("No issues found in review.")
                continue

            errors = [f for f in findings if str(f.get("severity", "")).lower() == "error"]
            warnings = [f for f in findings if str(f.get("severity", "")).lower() == "warning"]
            suggestions = [f for f in findings if str(f.get("severity", "")).lower() == "suggestion"]

            lines.append(f"**{len(errors)} error(s), {len(warnings)} warning(s), {len(suggestions)} suggestion(s)**")
            lines.append("")

            for finding in errors + warnings + suggestions:
                severity = str(finding.get("severity", "")).upper()
                title = finding.get("title", "N/A")
                desc = finding.get("description", "")
                lines.append(f"- **[{severity}]** {title}: {desc}")
                if finding.get("recommendation"):
                    lines.append(f"  - Recommendation: {finding['recommendation']}")
                if finding.get("potential_impact"):
                    lines.append(f"  - Potential impact: {_fmt(finding['potential_impact'])}")
            lines.append("")

    # ── Footer ──
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated by Tax Prep Agent on {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")
    lines.append("*This report is for informational purposes only and does not constitute tax advice.*")
    lines.append("*Consult a qualified tax professional before filing.*")

    return "\n".join(lines)


def _generate_checklist(
    analysis: dict,
    documents: list | None,
    reviews: list | None,
) -> list[str]:
    """Generate a preparation checklist based on available data."""
    items = []
    income = analysis.get("income_summary", {})
    docs_by_type = analysis.get("documents_by_type", {})

    # Document collection checks
    has_w2 = any("w2" in t.lower() for t in docs_by_type)
    has_income = sum(income.values()) > 0

    if has_w2:
        items.append("- [x] W-2 collected from employer(s)")
    elif income.get("wages", 0) > 0:
        items.append("- [ ] W-2 missing — wages detected but no W-2 on file")

    if income.get("interest", 0) > 0:
        items.append("- [x] 1099-INT collected for interest income")
    if income.get("dividends_ordinary", 0) > 0:
        items.append("- [x] 1099-DIV collected for dividend income")
    if income.get("capital_gains_short", 0) != 0 or income.get("capital_gains_long", 0) != 0:
        items.append("- [x] 1099-B collected for investment transactions")

    # General readiness
    if has_income:
        items.append("- [x] Income documents collected")
    else:
        items.append("- [ ] No income documents collected yet")

    if analysis.get("withholding_summary", {}).get("federal", 0) > 0:
        items.append("- [x] Federal withholding information available")
    else:
        items.append("- [ ] No federal withholding data found")

    # Review checks
    if reviews:
        error_count = sum(
            1 for r in reviews
            for f in r.get("findings", [])
            if str(f.get("severity", "")).lower() == "error"
        )
        if error_count == 0:
            items.append("- [x] Return reviewed — no errors found")
        else:
            items.append(f"- [ ] Return reviewed — {error_count} error(s) to resolve")
    else:
        items.append("- [ ] Return not yet reviewed")

    # Common missing items prompt
    common_docs = {"1098": "Mortgage interest", "1098-T": "Tuition", "1098-E": "Student loan interest"}
    for doc_key, desc in common_docs.items():
        if not any(doc_key.lower() in t.lower() for t in docs_by_type):
            items.append(f"- [ ] {desc} ({doc_key}) — not collected (if applicable)")

    return items


def generate_tax_summary_pdf(
    analysis: dict[str, Any],
    output_path: Path,
    documents: list | None = None,
    reviews: list | None = None,
    taxpayer_info: dict | None = None,
) -> Path:
    """
    Generate a styled PDF tax summary report.

    Args:
        analysis: Output from TaxAnalyzer.generate_analysis()
        output_path: Where to save the PDF
        documents: Optional list of TaxDocument objects
        reviews: Optional list of review dicts
        taxpayer_info: Optional taxpayer profile info

    Returns:
        Path to the generated PDF
    """
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    tax_year = analysis.get("tax_year", 2024)
    filing_status = analysis.get("filing_status", "single").replace("_", " ").title()
    income = analysis.get("income_summary", {})
    withholding = analysis.get("withholding_summary", {})
    tax_est = analysis.get("tax_estimate", {})
    refund_or_owed = analysis.get("refund_or_owed", 0)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)

    # ── Title Page ──
    pdf.add_page()
    pdf.ln(40)
    pdf.set_font("Helvetica", "B", 28)
    pdf.cell(w=0, h=15, text="Tax Preparation Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 18)
    pdf.cell(w=0, h=10, text=f"Tax Year {tax_year}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 12)
    pdf.cell(w=0, h=8, text=f"Filing Status: {filing_status}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    if taxpayer_info and taxpayer_info.get("state"):
        pdf.cell(w=0, h=8, text=f"State: {taxpayer_info['state']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    pdf.ln(20)

    # Bottom line box
    _draw_summary_box(pdf, refund_or_owed, tax_est)

    pdf.ln(15)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(
        w=0, h=6,
        text=f"Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )

    # ── Income Page ──
    pdf.add_page()
    _section_header(pdf, "Income Summary")

    income_rows = []
    if income.get("wages"):
        income_rows.append(("Wages & Salary", _fmt(income["wages"])))
    if income.get("interest"):
        income_rows.append(("Interest Income", _fmt(income["interest"])))
    if income.get("dividends_ordinary"):
        income_rows.append(("Ordinary Dividends", _fmt(income["dividends_ordinary"])))
    if income.get("capital_gains_short"):
        income_rows.append(("Short-Term Capital Gains", _fmt(income["capital_gains_short"])))
    if income.get("capital_gains_long"):
        income_rows.append(("Long-Term Capital Gains", _fmt(income["capital_gains_long"])))
    if income.get("other"):
        income_rows.append(("Other Income", _fmt(income["other"])))

    total_income = tax_est.get("total_income", 0)
    income_rows.append(("TOTAL INCOME", _fmt(total_income)))
    _draw_table(pdf, ["Source", "Amount"], income_rows, bold_last=True)

    pdf.ln(10)

    # Tax calculation
    _section_header(pdf, "Federal Tax Calculation")

    std_ded = tax_est.get("standard_deduction", 0)
    taxable = tax_est.get("taxable_income", 0)
    total_tax = tax_est.get("total_tax", 0)

    tax_rows = [
        ("Total Income", _fmt(total_income)),
        ("Standard Deduction", f"-({_fmt(std_ded)})"),
        ("Taxable Income", _fmt(taxable)),
        ("Ordinary Income Tax", _fmt(tax_est.get("ordinary_income_tax", 0))),
    ]
    if tax_est.get("capital_gains_tax", 0) > 0:
        tax_rows.append(("Capital Gains Tax", _fmt(tax_est["capital_gains_tax"])))
    tax_rows.append(("TOTAL FEDERAL TAX", _fmt(total_tax)))
    _draw_table(pdf, ["Item", "Amount"], tax_rows, bold_last=True)

    pdf.ln(10)

    # Withholding
    _section_header(pdf, "Withholding & Payments")

    wh_rows = []
    if withholding.get("federal"):
        wh_rows.append(("Federal Income Tax Withheld", _fmt(withholding["federal"])))
    if withholding.get("social_security"):
        wh_rows.append(("Social Security Tax", _fmt(withholding["social_security"])))
    if withholding.get("medicare"):
        wh_rows.append(("Medicare Tax", _fmt(withholding["medicare"])))
    if withholding.get("state"):
        wh_rows.append(("State Income Tax Withheld", _fmt(withholding["state"])))

    total_wh = sum(withholding.values())
    wh_rows.append(("TOTAL WITHHELD", _fmt(total_wh)))
    _draw_table(pdf, ["Source", "Amount"], wh_rows, bold_last=True)

    # ── Document Inventory Page ──
    docs_by_type = analysis.get("documents_by_type", {})
    if docs_by_type:
        pdf.add_page()
        _section_header(pdf, "Document Inventory")

        doc_rows = [(doc_type, str(count)) for doc_type, count in sorted(docs_by_type.items())]
        doc_rows.append(("TOTAL", str(analysis.get("documents_count", 0))))
        _draw_table(pdf, ["Document Type", "Count"], doc_rows, bold_last=True)

    # ── Review Findings Page ──
    if reviews:
        all_findings = []
        for review in reviews:
            all_findings.extend(review.get("findings", []))

        if all_findings:
            pdf.add_page()
            _section_header(pdf, "Review Findings")

            errors = [f for f in all_findings if str(f.get("severity", "")).lower() == "error"]
            warnings = [f for f in all_findings if str(f.get("severity", "")).lower() == "warning"]
            suggestions = [f for f in all_findings if str(f.get("severity", "")).lower() == "suggestion"]

            pdf.set_font("Helvetica", "", 10)
            pdf.cell(
                w=0, h=6,
                text=f"{len(errors)} error(s), {len(warnings)} warning(s), {len(suggestions)} suggestion(s)",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
            pdf.ln(5)

            for finding in errors + warnings + suggestions:
                severity = str(finding.get("severity", "")).upper()
                title = finding.get("title", "N/A")

                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(w=0, h=6, text=f"[{severity}] {title}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                if finding.get("description"):
                    pdf.set_font("Helvetica", "", 9)
                    pdf.multi_cell(w=0, h=5, text=finding["description"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                if finding.get("recommendation"):
                    pdf.set_font("Helvetica", "I", 9)
                    pdf.multi_cell(w=0, h=5, text=f"Recommendation: {finding['recommendation']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                pdf.ln(3)

    # ── Disclaimer Footer ──
    pdf.add_page()
    pdf.ln(20)
    _section_header(pdf, "Disclaimer")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        w=0, h=6,
        text=(
            "This report is for informational purposes only and does not constitute tax advice. "
            "The estimates provided are based on the documents collected and standard deduction amounts. "
            "Actual tax liability may differ based on additional income, deductions, credits, "
            "and other factors not captured in the collected documents.\n\n"
            "Consult a qualified tax professional before filing your tax return."
        ),
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )

    if not str(output_path).endswith(".pdf"):
        output_path = Path(str(output_path) + ".pdf")

    pdf.output(output_path)
    return output_path


def _section_header(pdf, title: str) -> None:
    """Draw a section header with underline."""
    from fpdf.enums import XPos, YPos

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(w=0, h=8, text=title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    y = pdf.get_y()
    pdf.line(20, y, 190, y)
    pdf.ln(5)


def _draw_summary_box(pdf, refund_or_owed: float, tax_est: dict) -> None:
    """Draw the bottom-line summary box on the title page."""
    from fpdf.enums import XPos, YPos

    x = 40
    w = 130
    y = pdf.get_y()

    # Box border
    pdf.rect(x, y, w, 35)

    # Inner content
    pdf.set_xy(x, y + 5)
    pdf.set_font("Helvetica", "B", 16)
    if refund_or_owed > 0:
        pdf.cell(w=w, h=10, text=f"Estimated Refund: {_fmt(refund_or_owed)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    elif refund_or_owed < 0:
        pdf.cell(w=w, h=10, text=f"Estimated Tax Owed: {_fmt(-refund_or_owed)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    else:
        pdf.cell(w=w, h=10, text="Break Even — $0.00", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    total_income = tax_est.get("total_income", 0)
    total_tax = tax_est.get("total_tax", 0)
    if total_income > 0:
        effective_rate = (total_tax / total_income) * 100
        pdf.set_xy(x, y + 20)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(w=w, h=8, text=f"Effective Tax Rate: {_pct(effective_rate)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

    pdf.set_y(y + 40)


def _draw_table(
    pdf,
    headers: list[str],
    rows: list[tuple[str, str]],
    bold_last: bool = False,
) -> None:
    """Draw a simple two-column table."""
    from fpdf.enums import XPos, YPos

    col_w = [120, 50]
    line_h = 6

    # Header
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(230, 230, 230)
    pdf.cell(w=col_w[0], h=line_h, text=headers[0], border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(w=col_w[1], h=line_h, text=headers[1], border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

    # Rows
    for i, (label, value) in enumerate(rows):
        is_last = (i == len(rows) - 1) and bold_last
        if is_last:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(w=col_w[0], h=line_h, text=label, border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(w=col_w[1], h=line_h, text=value, border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(w=col_w[0], h=line_h, text=label, border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.cell(w=col_w[1], h=line_h, text=value, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

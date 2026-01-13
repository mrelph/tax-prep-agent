"""Tax return error checking and review."""

import json
import uuid
from datetime import datetime
from pathlib import Path

from tax_agent.agent import get_agent
from tax_agent.collectors.ocr import extract_text_with_ocr
from tax_agent.config import get_config
from tax_agent.models.documents import TaxDocument
from tax_agent.models.returns import (
    ReturnType,
    ReviewFinding,
    ReviewSeverity,
    TaxReturnReview,
    TaxReturnSummary,
)
from tax_agent.storage.database import get_database


class ReturnReviewer:
    """Reviews completed tax returns for errors and optimization opportunities."""

    def __init__(self, tax_year: int | None = None):
        """Initialize the reviewer."""
        config = get_config()
        self.tax_year = tax_year or config.tax_year
        self.db = get_database()
        self.agent = get_agent()

    def review_return(self, return_path: str | Path) -> TaxReturnReview:
        """
        Review a completed tax return.

        Args:
            return_path: Path to the tax return PDF

        Returns:
            TaxReturnReview with findings
        """
        return_path = Path(return_path)
        if not return_path.exists():
            raise FileNotFoundError(f"Return file not found: {return_path}")

        # Extract text from the return
        return_text = extract_text_with_ocr(return_path)

        # Get source documents for comparison
        source_docs = self.db.get_documents(tax_year=self.tax_year)

        # Build source document summary
        source_summary = self._build_source_summary(source_docs)

        # Create initial review object
        review = TaxReturnReview(
            id=str(uuid.uuid4()),
            return_summary=TaxReturnSummary(
                return_type=ReturnType.FEDERAL_1040,
                tax_year=self.tax_year,
            ),
            source_documents_checked=[doc.id for doc in source_docs],
        )

        # Run rule-based checks first
        rule_findings = self._run_rule_based_checks(source_docs, return_text)
        for finding in rule_findings:
            review.add_finding(finding)

        # Run AI-powered review
        ai_findings_text = self.agent.review_tax_return(return_text, source_summary)
        ai_findings = self._parse_ai_findings(ai_findings_text)
        for finding in ai_findings:
            review.add_finding(finding)

        # Set overall assessment
        if review.errors_count > 0:
            review.overall_assessment = (
                f"Found {review.errors_count} error(s) that should be corrected before filing."
            )
        elif review.warnings_count > 0:
            review.overall_assessment = (
                f"Found {review.warnings_count} warning(s) to review. "
                f"Also found {review.suggestions_count} optimization opportunities."
            )
        elif review.suggestions_count > 0:
            review.overall_assessment = (
                f"Return looks correct. Found {review.suggestions_count} potential optimizations."
            )
        else:
            review.overall_assessment = "Return appears to be accurate with no issues found."

        return review

    def _build_source_summary(self, documents: list[TaxDocument]) -> str:
        """Build a summary of source documents for comparison."""
        if not documents:
            return "No source documents available for comparison."

        lines = [f"Source Documents for Tax Year {self.tax_year}:\n"]

        for doc in documents:
            line = f"- {doc.document_type.value} from {doc.issuer_name}"
            data = doc.extracted_data

            if doc.document_type.value == "W2":
                wages = data.get("box_1", 0) or 0
                federal_withheld = data.get("box_2", 0) or 0
                state_withheld = data.get("box_17", 0) or 0
                line += f"\n  Wages: ${wages:,.2f}"
                line += f"\n  Federal Withheld: ${federal_withheld:,.2f}"
                line += f"\n  State Withheld: ${state_withheld:,.2f}"

            elif doc.document_type.value == "1099_INT":
                interest = data.get("box_1", 0) or 0
                line += f"\n  Interest Income: ${interest:,.2f}"

            elif doc.document_type.value == "1099_DIV":
                ordinary = data.get("box_1a", 0) or 0
                qualified = data.get("box_1b", 0) or 0
                line += f"\n  Ordinary Dividends: ${ordinary:,.2f}"
                line += f"\n  Qualified Dividends: ${qualified:,.2f}"

            elif doc.document_type.value == "1099_B":
                summary = data.get("summary", {})
                proceeds = summary.get("total_proceeds", 0) or 0
                line += f"\n  Total Proceeds: ${proceeds:,.2f}"

            lines.append(line)

        return "\n".join(lines)

    def _run_rule_based_checks(
        self,
        source_docs: list[TaxDocument],
        return_text: str,
    ) -> list[ReviewFinding]:
        """Run basic rule-based checks."""
        findings: list[ReviewFinding] = []

        # Count expected income sources
        w2_count = sum(1 for d in source_docs if d.document_type.value == "W2")
        int_count = sum(1 for d in source_docs if d.document_type.value == "1099_INT")
        div_count = sum(1 for d in source_docs if d.document_type.value == "1099_DIV")
        b_count = sum(1 for d in source_docs if d.document_type.value == "1099_B")

        # Check for missing W-2s
        if w2_count > 0:
            total_wages = sum(
                (d.extracted_data.get("box_1", 0) or 0)
                for d in source_docs
                if d.document_type.value == "W2"
            )
            # Look for wages amount in return text (basic check)
            wages_str = f"${total_wages:,.0f}"
            if wages_str not in return_text and f"${total_wages:,.2f}" not in return_text:
                findings.append(
                    ReviewFinding(
                        severity=ReviewSeverity.WARNING,
                        category="income",
                        title="Wage Amount Verification Needed",
                        description=(
                            f"Expected total wages of ${total_wages:,.2f} from {w2_count} W-2(s). "
                            "Please verify this amount appears on Line 1 of Form 1040."
                        ),
                        expected_value=f"${total_wages:,.2f}",
                        recommendation="Verify wages match W-2 Box 1 total",
                    )
                )

        # Check for documents that need review
        needs_review = [d for d in source_docs if d.needs_review]
        if needs_review:
            findings.append(
                ReviewFinding(
                    severity=ReviewSeverity.WARNING,
                    category="documents",
                    title="Source Documents Need Review",
                    description=(
                        f"{len(needs_review)} source document(s) were flagged for manual review. "
                        "Verify the extracted data is accurate before relying on this review."
                    ),
                    recommendation="Run 'tax-agent documents list' to see documents needing review",
                )
            )

        return findings

    def _parse_ai_findings(self, ai_response: str) -> list[ReviewFinding]:
        """Parse AI review response into structured findings."""
        findings: list[ReviewFinding] = []

        # Try to extract structured findings from the AI response
        # The AI is prompted to provide structured output, but we'll handle
        # unstructured responses gracefully

        lines = ai_response.split("\n")
        current_finding: dict = {}

        severity_map = {
            "error": ReviewSeverity.ERROR,
            "warning": ReviewSeverity.WARNING,
            "suggestion": ReviewSeverity.SUGGESTION,
            "info": ReviewSeverity.INFO,
        }

        for line in lines:
            line_lower = line.lower().strip()

            # Look for severity markers
            for sev_name, sev_enum in severity_map.items():
                if line_lower.startswith(f"**{sev_name}") or line_lower.startswith(f"#{sev_name}"):
                    if current_finding and "title" in current_finding:
                        findings.append(
                            ReviewFinding(
                                severity=current_finding.get("severity", ReviewSeverity.INFO),
                                category=current_finding.get("category", "general"),
                                title=current_finding.get("title", "Finding"),
                                description=current_finding.get("description", ""),
                                recommendation=current_finding.get("recommendation"),
                                potential_impact=current_finding.get("impact"),
                            )
                        )
                    current_finding = {"severity": sev_enum}
                    # Extract title from the same line if present
                    rest = line.split(":", 1)
                    if len(rest) > 1:
                        current_finding["title"] = rest[1].strip()
                    break

            # Accumulate description
            if current_finding and "severity" in current_finding:
                if "description" not in current_finding:
                    current_finding["description"] = ""

                if line_lower.startswith("- ") or line_lower.startswith("* "):
                    current_finding["description"] += line[2:] + " "
                elif line.strip() and not any(
                    line_lower.startswith(x) for x in ["**", "#", "severity:", "category:"]
                ):
                    current_finding["description"] += line.strip() + " "

                # Look for recommendation
                if "recommendation:" in line_lower:
                    current_finding["recommendation"] = line.split(":", 1)[1].strip()

                # Look for impact
                if "impact:" in line_lower or "savings:" in line_lower:
                    try:
                        # Try to extract dollar amount
                        import re
                        match = re.search(r"\$[\d,]+", line)
                        if match:
                            amount = float(match.group().replace("$", "").replace(",", ""))
                            current_finding["impact"] = amount
                    except (ValueError, AttributeError):
                        pass

        # Don't forget the last finding
        if current_finding and "title" in current_finding:
            findings.append(
                ReviewFinding(
                    severity=current_finding.get("severity", ReviewSeverity.INFO),
                    category=current_finding.get("category", "general"),
                    title=current_finding.get("title", "Finding"),
                    description=current_finding.get("description", "").strip(),
                    recommendation=current_finding.get("recommendation"),
                    potential_impact=current_finding.get("impact"),
                )
            )

        # If no structured findings were parsed, create a general one from the response
        if not findings and ai_response.strip():
            findings.append(
                ReviewFinding(
                    severity=ReviewSeverity.INFO,
                    category="general",
                    title="AI Review Summary",
                    description=ai_response[:500] + ("..." if len(ai_response) > 500 else ""),
                )
            )

        return findings


def review_return(return_path: str | Path, tax_year: int | None = None) -> TaxReturnReview:
    """Convenience function to review a tax return."""
    reviewer = ReturnReviewer(tax_year)
    return reviewer.review_return(return_path)

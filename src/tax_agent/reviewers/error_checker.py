"""Tax return error checking and review."""

import base64
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
from tax_agent.utils import get_enum_value


class ReturnReviewer:
    """Reviews completed tax returns for errors and optimization opportunities."""

    def __init__(self, tax_year: int | None = None):
        """Initialize the reviewer."""
        self.config = get_config()
        self.tax_year = tax_year or self.config.tax_year
        self.db = get_database()
        self.agent = get_agent()
        self._last_review_text: str | None = None  # Store for chat context

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

        # Get source documents for comparison
        source_docs = self.db.get_documents(tax_year=self.tax_year)
        source_summary = self._build_source_summary(source_docs)

        # Get user memories for personalized review
        taxpayer_context = self._get_taxpayer_context()

        # Create initial review object
        review = TaxReturnReview(
            id=str(uuid.uuid4()),
            return_summary=TaxReturnSummary(
                return_type=ReturnType.FEDERAL_1040,
                tax_year=self.tax_year,
            ),
            source_documents_checked=[doc.id for doc in source_docs],
        )

        # Use Vision API for review (preferred) or fall back to OCR
        use_vision = self.config.get("use_vision", True)

        if use_vision:
            # Use Claude Vision to analyze the return directly
            ai_findings_text = self._review_with_vision(
                return_path, source_summary, taxpayer_context
            )
        else:
            # Legacy OCR-based review
            return_text = extract_text_with_ocr(return_path)

            # Run rule-based checks
            rule_findings = self._run_rule_based_checks(source_docs, return_text)
            for finding in rule_findings:
                review.add_finding(finding)

            # Run AI review on extracted text
            ai_findings_text = self._run_ai_review(return_text, source_summary, taxpayer_context)

        # Store for chat context
        self._last_review_text = ai_findings_text

        # Parse AI findings
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

        # Save review to database for later reference
        self.db.save_review(review)

        return review

    def _review_with_vision(
        self,
        return_path: Path,
        source_summary: str,
        taxpayer_context: str,
    ) -> str:
        """
        Review a tax return using Claude Vision.

        Analyzes the return images directly for more accurate review.
        """
        # Prepare images from PDF
        images_data = self.agent._prepare_images_for_vision(return_path)

        # Build comprehensive review prompt
        system = f"""You are an expert tax return reviewer. Analyze this tax return for:

1. **ERRORS** - Mathematical mistakes, incorrect entries, missing required fields
2. **MISSED DEDUCTIONS** - Deductions/credits that could have been claimed
3. **OPTIMIZATION OPPORTUNITIES** - Ways to reduce tax liability
4. **INCONSISTENCIES** - Numbers that don't match or add up

{f"TAXPAYER CONTEXT:{chr(10)}{taxpayer_context}" if taxpayer_context else ""}

{f"SOURCE DOCUMENTS:{chr(10)}{source_summary}" if source_summary != "No source documents available for comparison." else ""}

Return your findings as a JSON array. Each finding must have these fields:
- "severity": one of "error", "warning", "suggestion", "info"
- "category": e.g. "income", "deduction", "credit", "compliance", "optimization"
- "title": brief title
- "description": detailed description
- "recommendation": what to do (optional)
- "potential_impact": dollar amount as number, no $ sign (optional)
- "line_reference": form line reference like "1040 Line 1" (optional)

Example format:
```json
[
  {{"severity": "error", "category": "income", "title": "Missing W-2 income", "description": "...", "recommendation": "...", "potential_impact": 1500}}
]
```

Be thorough but only report genuine issues. Don't fabricate problems.
Return ONLY the JSON array, no other text."""

        # Build message with images (first 5 pages)
        content = []
        for img_data in images_data[:5]:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img_data["media_type"],
                    "data": img_data["data"],
                },
            })
        content.append({
            "type": "text",
            "text": "Review this tax return thoroughly. Identify all errors, missed deductions, and optimization opportunities.",
        })

        response = self.agent.client.messages.create(
            model=self.agent.model,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": content}],
        )

        return response.content[0].text

    def _build_source_summary(self, documents: list[TaxDocument]) -> str:
        """Build a summary of source documents for comparison."""
        if not documents:
            return "No source documents available for comparison."

        lines = [f"Source Documents for Tax Year {self.tax_year}:\n"]

        for doc in documents:
            line = f"- {get_enum_value(doc.document_type)} from {doc.issuer_name}"
            data = doc.extracted_data

            if get_enum_value(doc.document_type) == "W2":
                wages = data.get("box_1", 0) or 0
                federal_withheld = data.get("box_2", 0) or 0
                state_withheld = data.get("box_17", 0) or 0
                line += f"\n  Wages: ${wages:,.2f}"
                line += f"\n  Federal Withheld: ${federal_withheld:,.2f}"
                line += f"\n  State Withheld: ${state_withheld:,.2f}"

            elif get_enum_value(doc.document_type) == "1099_INT":
                interest = data.get("box_1", 0) or 0
                line += f"\n  Interest Income: ${interest:,.2f}"

            elif get_enum_value(doc.document_type) == "1099_DIV":
                ordinary = data.get("box_1a", 0) or 0
                qualified = data.get("box_1b", 0) or 0
                line += f"\n  Ordinary Dividends: ${ordinary:,.2f}"
                line += f"\n  Qualified Dividends: ${qualified:,.2f}"

            elif get_enum_value(doc.document_type) == "1099_B":
                summary = data.get("summary", {})
                proceeds = summary.get("total_proceeds", 0) or 0
                line += f"\n  Total Proceeds: ${proceeds:,.2f}"

            lines.append(line)

        return "\n".join(lines)

    def _get_taxpayer_context(self) -> str:
        """Get taxpayer context from memories and profile."""
        context_parts = []

        # Get memories
        try:
            from tax_agent.memory import MemoryManager
            memory_mgr = MemoryManager(self.db)
            memories = memory_mgr.get_all_memories()
            if memories:
                memory_context = memory_mgr.format_memories_for_context(memories)
                if memory_context:
                    context_parts.append("Known information about taxpayer:")
                    context_parts.append(memory_context)
        except Exception:
            pass

        # Get taxpayer profile if available
        try:
            profile = self.db.get_taxpayer_profile(self.tax_year)
            if profile:
                context_parts.append(f"\nFiling Status: {profile.filing_status}")
                context_parts.append(f"State: {profile.state}")
                if profile.is_self_employed:
                    context_parts.append("Self-employed: Yes")
                if profile.dependents:
                    context_parts.append(f"Dependents: {len(profile.dependents)}")
        except Exception:
            pass

        return "\n".join(context_parts) if context_parts else ""

    def _run_ai_review(
        self,
        return_text: str,
        source_summary: str,
        taxpayer_context: str,
    ) -> str:
        """Run comprehensive AI review with taxpayer context."""
        # Build enhanced prompt with taxpayer context
        enhanced_source = source_summary
        if taxpayer_context:
            enhanced_source = f"{taxpayer_context}\n\n{source_summary}"

        # Add specific prompts based on taxpayer situation
        situation_prompts = []
        context_lower = taxpayer_context.lower()

        if "self-employed" in context_lower or "freelance" in context_lower:
            situation_prompts.append(
                "SELF-EMPLOYMENT CHECK: Verify Schedule C is included. "
                "Check for home office deduction (Form 8829), health insurance deduction, "
                "retirement contributions (SEP-IRA, Solo 401k), and QBI deduction (199A)."
            )

        if "home" in context_lower and ("office" in context_lower or "work" in context_lower):
            situation_prompts.append(
                "HOME OFFICE CHECK: Is Form 8829 or simplified method claimed? "
                "Calculate potential deduction if missing."
            )

        if "invest" in context_lower or "stock" in context_lower or "rsu" in context_lower:
            situation_prompts.append(
                "INVESTMENT CHECK: Verify cost basis accuracy (especially RSUs). "
                "Check for tax-loss harvesting opportunities and wash sale compliance."
            )

        # Use agent's review method but append situation-specific prompts
        base_review = self.agent.review_tax_return(return_text, enhanced_source)

        # If we have specific situation prompts, do a follow-up analysis
        if situation_prompts:
            follow_up = "\n\n".join(situation_prompts)
            follow_up_review = self.agent._call(
                system="You are a tax optimization specialist. Given the taxpayer's specific situation, check for these commonly missed deductions and credits. Be specific about dollar amounts when possible.",
                user_message=f"""Taxpayer situation:
{taxpayer_context}

Return text (excerpt):
{return_text[:4000]}

SPECIFIC CHECKS:
{follow_up}

List any missed deductions or optimization opportunities as:
**OPPORTUNITY**: [description]
- Potential savings: $X
- Action: [what to do]""",
                max_tokens=2000,
            )
            return f"{base_review}\n\n## Situation-Specific Review\n{follow_up_review}"

        return base_review

    def _run_rule_based_checks(
        self,
        source_docs: list[TaxDocument],
        return_text: str,
    ) -> list[ReviewFinding]:
        """Run basic rule-based checks."""
        findings: list[ReviewFinding] = []

        # Count expected income sources
        w2_count = sum(1 for d in source_docs if get_enum_value(d.document_type) == "W2")
        int_count = sum(1 for d in source_docs if get_enum_value(d.document_type) == "1099_INT")
        div_count = sum(1 for d in source_docs if get_enum_value(d.document_type) == "1099_DIV")
        b_count = sum(1 for d in source_docs if get_enum_value(d.document_type) == "1099_B")

        # Check for missing W-2s
        if w2_count > 0:
            total_wages = sum(
                (d.extracted_data.get("box_1", 0) or 0)
                for d in source_docs
                if get_enum_value(d.document_type) == "W2"
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
        """Parse AI review response into structured findings.

        Tries JSON parsing first, falls back to text parsing for older-style responses.
        """
        # Try JSON parsing first
        findings = self._parse_json_findings(ai_response)
        if findings:
            return findings

        # Fall back to text-based parsing
        return self._parse_text_findings(ai_response)

    def _parse_json_findings(self, ai_response: str) -> list[ReviewFinding]:
        """Parse JSON-formatted AI findings."""
        import re

        text = ai_response.strip()

        # Strip markdown code fences if present
        if "```" in text:
            match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
            if match:
                text = match.group(1).strip()

        # Find JSON array in the response
        bracket_start = text.find("[")
        bracket_end = text.rfind("]")
        if bracket_start < 0 or bracket_end < 0:
            return []

        try:
            items = json.loads(text[bracket_start:bracket_end + 1])
        except json.JSONDecodeError:
            return []

        if not isinstance(items, list):
            return []

        severity_map = {
            "error": ReviewSeverity.ERROR,
            "warning": ReviewSeverity.WARNING,
            "suggestion": ReviewSeverity.SUGGESTION,
            "opportunity": ReviewSeverity.SUGGESTION,
            "info": ReviewSeverity.INFO,
        }

        findings: list[ReviewFinding] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            sev_str = str(item.get("severity", "info")).lower()
            severity = severity_map.get(sev_str, ReviewSeverity.INFO)

            impact = item.get("potential_impact")
            if impact is not None:
                try:
                    impact = float(str(impact).replace("$", "").replace(",", ""))
                except (ValueError, TypeError):
                    impact = None

            findings.append(
                ReviewFinding(
                    severity=severity,
                    category=item.get("category", "general"),
                    title=item.get("title", "Finding"),
                    description=item.get("description", ""),
                    line_reference=item.get("line_reference"),
                    expected_value=item.get("expected_value"),
                    actual_value=item.get("actual_value"),
                    recommendation=item.get("recommendation"),
                    potential_impact=impact,
                    source_document_id=item.get("source_document_id"),
                )
            )

        return findings

    def _parse_text_findings(self, ai_response: str) -> list[ReviewFinding]:
        """Fall back text parser for unstructured AI responses."""
        import re

        findings: list[ReviewFinding] = []
        lines = ai_response.split("\n")
        current_finding: dict = {}

        severity_map = {
            "error": ReviewSeverity.ERROR,
            "warning": ReviewSeverity.WARNING,
            "suggestion": ReviewSeverity.SUGGESTION,
            "opportunity": ReviewSeverity.SUGGESTION,
            "info": ReviewSeverity.INFO,
        }

        for line in lines:
            line_lower = line.lower().strip()

            for sev_name, sev_enum in severity_map.items():
                if line_lower.startswith(f"**{sev_name}") or line_lower.startswith(f"#{sev_name}"):
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
                    current_finding = {"severity": sev_enum}
                    rest = line.split(":", 1)
                    if len(rest) > 1:
                        current_finding["title"] = rest[1].strip()
                    break

            if current_finding and "severity" in current_finding:
                if "description" not in current_finding:
                    current_finding["description"] = ""

                if line_lower.startswith("- ") or line_lower.startswith("* "):
                    current_finding["description"] += line[2:] + " "
                elif line.strip() and not any(
                    line_lower.startswith(x) for x in ["**", "#", "severity:", "category:"]
                ):
                    current_finding["description"] += line.strip() + " "

                if "recommendation:" in line_lower:
                    current_finding["recommendation"] = line.split(":", 1)[1].strip()

                if "impact:" in line_lower or "savings:" in line_lower:
                    try:
                        match = re.search(r"\$[\d,]+", line)
                        if match:
                            amount = float(match.group().replace("$", "").replace(",", ""))
                            current_finding["impact"] = amount
                    except (ValueError, AttributeError):
                        pass

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

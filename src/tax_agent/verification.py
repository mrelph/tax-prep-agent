"""Verification module to prevent hallucinations and validate AI outputs."""

import json
import re
from typing import Any

from tax_agent.agent import get_agent
from tax_agent.config import get_config


class OutputVerifier:
    """
    Verifies AI outputs to catch hallucinations and errors.

    Uses multiple strategies:
    1. Self-consistency checks (ask the same question differently)
    2. Cross-validation with known rules
    3. Sanity checks on numerical values
    4. Source document verification
    """

    def __init__(self):
        self.agent = get_agent()
        config = get_config()
        self.tax_year = config.tax_year

    def verify_extracted_data(
        self,
        document_type: str,
        extracted_data: dict[str, Any],
        raw_text: str,
    ) -> dict[str, Any]:
        """
        Verify extracted data against the source document.

        Args:
            document_type: Type of tax document
            extracted_data: Data extracted by AI
            raw_text: Original document text

        Returns:
            Verification result with confidence and issues
        """
        issues = []
        verified_fields = {}

        # 1. Check that key values appear in the source text
        for key, value in extracted_data.items():
            if value is None:
                continue

            if isinstance(value, (int, float)) and value > 0:
                # Check if this number appears in the source
                value_str = f"{value:,.2f}".replace(",", "").replace(".00", "")
                alt_formats = [
                    str(int(value)) if value == int(value) else str(value),
                    f"{value:,.2f}",
                    f"{value:.2f}",
                    f"{int(value):,}",
                ]

                found = any(fmt in raw_text.replace(",", "") for fmt in alt_formats)
                if not found and value > 100:  # Only flag significant amounts
                    issues.append({
                        "field": key,
                        "value": value,
                        "issue": "Value not found in source document",
                        "severity": "warning"
                    })
                else:
                    verified_fields[key] = True

        # 2. Sanity checks for specific document types
        if document_type == "W2":
            issues.extend(self._verify_w2(extracted_data))
        elif document_type == "1099_B":
            issues.extend(self._verify_1099b(extracted_data))

        # 3. Calculate confidence score
        total_fields = len([v for v in extracted_data.values() if v is not None])
        verified_count = len(verified_fields)
        issue_count = len([i for i in issues if i["severity"] == "error"])

        if total_fields > 0:
            confidence = max(0, (verified_count - issue_count) / total_fields)
        else:
            confidence = 0.5

        return {
            "verified": len(issues) == 0 or all(i["severity"] != "error" for i in issues),
            "confidence": confidence,
            "issues": issues,
            "verified_fields": list(verified_fields.keys()),
        }

    def _verify_w2(self, data: dict) -> list[dict]:
        """W2-specific verification checks."""
        issues = []

        # Box 1 should be >= Box 3 (wages >= SS wages, usually equal)
        box1 = data.get("box_1", 0) or 0
        box3 = data.get("box_3", 0) or 0
        if box1 > 0 and box3 > box1 * 1.1:  # Allow 10% tolerance
            issues.append({
                "field": "box_3",
                "value": box3,
                "issue": f"SS wages ({box3}) exceeds total wages ({box1})",
                "severity": "error"
            })

        # Box 4 should be ~6.2% of Box 3 (SS tax)
        box4 = data.get("box_4", 0) or 0
        if box3 > 0:
            expected_ss = box3 * 0.062
            if abs(box4 - expected_ss) > expected_ss * 0.05:  # 5% tolerance
                issues.append({
                    "field": "box_4",
                    "value": box4,
                    "issue": f"SS tax ({box4}) doesn't match 6.2% of SS wages (expected ~{expected_ss:.2f})",
                    "severity": "warning"
                })

        # Box 6 should be ~1.45% of Box 5 (Medicare)
        box5 = data.get("box_5", 0) or 0
        box6 = data.get("box_6", 0) or 0
        if box5 > 0:
            expected_med = box5 * 0.0145
            if abs(box6 - expected_med) > expected_med * 0.1:  # 10% tolerance (additional Medicare possible)
                issues.append({
                    "field": "box_6",
                    "value": box6,
                    "issue": f"Medicare tax ({box6}) differs from expected 1.45% (expected ~{expected_med:.2f})",
                    "severity": "warning"
                })

        return issues

    def _verify_1099b(self, data: dict) -> list[dict]:
        """1099-B specific verification checks."""
        issues = []

        transactions = data.get("transactions", [])
        summary = data.get("summary", {})

        # Verify summary matches transactions
        if transactions:
            calc_proceeds = sum(t.get("proceeds", 0) or 0 for t in transactions)
            reported_proceeds = summary.get("total_proceeds", 0) or 0

            if abs(calc_proceeds - reported_proceeds) > 1:  # $1 tolerance
                issues.append({
                    "field": "summary.total_proceeds",
                    "value": reported_proceeds,
                    "issue": f"Summary proceeds ({reported_proceeds}) doesn't match transaction total ({calc_proceeds})",
                    "severity": "error"
                })

        return issues

    def verify_tax_calculation(
        self,
        income: float,
        calculated_tax: float,
        filing_status: str,
    ) -> dict[str, Any]:
        """
        Verify a tax calculation is reasonable.

        Args:
            income: Taxable income
            calculated_tax: The calculated tax amount
            filing_status: Filing status used

        Returns:
            Verification result
        """
        issues = []

        if income <= 0:
            return {"verified": True, "issues": []}

        effective_rate = calculated_tax / income

        # Sanity checks
        if effective_rate < 0:
            issues.append({
                "issue": "Negative effective tax rate",
                "severity": "error"
            })
        elif effective_rate > 0.40:  # Max federal rate is 37% + state
            issues.append({
                "issue": f"Effective rate ({effective_rate:.1%}) exceeds maximum possible",
                "severity": "warning"
            })
        elif effective_rate < 0.05 and income > 50000:
            issues.append({
                "issue": f"Effective rate ({effective_rate:.1%}) seems too low for income of ${income:,.0f}",
                "severity": "warning"
            })

        return {
            "verified": len([i for i in issues if i["severity"] == "error"]) == 0,
            "effective_rate": effective_rate,
            "issues": issues,
        }

    def double_check_analysis(
        self,
        original_analysis: str,
        documents_summary: str,
    ) -> dict[str, Any]:
        """
        Have AI double-check its own analysis for errors.

        Args:
            original_analysis: The original AI analysis
            documents_summary: Summary of source documents

        Returns:
            Verification with any corrections
        """
        system = """You are a tax accuracy auditor. Review the following tax analysis and check for:

1. FACTUAL ERRORS - Incorrect tax rules, rates, or limits
2. MATH ERRORS - Wrong calculations or totals
3. HALLUCINATIONS - Claims not supported by the source documents
4. OUTDATED INFO - Rules that may have changed
5. MISSING CONTEXT - Important caveats or conditions not mentioned

Be skeptical. If something seems too good to be true, flag it.

Return JSON:
{
  "verified": true/false,
  "errors_found": [{"issue": "description", "severity": "error/warning", "correction": "what it should say"}],
  "suspicious_claims": ["claim that needs verification"],
  "confidence_score": 0.0-1.0,
  "summary": "brief assessment"
}

Only return the JSON object."""

        user_message = f"""Source Documents:
{documents_summary}

Analysis to Verify:
{original_analysis}

Check this analysis for errors, hallucinations, or suspicious claims."""

        response = self.agent._call(system, user_message, max_tokens=2000)

        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "verified": False,
                "errors_found": [],
                "confidence_score": 0.5,
                "summary": "Could not parse verification response"
            }


def verify_extraction(document_type: str, data: dict, raw_text: str) -> dict:
    """Convenience function to verify extracted data."""
    verifier = OutputVerifier()
    return verifier.verify_extracted_data(document_type, data, raw_text)


def double_check(analysis: str, documents: str) -> dict:
    """Convenience function to double-check an analysis."""
    verifier = OutputVerifier()
    return verifier.double_check_analysis(analysis, documents)

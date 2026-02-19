"""Tax implication analysis module."""

import asyncio
from pathlib import Path
from typing import Any

import yaml

from tax_agent.agent import get_agent
from tax_agent.config import get_config
from tax_agent.models.documents import DocumentType, TaxDocument
from tax_agent.models.taxpayer import FilingStatus, TaxpayerProfile
from tax_agent.storage.database import get_database
from tax_agent.utils import get_enum_value


def _get_sdk_agent():
    """Get SDK agent if available and enabled."""
    config = get_config()
    if config.use_agent_sdk:
        from tax_agent.agent_sdk import get_sdk_agent, sdk_available
        if sdk_available():
            return get_sdk_agent()
    return None


def _build_bracket_list(cumulative_brackets: list[tuple[float, float]]) -> list[dict]:
    """Convert (threshold, rate) tuples to {min, max, rate} bracket dicts."""
    result = []
    prev_max = 0
    for threshold, rate in cumulative_brackets:
        result.append({
            "min": prev_max,
            "max": None if threshold == float("inf") else threshold,
            "rate": rate,
        })
        prev_max = threshold
    return result


def _get_fallback_rules(tax_year: int) -> dict[str, Any]:
    """Get hardcoded tax rules when YAML files are unavailable."""
    from tax_agent.tools.tax_calculations import (
        TAX_BRACKETS_2024,
        TAX_BRACKETS_2025,
        STANDARD_DEDUCTIONS,
    )

    brackets_src = TAX_BRACKETS_2025 if tax_year >= 2025 else TAX_BRACKETS_2024
    deductions_src = STANDARD_DEDUCTIONS.get(tax_year, STANDARD_DEDUCTIONS[2024])

    brackets = {
        status: _build_bracket_list(rates)
        for status, rates in brackets_src.items()
    }

    # Long-term capital gains brackets (2024)
    cap_gains = {
        "long_term": {
            "single": _build_bracket_list([
                (47025, 0.0), (518900, 0.15), (float("inf"), 0.20),
            ]),
            "married_filing_jointly": _build_bracket_list([
                (94050, 0.0), (583750, 0.15), (float("inf"), 0.20),
            ]),
            "head_of_household": _build_bracket_list([
                (63000, 0.0), (551350, 0.15), (float("inf"), 0.20),
            ]),
        }
    }

    return {
        "standard_deduction": {k: v for k, v in deductions_src.items() if not k.startswith("additional")},
        "brackets": brackets,
        "capital_gains": cap_gains,
        "retirement_401k": {"employee_contribution_limit": 23000 if tax_year <= 2024 else 23500},
        "ira": {"contribution_limit": 7000},
    }


def load_tax_rules(tax_year: int = 2024) -> dict[str, Any]:
    """Load federal tax rules for a given year.

    Falls back to hardcoded values from tax_calculations.py if YAML files
    are not available (e.g. in CI or fresh deployments).
    """
    rules_dir = Path(__file__).parent.parent.parent.parent / "data" / "tax_rules"
    rules_file = rules_dir / f"federal_{tax_year}.yaml"

    if not rules_file.exists():
        rules_file = rules_dir / "federal_2024.yaml"

    try:
        with open(rules_file) as f:
            return yaml.safe_load(f)
    except (FileNotFoundError, OSError):
        import logging
        logging.getLogger("tax_agent").info(
            f"Tax rules YAML not found for {tax_year}, using hardcoded fallback"
        )
        return _get_fallback_rules(tax_year)


def load_state_rules(state: str, tax_year: int = 2024) -> dict[str, Any] | None:
    """Load state tax rules if available."""
    rules_dir = Path(__file__).parent.parent.parent.parent / "data" / "tax_rules" / "states"
    rules_file = rules_dir / f"{state.lower()}_{tax_year}.yaml"

    if rules_file.exists():
        with open(rules_file) as f:
            return yaml.safe_load(f)
    return None


def get_tax_year_context(tax_year: int, state: str | None = None) -> str:
    """Generate tax year and state context for AI prompts."""
    context_lines = [
        f"TAX YEAR: {tax_year}",
        "",
        f"KEY {tax_year} FEDERAL TAX RULES:",
    ]

    rules = load_tax_rules(tax_year)
    if rules:
        context_lines.extend([
            f"- Standard Deduction (Single): ${rules['standard_deduction']['single']:,}",
            f"- Standard Deduction (MFJ): ${rules['standard_deduction']['married_filing_jointly']:,}",
            f"- Top marginal rate: {rules['brackets']['single'][-1]['rate']*100:.0f}%",
            f"- SALT cap: $10,000",
            f"- 401(k) limit: ${rules['retirement_401k']['employee_contribution_limit']:,}",
            f"- IRA limit: ${rules['ira']['contribution_limit']:,}",
        ])

    if state:
        state_rules = load_state_rules(state, tax_year)
        if state_rules:
            context_lines.extend([
                "",
                f"STATE: {state_rules.get('state_name', state)}",
                f"- Standard Deduction (Single): ${state_rules['standard_deduction']['single']:,}",
                f"- Top marginal rate: {state_rules['brackets']['single'][-1]['rate']*100:.1f}%",
            ])
            if state_rules.get("special_rules", {}).get("capital_gains_treatment") == "ordinary_income":
                context_lines.append("- Capital gains taxed as ORDINARY INCOME (no preferential rate)")
            if not state_rules.get("special_rules", {}).get("qbi_deduction_allowed", True):
                context_lines.append("- Does NOT conform to federal QBI deduction")
        else:
            context_lines.extend([
                "",
                f"STATE: {state} (no specific rules loaded - use general state tax knowledge)",
            ])

    return "\n".join(context_lines)


class TaxAnalyzer:
    """Analyzes tax documents and calculates implications."""

    def __init__(self, tax_year: int | None = None):
        """Initialize the analyzer."""
        config = get_config()
        self.tax_year = tax_year or config.tax_year
        self.rules = load_tax_rules(self.tax_year)
        self.db = get_database()

    def get_documents(self) -> list[TaxDocument]:
        """Get all documents for the tax year."""
        return self.db.get_documents(tax_year=self.tax_year)

    def calculate_income_summary(self, documents: list[TaxDocument]) -> dict[str, float]:
        """
        Calculate income summary from documents.

        Returns:
            Dictionary of income by category
        """
        income: dict[str, float] = {
            "wages": 0.0,
            "interest": 0.0,
            "dividends_ordinary": 0.0,
            "dividends_qualified": 0.0,
            "capital_gains_short": 0.0,
            "capital_gains_long": 0.0,
            "other": 0.0,
        }

        for doc in documents:
            data = doc.extracted_data

            if doc.document_type == DocumentType.W2:
                income["wages"] += data.get("box_1", 0) or 0

            elif doc.document_type == DocumentType.FORM_1099_INT:
                income["interest"] += data.get("box_1", 0) or 0

            elif doc.document_type == DocumentType.FORM_1099_DIV:
                income["dividends_ordinary"] += data.get("box_1a", 0) or 0
                income["dividends_qualified"] += data.get("box_1b", 0) or 0

            elif doc.document_type == DocumentType.FORM_1099_B:
                summary = data.get("summary", {})
                income["capital_gains_short"] += summary.get("short_term_gain_loss", 0) or 0
                income["capital_gains_long"] += summary.get("long_term_gain_loss", 0) or 0

            elif doc.document_type in (DocumentType.FORM_1099_NEC, DocumentType.FORM_1099_MISC):
                income["other"] += data.get("box_1", 0) or data.get("box_7", 0) or 0

        return income

    def calculate_withholding(self, documents: list[TaxDocument]) -> dict[str, float]:
        """Calculate total tax withholding from documents."""
        withholding: dict[str, float] = {
            "federal": 0.0,
            "state": 0.0,
            "social_security": 0.0,
            "medicare": 0.0,
        }

        for doc in documents:
            data = doc.extracted_data

            if doc.document_type == DocumentType.W2:
                withholding["federal"] += data.get("box_2", 0) or 0
                withholding["state"] += data.get("box_17", 0) or 0
                withholding["social_security"] += data.get("box_4", 0) or 0
                withholding["medicare"] += data.get("box_6", 0) or 0

            elif doc.document_type in (
                DocumentType.FORM_1099_INT,
                DocumentType.FORM_1099_DIV,
                DocumentType.FORM_1099_B,
            ):
                withholding["federal"] += data.get("federal_tax_withheld", 0) or data.get("box_4", 0) or 0

        return withholding

    def estimate_tax_liability(
        self,
        income: dict[str, float],
        filing_status: FilingStatus | str,
    ) -> dict[str, float]:
        """
        Estimate federal tax liability.

        Args:
            income: Income by category
            filing_status: Filing status

        Returns:
            Estimated tax breakdown
        """
        if isinstance(filing_status, FilingStatus):
            filing_status = filing_status.value

        # Total income includes all dividends (qualified are a subset of ordinary)
        total_income = (
            income["wages"]
            + income["interest"]
            + income["dividends_ordinary"]
            + income["capital_gains_short"]
            + income["capital_gains_long"]
            + income["other"]
        )

        # Get standard deduction
        standard_deduction = self.rules["standard_deduction"].get(filing_status, 14600)

        # Taxable income after standard deduction
        taxable_income = max(0, total_income - standard_deduction)

        # Preferential income (qualified dividends + long-term gains)
        # Cannot exceed total taxable income (standard deduction may shelter some)
        preferential_income = min(
            income["dividends_qualified"] + income["capital_gains_long"],
            taxable_income,
        )

        # Ordinary portion = taxable income minus preferential portion
        taxable_ordinary = taxable_income - preferential_income

        # Calculate ordinary income tax using brackets
        brackets = self.rules["brackets"].get(filing_status, self.rules["brackets"]["single"])
        ordinary_tax = self._calculate_tax_from_brackets(taxable_ordinary, brackets)

        # Calculate preferential rate tax (qualified dividends + long-term gains)
        cap_gains_brackets = self.rules["capital_gains"]["long_term"].get(
            filing_status, self.rules["capital_gains"]["long_term"]["single"]
        )
        cap_gains_tax = self._calculate_tax_from_brackets(preferential_income, cap_gains_brackets)

        # Total tax
        total_tax = ordinary_tax + cap_gains_tax

        return {
            "total_income": total_income,
            "taxable_income": taxable_income,
            "taxable_ordinary_income": taxable_ordinary,
            "standard_deduction": standard_deduction,
            "ordinary_income_tax": ordinary_tax,
            "capital_gains_income": preferential_income,
            "capital_gains_tax": cap_gains_tax,
            "total_tax": total_tax,
        }

    def _calculate_tax_from_brackets(
        self,
        income: float,
        brackets: list[dict],
    ) -> float:
        """Calculate tax using tax brackets."""
        tax = 0.0
        remaining = income

        for bracket in brackets:
            bracket_min = bracket["min"]
            bracket_max = bracket["max"]
            rate = bracket["rate"]

            if remaining <= 0:
                break

            if bracket_max is None:
                # Top bracket
                taxable_in_bracket = remaining
            else:
                bracket_size = bracket_max - bracket_min
                taxable_in_bracket = min(remaining, bracket_size)

            tax += taxable_in_bracket * rate
            remaining -= taxable_in_bracket

        return tax

    def generate_analysis(self, taxpayer: TaxpayerProfile | None = None) -> dict[str, Any]:
        """
        Generate a complete tax analysis.

        Args:
            taxpayer: Taxpayer profile (optional, will try to load from DB)

        Returns:
            Complete analysis dictionary
        """
        documents = self.get_documents()

        if not documents:
            return {
                "error": "No documents found",
                "tax_year": self.tax_year,
            }

        # Get or create taxpayer profile
        if taxpayer is None:
            taxpayer = self.db.get_taxpayer_profile(self.tax_year)

        filing_status = (
            taxpayer.filing_status if taxpayer else FilingStatus.SINGLE
        )

        # Calculate summaries
        income = self.calculate_income_summary(documents)
        withholding = self.calculate_withholding(documents)
        tax_estimate = self.estimate_tax_liability(income, filing_status)

        # Calculate refund or amount owed
        total_withheld = withholding["federal"]
        estimated_tax = tax_estimate["total_tax"]
        refund_or_owed = total_withheld - estimated_tax

        return {
            "tax_year": self.tax_year,
            "filing_status": filing_status.value if isinstance(filing_status, FilingStatus) else filing_status,
            "documents_count": len(documents),
            "documents_by_type": self._count_by_type(documents),
            "income_summary": income,
            "total_income": sum(income.values()),
            "withholding_summary": withholding,
            "tax_estimate": tax_estimate,
            "refund_or_owed": refund_or_owed,
            "estimated_refund": refund_or_owed if refund_or_owed > 0 else 0,
            "estimated_owed": -refund_or_owed if refund_or_owed < 0 else 0,
        }

    def _count_by_type(self, documents: list[TaxDocument]) -> dict[str, int]:
        """Count documents by type."""
        counts: dict[str, int] = {}
        for doc in documents:
            doc_type = get_enum_value(doc.document_type)
            counts[doc_type] = counts.get(doc_type, 0) + 1
        return counts

    def generate_ai_analysis(
        self,
        taxpayer: TaxpayerProfile | None = None,
        use_sdk: bool | None = None,
    ) -> str:
        """
        Generate AI-powered analysis using Claude.

        When Agent SDK is enabled, this method can use tools to verify
        data against source documents and look up current IRS rules.

        Args:
            taxpayer: Taxpayer profile
            use_sdk: Override config.use_agent_sdk (None = use config)

        Returns:
            Natural language analysis
        """
        documents = self.get_documents()
        if not documents:
            return "No tax documents have been collected yet."

        # Build document summary for Claude
        doc_summaries = []
        source_dir = None
        for doc in documents:
            summary = f"- {get_enum_value(doc.document_type)} from {doc.issuer_name}"
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
                    qualified = doc.extracted_data.get("box_1b", 0)
                    summary += f": Dividends ${dividends:,.2f} (Qualified: ${qualified:,.2f})"
                elif doc.document_type == DocumentType.FORM_1099_B:
                    total_proceeds = doc.extracted_data.get("summary", {}).get("total_proceeds", 0)
                    summary += f": Total proceeds ${total_proceeds:,.2f}"
            doc_summaries.append(summary)

            # Track source directory for SDK tool access
            if doc.file_path and source_dir is None:
                source_dir = Path(doc.file_path).parent

        documents_text = "\n".join(doc_summaries)

        # Build taxpayer info
        if taxpayer:
            taxpayer_text = f"""
Filing Status: {get_enum_value(taxpayer.filing_status)}
State: {taxpayer.state}
Dependents: {taxpayer.num_dependents}
Self-employed: {taxpayer.is_self_employed}
Has HSA: {taxpayer.has_hsa}
"""
        else:
            config = get_config()
            taxpayer_text = f"""
State: {config.state or 'Not specified'}
Filing Status: {config.get('filing_status', 'Not specified')}
"""

        # Determine whether to use SDK
        config = get_config()
        should_use_sdk = use_sdk if use_sdk is not None else config.use_agent_sdk

        if should_use_sdk:
            sdk_agent = _get_sdk_agent()
            if sdk_agent:
                # Use SDK with tool access for enhanced analysis
                return sdk_agent.analyze_documents(
                    documents_text,
                    taxpayer_text,
                    source_dir=source_dir,
                )

        # Fall back to legacy agent
        agent = get_agent()
        return agent.analyze_tax_implications(documents_text, taxpayer_text)


def analyze_taxes(tax_year: int | None = None) -> dict[str, Any]:
    """Convenience function to run tax analysis."""
    analyzer = TaxAnalyzer(tax_year)
    return analyzer.generate_analysis()

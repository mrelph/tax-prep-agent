"""Agent compatibility layer with Claude Agent SDK as primary interface.

The Claude Agent SDK is the primary interface for AI operations, providing:
- Agentic loops with tool use for verification
- Specialized subagents for different tax domains
- Safety hooks for SSN redaction and file access control
- Streaming responses for real-time feedback

Legacy Anthropic SDK fallback is provided when the Agent SDK is unavailable.

Usage:
    from tax_agent.agent_compat import get_compatible_agent

    agent = get_compatible_agent()
    # Uses Agent SDK by default:
    result = agent.classify_document(text)
    analysis = agent.analyze_tax_implications(docs, profile)

    # Check which backend is active:
    print(agent.backend_name)  # "agent_sdk" or "legacy"
"""

from pathlib import Path
from typing import Any, AsyncIterator, Protocol, runtime_checkable

from tax_agent.config import get_config


@runtime_checkable
class TaxAgentInterface(Protocol):
    """Protocol defining the tax agent interface."""

    def classify_document(self, text: str, file_path: Path | None = None) -> dict:
        """Classify a tax document."""
        ...

    def extract_w2_data(self, text: str) -> dict:
        """Extract W-2 data."""
        ...

    def extract_1099_int_data(self, text: str) -> dict:
        """Extract 1099-INT data."""
        ...

    def extract_1099_div_data(self, text: str) -> dict:
        """Extract 1099-DIV data."""
        ...

    def extract_1099_b_data(self, text: str) -> dict:
        """Extract 1099-B data."""
        ...

    def extract_1099_nec_data(self, text: str) -> dict:
        """Extract 1099-NEC data."""
        ...

    def extract_1099_r_data(self, text: str) -> dict:
        """Extract 1099-R data."""
        ...

    def extract_1098_data(self, text: str) -> dict:
        """Extract 1098 data."""
        ...

    def extract_w2_g_data(self, text: str) -> dict:
        """Extract W-2G data."""
        ...

    def extract_1099_misc_data(self, text: str) -> dict:
        """Extract 1099-MISC data."""
        ...

    def extract_1099_g_data(self, text: str) -> dict:
        """Extract 1099-G data."""
        ...

    def extract_1099_k_data(self, text: str) -> dict:
        """Extract 1099-K data."""
        ...

    def extract_1098_t_data(self, text: str) -> dict:
        """Extract 1098-T data."""
        ...

    def extract_1098_e_data(self, text: str) -> dict:
        """Extract 1098-E data."""
        ...

    def extract_5498_data(self, text: str) -> dict:
        """Extract 5498 data."""
        ...

    def extract_k1_data(self, text: str) -> dict:
        """Extract K-1 data."""
        ...

    def analyze_tax_implications(
        self,
        documents_summary: str,
        taxpayer_info: str,
        source_dir: Path | None = None,
    ) -> str:
        """Analyze tax implications."""
        ...

    def review_tax_return(
        self,
        return_text: str,
        source_documents: str,
        source_dir: Path | None = None,
    ) -> str:
        """Review a tax return."""
        ...


class CompatibleAgent:
    """
    Unified agent interface with Claude Agent SDK as the primary backend.

    Uses the Agent SDK by default, which provides:
    - Agentic verification with tool access
    - Web search for current IRS rules and limits
    - Specialized subagents for different tax domains
    - Safety hooks for data protection

    Falls back to the legacy Anthropic SDK when the Agent SDK is unavailable
    (e.g., when claude-code-sdk package is not installed).
    """

    def __init__(self):
        """Initialize the compatible agent."""
        self.config = get_config()
        self._legacy_agent = None
        self._sdk_agent = None

    @property
    def legacy_agent(self):
        """Get the legacy agent (lazy initialization)."""
        if self._legacy_agent is None:
            from tax_agent.agent import get_agent
            self._legacy_agent = get_agent()
        return self._legacy_agent

    @property
    def sdk_agent(self):
        """Get the SDK agent if available (lazy initialization)."""
        if self._sdk_agent is None and self.config.use_agent_sdk:
            from tax_agent.agent_sdk import get_sdk_agent, sdk_available
            if sdk_available():
                self._sdk_agent = get_sdk_agent()
        return self._sdk_agent

    def _use_sdk(self) -> bool:
        """Check if SDK should be used."""
        return self.config.use_agent_sdk and self.sdk_agent is not None

    @property
    def is_sdk_enabled(self) -> bool:
        """Check if SDK features are currently active."""
        return self._use_sdk()

    @property
    def backend_name(self) -> str:
        """Get the name of the active backend."""
        return "agent_sdk" if self._use_sdk() else "legacy"

    # Document classification

    def classify_document(
        self,
        text: str,
        file_path: Path | None = None,
    ) -> dict:
        """
        Classify a tax document.

        When SDK is enabled, uses agentic verification with tool access.

        Args:
            text: Document text
            file_path: Optional path to source file for verification

        Returns:
            Classification dictionary
        """
        if self._use_sdk():
            return self.sdk_agent.classify_document(text, file_path)
        return self.legacy_agent.classify_document(text)

    # Data extraction methods (currently legacy only)

    def extract_w2_data(self, text: str) -> dict:
        """Extract W-2 data."""
        return self.legacy_agent.extract_w2_data(text)

    def extract_1099_int_data(self, text: str) -> dict:
        """Extract 1099-INT data."""
        return self.legacy_agent.extract_1099_int_data(text)

    def extract_1099_div_data(self, text: str) -> dict:
        """Extract 1099-DIV data."""
        return self.legacy_agent.extract_1099_div_data(text)

    def extract_1099_b_data(self, text: str) -> dict:
        """Extract 1099-B data."""
        return self.legacy_agent.extract_1099_b_data(text)

    def extract_1099_nec_data(self, text: str) -> dict:
        """Extract 1099-NEC data."""
        return self.legacy_agent.extract_1099_nec_data(text)

    def extract_1099_r_data(self, text: str) -> dict:
        """Extract 1099-R data."""
        return self.legacy_agent.extract_1099_r_data(text)

    def extract_1098_data(self, text: str) -> dict:
        """Extract 1098 data."""
        return self.legacy_agent.extract_1098_data(text)

    def extract_w2_g_data(self, text: str) -> dict:
        """Extract W-2G data."""
        return self.legacy_agent.extract_w2_g_data(text)

    def extract_1099_misc_data(self, text: str) -> dict:
        """Extract 1099-MISC data."""
        return self.legacy_agent.extract_1099_misc_data(text)

    def extract_1099_g_data(self, text: str) -> dict:
        """Extract 1099-G data."""
        return self.legacy_agent.extract_1099_g_data(text)

    def extract_1099_k_data(self, text: str) -> dict:
        """Extract 1099-K data."""
        return self.legacy_agent.extract_1099_k_data(text)

    def extract_1098_t_data(self, text: str) -> dict:
        """Extract 1098-T data."""
        return self.legacy_agent.extract_1098_t_data(text)

    def extract_1098_e_data(self, text: str) -> dict:
        """Extract 1098-E data."""
        return self.legacy_agent.extract_1098_e_data(text)

    def extract_5498_data(self, text: str) -> dict:
        """Extract 5498 data."""
        return self.legacy_agent.extract_5498_data(text)

    def extract_k1_data(self, text: str) -> dict:
        """Extract K-1 data."""
        return self.legacy_agent.extract_k1_data(text)

    # Analysis methods

    def analyze_tax_implications(
        self,
        documents_summary: str,
        taxpayer_info: str,
        source_dir: Path | None = None,
    ) -> str:
        """
        Analyze tax implications.

        When SDK is enabled, can verify data against source documents
        and look up current IRS rules via web search.

        Args:
            documents_summary: Summary of collected documents
            taxpayer_info: Taxpayer profile information
            source_dir: Directory containing source documents

        Returns:
            Analysis text
        """
        if self._use_sdk():
            return self.sdk_agent.analyze_documents(
                documents_summary,
                taxpayer_info,
                source_dir,
            )
        return self.legacy_agent.analyze_tax_implications(
            documents_summary,
            taxpayer_info,
        )

    async def analyze_tax_implications_async(
        self,
        documents_summary: str,
        taxpayer_info: str,
        source_dir: Path | None = None,
    ) -> AsyncIterator[str]:
        """
        Analyze tax implications with streaming (SDK only).

        Args:
            documents_summary: Summary of collected documents
            taxpayer_info: Taxpayer profile information
            source_dir: Directory containing source documents

        Yields:
            Analysis text chunks
        """
        if self._use_sdk():
            async for chunk in self.sdk_agent.analyze_documents_async(
                documents_summary,
                taxpayer_info,
                source_dir,
            ):
                yield chunk
        else:
            yield self.legacy_agent.analyze_tax_implications(
                documents_summary,
                taxpayer_info,
            )

    def review_tax_return(
        self,
        return_text: str,
        source_documents: str,
        source_dir: Path | None = None,
    ) -> str:
        """
        Review a tax return.

        When SDK is enabled, can cross-reference against source documents
        using tool access.

        Args:
            return_text: Text from tax return
            source_documents: Summary of source documents
            source_dir: Directory containing source documents

        Returns:
            Review findings
        """
        if self._use_sdk():
            return self.sdk_agent.review_return(
                return_text,
                source_documents,
                source_dir,
            )
        return self.legacy_agent.review_tax_return(
            return_text,
            source_documents,
        )

    async def review_tax_return_async(
        self,
        return_text: str,
        source_documents: str,
        source_dir: Path | None = None,
    ) -> AsyncIterator[str]:
        """
        Review a tax return with streaming (SDK only).

        Args:
            return_text: Text from tax return
            source_documents: Summary of source documents
            source_dir: Directory containing source documents

        Yields:
            Review findings chunks
        """
        if self._use_sdk():
            async for chunk in self.sdk_agent.review_return_async(
                return_text,
                source_documents,
                source_dir,
            ):
                yield chunk
        else:
            yield self.legacy_agent.review_tax_return(
                return_text,
                source_documents,
            )

    # Interactive query (SDK-enhanced)

    def interactive_query(
        self,
        query_text: str,
        context: dict | None = None,
        source_dir: Path | None = None,
    ) -> str:
        """
        Run an interactive tax query.

        When SDK is enabled, provides full tool access for verification
        and research. Falls back to a simple analysis with legacy agent.

        Args:
            query_text: User's question or request
            context: Optional context dictionary
            source_dir: Directory for file access

        Returns:
            Response text
        """
        if self._use_sdk():
            return self.sdk_agent.interactive_query(
                query_text,
                context,
                source_dir,
            )
        # Legacy fallback - simple analysis
        context_str = ""
        if context:
            import json
            context_str = f"\n\nContext:\n{json.dumps(context, indent=2, default=str)}"
        return self.legacy_agent._call(
            "You are an expert tax advisor. Provide helpful, accurate advice.",
            f"{query_text}{context_str}",
            max_tokens=2000,
        )

    async def interactive_query_async(
        self,
        query_text: str,
        context: dict | None = None,
        source_dir: Path | None = None,
    ) -> AsyncIterator[str]:
        """
        Run an interactive tax query with streaming (SDK only).

        Args:
            query_text: User's question or request
            context: Optional context dictionary
            source_dir: Directory for file access

        Yields:
            Response chunks
        """
        if self._use_sdk():
            async for chunk in self.sdk_agent.interactive_query_async(
                query_text,
                context,
                source_dir,
            ):
                yield chunk
        else:
            yield self.interactive_query(query_text, context, source_dir)

    # SDK-enhanced methods with legacy fallback

    def _sdk_query_with_fallback(
        self,
        prompt: str,
        context: dict,
        legacy_fn,
        legacy_args: tuple,
    ):
        """Route through SDK interactive_query with legacy fallback."""
        if self._use_sdk():
            import json
            try:
                result = self.sdk_agent.interactive_query(prompt, context)
                # Try to parse JSON from response
                text = result.strip()
                if "```" in text:
                    import re
                    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
                    if match:
                        text = match.group(1).strip()
                brace_start = text.find("{")
                brace_end = text.rfind("}")
                if brace_start >= 0 and brace_end > brace_start:
                    return json.loads(text[brace_start:brace_end + 1])
                return {"analysis": result}
            except Exception:
                pass
        return legacy_fn(*legacy_args)

    def validate_documents_cross_reference(self, documents_data: list[dict]) -> dict:
        """Cross-validate documents for consistency."""
        import json
        return self._sdk_query_with_fallback(
            prompt=(
                "Cross-validate these tax documents for consistency. "
                "Check that amounts match across related documents (e.g. W-2 wages vs 1040 Line 1). "
                "Return a JSON object with 'consistent' (bool), 'discrepancies' (list), and 'summary'."
            ),
            context={"documents": documents_data},
            legacy_fn=self.legacy_agent.validate_documents_cross_reference,
            legacy_args=(documents_data,),
        )

    def assess_audit_risk(
        self,
        return_summary: dict,
        documents_summary: dict,
    ) -> dict:
        """Assess audit risk based on return data."""
        return self._sdk_query_with_fallback(
            prompt=(
                "Assess the audit risk for this tax return. Consider DIF scores, "
                "unusual deduction ratios, round numbers, and IRS matching program triggers. "
                "Return JSON with 'risk_level', 'risk_score' (1-10), 'flags' (list), and 'recommendations'."
            ),
            context={"return_summary": return_summary, "documents": documents_summary},
            legacy_fn=self.legacy_agent.assess_audit_risk,
            legacy_args=(return_summary, documents_summary),
        )

    def compare_filing_scenarios(
        self,
        income_data: dict,
        deductions_data: dict,
        tax_year: int,
    ) -> dict:
        """Compare filing scenarios (e.g. standard vs itemized, MFJ vs MFS)."""
        return self._sdk_query_with_fallback(
            prompt=(
                f"Compare filing scenarios for tax year {tax_year}. "
                "Analyze standard vs itemized deductions, and if married, MFJ vs MFS. "
                "Return JSON with 'scenarios' (list of {name, tax_liability, refund}), "
                "'recommended', and 'savings'."
            ),
            context={"income": income_data, "deductions": deductions_data, "tax_year": tax_year},
            legacy_fn=self.legacy_agent.compare_filing_scenarios,
            legacy_args=(income_data, deductions_data, tax_year),
        )

    def analyze_investment_taxes(
        self,
        transactions: list[dict],
        holdings: list[dict] | None = None,
    ) -> dict:
        """Analyze investment taxes including wash sales and optimization."""
        return self._sdk_query_with_fallback(
            prompt=(
                "Analyze these investment transactions for tax implications. "
                "Check for wash sales, identify tax-loss harvesting opportunities, "
                "and classify short-term vs long-term gains. "
                "Return JSON with 'total_gain_loss', 'wash_sales', 'harvesting_opportunities', "
                "and 'recommendations'."
            ),
            context={"transactions": transactions, "holdings": holdings or []},
            legacy_fn=self.legacy_agent.analyze_investment_taxes,
            legacy_args=(transactions, holdings),
        )

    def identify_missing_documents(
        self,
        collected_docs: list[dict],
        tax_profile: dict,
    ) -> dict:
        """Identify potentially missing tax documents."""
        return self._sdk_query_with_fallback(
            prompt=(
                "Based on this taxpayer's profile and collected documents, "
                "identify any documents that are likely missing. "
                "Return JSON with 'missing' (list of {type, reason, importance}), "
                "'complete' (bool), and 'recommendations'."
            ),
            context={"collected_documents": collected_docs, "taxpayer_profile": tax_profile},
            legacy_fn=self.legacy_agent.identify_missing_documents,
            legacy_args=(collected_docs, tax_profile),
        )

    def deep_document_analysis(
        self,
        document_type: str,
        extracted_data: dict,
        raw_text: str,
    ) -> dict:
        """Perform deep analysis of a specific document."""
        return self._sdk_query_with_fallback(
            prompt=(
                f"Perform a deep analysis of this {document_type} document. "
                "Verify extracted amounts, identify unusual entries, "
                "and flag anything that needs attention. "
                "Return JSON with 'verified' (bool), 'issues' (list), "
                "'additional_data' (any missed fields), and 'notes'."
            ),
            context={"document_type": document_type, "extracted_data": extracted_data},
            legacy_fn=self.legacy_agent.deep_document_analysis,
            legacy_args=(document_type, extracted_data, raw_text),
        )

    def generate_tax_planning_recommendations(
        self,
        current_year_data: dict,
        profile: dict,
    ) -> dict:
        """Generate tax planning recommendations."""
        return self._sdk_query_with_fallback(
            prompt=(
                "Generate specific, actionable tax planning recommendations "
                "based on this taxpayer's current year data and profile. "
                "Consider retirement contributions, Roth conversions, "
                "estimated payments, and timing strategies. "
                "Return JSON with 'recommendations' (list of {title, description, "
                "estimated_savings, priority}), and 'summary'."
            ),
            context={"current_year": current_year_data, "profile": profile},
            legacy_fn=self.legacy_agent.generate_tax_planning_recommendations,
            legacy_args=(current_year_data, profile),
        )


# Global compatible agent instance
_compat_agent: CompatibleAgent | None = None


def get_compatible_agent() -> CompatibleAgent:
    """
    Get the global compatible agent instance.

    This is the recommended way to get an agent for new code.
    It automatically uses SDK features when enabled.

    Returns:
        CompatibleAgent instance
    """
    global _compat_agent
    if _compat_agent is None:
        _compat_agent = CompatibleAgent()
    return _compat_agent


def reset_compatible_agent() -> None:
    """Reset the global compatible agent (useful for testing)."""
    global _compat_agent
    _compat_agent = None

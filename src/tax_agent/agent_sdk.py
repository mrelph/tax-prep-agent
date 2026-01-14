"""Claude Agent SDK integration for agentic tax document analysis.

This module provides an alternative to the direct Anthropic SDK (agent.py),
enabling agentic loops, tool use, and more sophisticated analysis capabilities.
"""

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

from tax_agent.config import get_config

# Model mapping (same as agent.py for consistency)
AGENT_SDK_MODELS = {
    "claude-opus-4-5": "claude-opus-4-5-20251101",
    "claude-sonnet-4-5": "claude-sonnet-4-5-20250929",
    "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
    "claude-3-opus": "claude-3-opus-20240229",
    "claude-3-sonnet": "claude-3-sonnet-20240229",
    "claude-3-haiku": "claude-3-haiku-20240307",
}

DEFAULT_MODEL = "claude-sonnet-4-5"


# Tax-specific system prompts
TAX_DOCUMENT_CLASSIFIER_PROMPT = """You are a tax document classifier with access to tools for verification.

When classifying documents:
1. First identify the document type from visual cues and content
2. If uncertain, use available tools to search for specific markers
3. Verify your classification by checking key fields match the form type
4. Return a JSON classification with confidence score

DOCUMENT CATEGORIES:

SOURCE DOCUMENTS (used to prepare tax returns):
- W2, W2_G, 1099_INT, 1099_DIV, 1099_B, 1099_NEC, 1099_MISC, 1099_R, 1099_G, 1099_K
- 1098 (mortgage), 1098_T (tuition), 1098_E (student loan)
- 5498 (IRA), K1 (partnership)

COMPLETED TAX RETURNS (for review):
- 1040, 1040_SR, 1040_NR, 1040_X
- SCHEDULE_A/B/C/D/E/SE
- STATE_RETURN
"""

TAX_ANALYSIS_PROMPT = """You are an AGGRESSIVE tax advisor with access to tools for verification and research.
Your primary mission is to MINIMIZE the taxpayer's tax burden through every legal means available.

You have access to:
- File reading tools to verify source document data
- Search tools to find patterns across documents
- Web tools to research current IRS limits and rules
- Tax calculation tools

Always verify key figures against source documents before making recommendations.
Be SPECIFIC with dollar amounts. The goal is MAXIMUM tax efficiency within legal bounds.
"""

TAX_REVIEW_PROMPT = """You are an EXPERT IRS auditor and tax optimization specialist with tool access.

You can:
- Read source documents to verify amounts
- Search across documents for discrepancies
- Look up current tax rules and limits

For EACH finding, provide:
- SEVERITY: ERROR (must fix) / WARNING (investigate) / OPPORTUNITY (money left on table)
- CATEGORY: income/deduction/credit/compliance/optimization
- ISSUE: Clear description with specific amounts
- TAX IMPACT: Dollar amount at stake
- ACTION: Specific fix or optimization

Be AGGRESSIVE in finding issues. Cross-reference everything against source documents.
"""


class TaxAgentSDK:
    """Agent SDK-powered tax agent with tool use and agentic loops."""

    def __init__(
        self,
        model: str | None = None,
        max_turns: int | None = None,
        use_hooks: bool = True,
    ):
        """
        Initialize the SDK-based tax agent.

        Args:
            model: Claude model to use. Defaults to config setting.
            max_turns: Maximum agentic turns before stopping.
            use_hooks: Whether to use safety/audit hooks.
        """
        self.config = get_config()
        base_model = model or self.config.get("model", DEFAULT_MODEL)
        self.model = AGENT_SDK_MODELS.get(base_model, base_model)
        self.max_turns = max_turns or self.config.agent_sdk_max_turns
        self.use_hooks = use_hooks
        self._sdk_available = self._check_sdk_available()
        self._hooks = None

    def _check_sdk_available(self) -> bool:
        """Check if the Claude Agent SDK is available."""
        try:
            from claude_code_sdk import query
            return True
        except ImportError:
            return False

    def _get_hooks(self) -> dict | None:
        """Get configured hooks for SDK operations."""
        if not self.use_hooks:
            return None

        if self._hooks is None:
            try:
                from tax_agent.hooks import get_tax_hooks
                self._hooks = get_tax_hooks()
            except ImportError:
                self._hooks = {}

        return self._hooks if self._hooks else None

    def _get_allowed_tools(self, include_web: bool | None = None) -> list[str]:
        """Get list of allowed tools for tax operations."""
        tools = ["Read", "Grep", "Glob"]

        # Check config if not explicitly specified
        if include_web is None:
            include_web = self.config.agent_sdk_allow_web

        if include_web:
            tools.extend(["WebSearch", "WebFetch"])
        return tools

    def get_subagent(self, name: str):
        """
        Get a specialized subagent by name.

        Args:
            name: Subagent name (e.g., 'deduction-finder', 'compliance-auditor')

        Returns:
            SubagentDefinition or None
        """
        from tax_agent.subagents import get_subagent
        return get_subagent(name)

    def list_subagents(self) -> list[dict[str, str]]:
        """List all available specialized subagents."""
        from tax_agent.subagents import list_subagents
        return list_subagents()

    async def invoke_subagent_async(
        self,
        subagent_name: str,
        prompt: str,
        source_dir: Path | None = None,
    ) -> AsyncIterator[str]:
        """
        Invoke a specialized subagent for a specific task.

        Args:
            subagent_name: Name of the subagent to invoke
            prompt: Task prompt for the subagent
            source_dir: Directory for file access

        Yields:
            Response chunks from the subagent
        """
        from tax_agent.subagents import get_subagent

        subagent = get_subagent(subagent_name)
        if not subagent:
            yield f"Unknown subagent: {subagent_name}"
            return

        if not self._sdk_available:
            yield "Agent SDK not available for subagent invocation"
            return

        from claude_code_sdk import query, ClaudeCodeOptions

        # Use subagent's model or default
        model = subagent.model or self.model

        options = ClaudeCodeOptions(
            system_prompt=subagent.system_prompt,
            allowed_tools=subagent.allowed_tools,
            max_turns=subagent.max_turns,
            model=model,
            cwd=str(source_dir) if source_dir else None,
        )

        async for message in query(prompt=prompt, options=options):
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        yield block.text

    def invoke_subagent(
        self,
        subagent_name: str,
        prompt: str,
        source_dir: Path | None = None,
    ) -> str:
        """Synchronous wrapper for invoke_subagent_async."""
        chunks = []
        async def collect():
            async for chunk in self.invoke_subagent_async(
                subagent_name, prompt, source_dir
            ):
                chunks.append(chunk)
        asyncio.run(collect())
        return "".join(chunks)

    async def classify_document_async(
        self,
        text: str,
        file_path: Path | None = None,
    ) -> dict:
        """
        Classify a tax document using agentic loop with verification.

        Args:
            text: Extracted text from the document
            file_path: Optional path to source file for tool access

        Returns:
            Dictionary with document classification
        """
        if not self._sdk_available:
            # Fall back to legacy agent
            from tax_agent.agent import get_agent
            return get_agent().classify_document(text)

        from claude_code_sdk import query, ClaudeCodeOptions

        options = ClaudeCodeOptions(
            system_prompt=TAX_DOCUMENT_CLASSIFIER_PROMPT,
            allowed_tools=["Read", "Grep"] if file_path else [],
            max_turns=3,
            model=self.model,
        )

        prompt = f"""Classify this tax document and return a JSON object with:
- document_type: The document type (W2, 1099_INT, 1040, etc.)
- document_category: "SOURCE" or "RETURN"
- confidence: 0.0-1.0
- issuer_name: Entity that issued this document
- tax_year: Tax year
- reasoning: Brief explanation

Document text:
{text[:8000]}
"""

        result = {}
        async for message in query(prompt=prompt, options=options):
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        result = self._parse_json_response(block.text)

        return result or {
            "document_type": "UNKNOWN",
            "confidence": 0.0,
            "reasoning": "Failed to classify document",
        }

    async def analyze_documents_async(
        self,
        documents_summary: str,
        taxpayer_info: str,
        source_dir: Path | None = None,
    ) -> AsyncIterator[str]:
        """
        Analyze tax documents with agentic verification capabilities.

        Args:
            documents_summary: Summary of all collected documents
            taxpayer_info: Taxpayer profile information
            source_dir: Directory containing source documents for tool access

        Yields:
            Analysis text chunks as they're generated
        """
        if not self._sdk_available:
            from tax_agent.agent import get_agent
            result = get_agent().analyze_tax_implications(documents_summary, taxpayer_info)
            yield result
            return

        from claude_code_sdk import query, ClaudeCodeOptions

        options = ClaudeCodeOptions(
            system_prompt=TAX_ANALYSIS_PROMPT,
            allowed_tools=self._get_allowed_tools(include_web=True),
            max_turns=self.max_turns,
            model=self.model,
            cwd=str(source_dir) if source_dir else None,
        )

        prompt = f"""Analyze this taxpayer's situation. Verify key figures by reading
source documents if needed. Use current IRS limits via web search when relevant.

Taxpayer Information:
{taxpayer_info}

Collected Documents Summary:
{documents_summary}

Provide comprehensive analysis with verification of key figures."""

        async for message in query(prompt=prompt, options=options):
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        yield block.text

    async def review_return_async(
        self,
        return_text: str,
        source_documents: str,
        source_dir: Path | None = None,
    ) -> AsyncIterator[str]:
        """
        Review a tax return with agentic verification against source documents.

        Args:
            return_text: Text extracted from the tax return
            source_documents: Summary of source documents
            source_dir: Directory containing source documents

        Yields:
            Review findings as they're generated
        """
        if not self._sdk_available:
            from tax_agent.agent import get_agent
            result = get_agent().review_tax_return(return_text, source_documents)
            yield result
            return

        from claude_code_sdk import query, ClaudeCodeOptions

        options = ClaudeCodeOptions(
            system_prompt=TAX_REVIEW_PROMPT,
            allowed_tools=self._get_allowed_tools(include_web=True),
            max_turns=self.max_turns,
            model=self.model,
            cwd=str(source_dir) if source_dir else None,
        )

        prompt = f"""Review this tax return against source documents.
Cross-reference ALL amounts. Find EVERY error and optimization opportunity.

Source Documents:
{source_documents}

Tax Return:
{return_text}

Verify each amount against source documents and identify discrepancies."""

        async for message in query(prompt=prompt, options=options):
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        yield block.text

    async def interactive_query_async(
        self,
        query_text: str,
        context: dict | None = None,
        source_dir: Path | None = None,
    ) -> AsyncIterator[str]:
        """
        Run an interactive tax query with full tool access.

        Args:
            query_text: The user's question or request
            context: Optional context (documents, profile, etc.)
            source_dir: Directory for file access

        Yields:
            Response chunks as they're generated
        """
        if not self._sdk_available:
            yield "Agent SDK not available. Install claude-code-sdk for agentic features."
            return

        from claude_code_sdk import query, ClaudeCodeOptions

        system_prompt = """You are an expert tax advisor with access to tools.
You can read files, search for patterns, and look up current tax information.
Provide specific, actionable advice based on the taxpayer's situation.
Always verify your recommendations against source documents when available."""

        options = ClaudeCodeOptions(
            system_prompt=system_prompt,
            allowed_tools=self._get_allowed_tools(include_web=True),
            max_turns=self.max_turns,
            model=self.model,
            cwd=str(source_dir) if source_dir else None,
        )

        full_prompt = query_text
        if context:
            full_prompt = f"""Context:
{json.dumps(context, indent=2, default=str)}

Question/Request:
{query_text}"""

        async for message in query(prompt=full_prompt, options=options):
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'text'):
                        yield block.text

    # Synchronous wrapper methods for backward compatibility

    def classify_document(self, text: str, file_path: Path | None = None) -> dict:
        """Synchronous wrapper for classify_document_async."""
        return asyncio.run(self.classify_document_async(text, file_path))

    def analyze_documents(
        self,
        documents_summary: str,
        taxpayer_info: str,
        source_dir: Path | None = None,
    ) -> str:
        """Synchronous wrapper for analyze_documents_async."""
        chunks = []
        async def collect():
            async for chunk in self.analyze_documents_async(
                documents_summary, taxpayer_info, source_dir
            ):
                chunks.append(chunk)
        asyncio.run(collect())
        return "".join(chunks)

    def review_return(
        self,
        return_text: str,
        source_documents: str,
        source_dir: Path | None = None,
    ) -> str:
        """Synchronous wrapper for review_return_async."""
        chunks = []
        async def collect():
            async for chunk in self.review_return_async(
                return_text, source_documents, source_dir
            ):
                chunks.append(chunk)
        asyncio.run(collect())
        return "".join(chunks)

    def interactive_query(
        self,
        query_text: str,
        context: dict | None = None,
        source_dir: Path | None = None,
    ) -> str:
        """Synchronous wrapper for interactive_query_async."""
        chunks = []
        async def collect():
            async for chunk in self.interactive_query_async(
                query_text, context, source_dir
            ):
                chunks.append(chunk)
        asyncio.run(collect())
        return "".join(chunks)

    def _parse_json_response(self, text: str) -> dict:
        """Parse JSON from Claude's response, handling markdown code blocks."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    @property
    def is_available(self) -> bool:
        """Check if Agent SDK features are available."""
        return self._sdk_available


# Global SDK agent instance
_sdk_agent: TaxAgentSDK | None = None


def get_sdk_agent() -> TaxAgentSDK:
    """Get the global SDK-based tax agent instance."""
    global _sdk_agent
    if _sdk_agent is None:
        _sdk_agent = TaxAgentSDK()
    return _sdk_agent


def sdk_available() -> bool:
    """Check if the Claude Agent SDK is available."""
    try:
        from claude_code_sdk import query
        return True
    except ImportError:
        return False

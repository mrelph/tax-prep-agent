"""Interactive chat mode for exploring tax strategies with the user."""

import asyncio
from pathlib import Path
from typing import AsyncIterator

from tax_agent.agent import get_agent
from tax_agent.config import get_config
from tax_agent.models.documents import TaxDocument
from tax_agent.storage.database import get_database
from tax_agent.utils import get_enum_value


class TaxAdvisorChat:
    """
    Interactive chat for exploring tax strategies.

    Allows back-and-forth conversation about tax situations,
    with context from collected documents.

    When Agent SDK is enabled (via config.use_agent_sdk), the chat
    gains tool access for verifying information against source documents
    and looking up current IRS rules via web search.
    """

    def __init__(self, tax_year: int | None = None):
        self.config = get_config()
        self.tax_year = tax_year or self.config.tax_year
        self.state = self.config.state
        self._agent = None  # Lazy initialization
        self._sdk_agent = None  # Lazy initialization
        self.db = get_database()
        self.conversation_history: list[dict] = []
        self._source_dir: Path | None = None

    @property
    def agent(self):
        """Get the legacy agent (lazy initialization)."""
        if self._agent is None:
            self._agent = get_agent()
        return self._agent

    @property
    def sdk_agent(self):
        """Get the SDK agent if enabled (lazy initialization)."""
        if self._sdk_agent is None and self.config.use_agent_sdk:
            from tax_agent.agent_sdk import get_sdk_agent, sdk_available
            if sdk_available():
                self._sdk_agent = get_sdk_agent()
        return self._sdk_agent

    def _use_sdk(self) -> bool:
        """Check if we should use the Agent SDK."""
        return self.config.use_agent_sdk and self.sdk_agent is not None

    def _build_context(self) -> str:
        """Build context from collected documents and profile."""
        documents = self.db.get_documents(tax_year=self.tax_year)

        context_parts = [
            f"TAX YEAR: {self.tax_year}",
            f"STATE: {self.state or 'Not specified'}",
            "",
            "COLLECTED DOCUMENTS:",
        ]

        if documents:
            for doc in documents:
                summary = f"- {get_enum_value(doc.document_type)} from {doc.issuer_name}"
                if doc.extracted_data:
                    if get_enum_value(doc.document_type) == "W2":
                        wages = doc.extracted_data.get("box_1", 0)
                        summary += f" (Wages: ${wages:,.2f})"
                    elif "1099" in get_enum_value(doc.document_type):
                        for key in ["box_1", "box_1a", "total_proceeds"]:
                            if key in doc.extracted_data:
                                summary += f" (${doc.extracted_data[key]:,.2f})"
                                break
                context_parts.append(summary)

                # Track source directory for SDK tool access
                if doc.file_path and self._source_dir is None:
                    self._source_dir = Path(doc.file_path).parent
        else:
            context_parts.append("- No documents collected yet")

        return "\n".join(context_parts)

    def chat(self, user_message: str) -> str:
        """
        Send a message and get a response.

        Args:
            user_message: The user's question or message

        Returns:
            AI response
        """
        # Use SDK if available and enabled
        if self._use_sdk():
            return self._chat_with_sdk(user_message)

        return self._chat_with_legacy(user_message)

    def _chat_with_legacy(self, user_message: str) -> str:
        """Chat using the legacy agent (direct Anthropic SDK)."""
        context = self._build_context()

        system = f"""You are an expert tax advisor having a conversation with a taxpayer.

TAXPAYER CONTEXT:
{context}

YOUR ROLE:
1. Answer tax questions accurately and specifically
2. Proactively suggest tax-saving strategies relevant to their situation
3. Explain complex topics in plain English
4. Ask clarifying questions when needed
5. Be AGGRESSIVE about finding savings - don't be passive
6. When you identify a potential savings, quantify it with dollar estimates
7. If you need more information to give better advice, ask for it

CONVERSATION STYLE:
- Be conversational but professional
- Give specific, actionable advice
- Cite IRS rules when relevant (Pub 17, Pub 550, etc.)
- If something could save them $100+, emphasize it
- Proactively explore: "Have you considered...?" "Are you aware that...?"

IMPORTANT:
- Stay current with {self.tax_year} tax rules
- If a question is outside tax scope, politely redirect
- Never give advice that could be illegal
- Recommend professional help for complex situations

Previous conversation:
{self._format_history()}"""

        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Get response
        response = self.agent._call(system, user_message, max_tokens=2000)

        # Add response to history
        self.conversation_history.append({"role": "assistant", "content": response})

        return response

    def _chat_with_sdk(self, user_message: str) -> str:
        """
        Chat using the Agent SDK with tool access.

        The SDK chat can:
        - Read source documents to verify information
        - Search documents for specific patterns
        - Look up current IRS rules via web search
        """
        context = self._build_context()

        # Build context dict for SDK
        sdk_context = {
            "tax_year": self.tax_year,
            "state": self.state,
            "taxpayer_situation": context,
            "conversation_history": self._format_history(),
        }

        # Build the full prompt for SDK
        prompt = f"""You are an expert tax advisor having a conversation with a taxpayer.

You have access to tools that let you:
- Read the taxpayer's source documents to verify information
- Search across documents for specific amounts or patterns
- Look up current IRS rules and limits via web search

Use these tools proactively to give accurate, verified advice.

TAXPAYER CONTEXT:
{context}

Previous conversation:
{self._format_history()}

Current question:
{user_message}

Provide a helpful, specific response. If you need to verify something against source documents, use your tools. Be AGGRESSIVE about finding tax savings opportunities."""

        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Get response from SDK
        response = self.sdk_agent.interactive_query(
            prompt,
            context=sdk_context,
            source_dir=self._source_dir,
        )

        # Add response to history
        self.conversation_history.append({"role": "assistant", "content": response})

        return response

    async def chat_async(self, user_message: str) -> AsyncIterator[str]:
        """
        Send a message and stream the response (SDK only).

        Args:
            user_message: The user's question or message

        Yields:
            Response chunks as they're generated
        """
        if not self._use_sdk():
            # Fall back to sync for legacy
            yield self._chat_with_legacy(user_message)
            return

        context = self._build_context()

        sdk_context = {
            "tax_year": self.tax_year,
            "state": self.state,
            "taxpayer_situation": context,
        }

        prompt = f"""You are an expert tax advisor having a conversation with a taxpayer.

You have access to tools that let you:
- Read the taxpayer's source documents to verify information
- Search across documents for specific amounts or patterns
- Look up current IRS rules and limits via web search

TAXPAYER CONTEXT:
{context}

Previous conversation:
{self._format_history()}

Current question:
{user_message}

Provide a helpful, specific response. Be AGGRESSIVE about finding tax savings opportunities."""

        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})

        # Stream response from SDK
        full_response = []
        async for chunk in self.sdk_agent.interactive_query_async(
            prompt,
            context=sdk_context,
            source_dir=self._source_dir,
        ):
            full_response.append(chunk)
            yield chunk

        # Add full response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": "".join(full_response),
        })

    def _format_history(self) -> str:
        """Format conversation history for context."""
        if not self.conversation_history:
            return "(New conversation)"

        # Keep last 10 exchanges
        recent = self.conversation_history[-20:]
        formatted = []
        for msg in recent:
            role = "User" if msg["role"] == "user" else "Advisor"
            content = msg["content"][:500] + "..." if len(msg["content"]) > 500 else msg["content"]
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted)

    def suggest_topics(self) -> list[str]:
        """
        Suggest relevant topics to explore based on documents.

        Returns:
            List of suggested questions/topics
        """
        documents = self.db.get_documents(tax_year=self.tax_year)

        suggestions = [
            "What deductions am I likely missing?",
            "How can I reduce my taxes for next year?",
        ]

        has_w2 = any(get_enum_value(d.document_type) == "W2" for d in documents)
        has_investments = any("1099" in get_enum_value(d.document_type) for d in documents)

        if has_w2:
            suggestions.extend([
                "Should I contribute more to my 401(k)?",
                "Am I withholding enough in taxes?",
                "Can I benefit from a backdoor Roth IRA?",
            ])

        if has_investments:
            suggestions.extend([
                "How can I minimize capital gains taxes?",
                "Should I do tax-loss harvesting?",
                "What's the best way to handle my dividends?",
            ])

        if self.state in ["CA", "NY", "NJ"]:
            suggestions.append("How can I reduce my state tax burden?")

        return suggestions

    def reset(self) -> None:
        """Reset conversation history."""
        self.conversation_history = []


def start_chat_session(tax_year: int | None = None) -> TaxAdvisorChat:
    """Start a new chat session."""
    return TaxAdvisorChat(tax_year)

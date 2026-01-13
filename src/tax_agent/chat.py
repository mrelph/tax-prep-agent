"""Interactive chat mode for exploring tax strategies with the user."""

from tax_agent.agent import get_agent
from tax_agent.config import get_config
from tax_agent.models.documents import TaxDocument
from tax_agent.storage.database import get_database


class TaxAdvisorChat:
    """
    Interactive chat for exploring tax strategies.

    Allows back-and-forth conversation about tax situations,
    with context from collected documents.
    """

    def __init__(self, tax_year: int | None = None):
        config = get_config()
        self.tax_year = tax_year or config.tax_year
        self.state = config.state
        self.agent = get_agent()
        self.db = get_database()
        self.conversation_history: list[dict] = []

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
                summary = f"- {doc.document_type.value} from {doc.issuer_name}"
                if doc.extracted_data:
                    if doc.document_type.value == "W2":
                        wages = doc.extracted_data.get("box_1", 0)
                        summary += f" (Wages: ${wages:,.2f})"
                    elif "1099" in doc.document_type.value:
                        for key in ["box_1", "box_1a", "total_proceeds"]:
                            if key in doc.extracted_data:
                                summary += f" (${doc.extracted_data[key]:,.2f})"
                                break
                context_parts.append(summary)
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

        has_w2 = any(d.document_type.value == "W2" for d in documents)
        has_investments = any("1099" in d.document_type.value for d in documents)

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

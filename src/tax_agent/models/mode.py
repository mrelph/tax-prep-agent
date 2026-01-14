"""Agent mode models for tax agent workflow management."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AgentMode(str, Enum):
    """Operating modes for the tax agent."""

    PREP = "prep"  # Preparing a new tax return
    REVIEW = "review"  # Reviewing a completed return
    PLANNING = "planning"  # Long-term tax planning


class ModeState(BaseModel):
    """Persistent state for a specific mode."""

    id: str = Field(description="Unique identifier for the state")
    mode: AgentMode = Field(description="The operating mode")
    tax_year: int = Field(description="Tax year this state applies to")
    context_data: dict = Field(
        default_factory=dict,
        description="Mode-specific context data",
    )
    conversation_history: list[dict] = Field(
        default_factory=list,
        description="Conversation history for this mode",
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Mode-specific context fields
    # PREP mode: documents collected, analysis progress
    # REVIEW mode: return file path, findings so far
    # PLANNING mode: scenarios analyzed, recommendations

    def update_context(self, key: str, value: any) -> None:
        """Update a context value."""
        self.context_data[key] = value
        self.updated_at = datetime.now()

    def add_message(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()

    def get_recent_history(self, limit: int = 10) -> list[dict]:
        """Get recent conversation history."""
        return self.conversation_history[-limit:]


# Mode display names and descriptions
MODE_INFO = {
    AgentMode.PREP: {
        "name": "PREP",
        "description": "Prepare a new tax return",
        "color": "#4CAF50",  # Green
        "focus": "collecting documents, finding deductions, maximizing credits",
    },
    AgentMode.REVIEW: {
        "name": "REVIEW",
        "description": "Review a completed return",
        "color": "#FF9800",  # Orange
        "focus": "finding errors, missed deductions, amendment opportunities",
    },
    AgentMode.PLANNING: {
        "name": "PLANNING",
        "description": "Long-term tax planning",
        "color": "#2196F3",  # Blue
        "focus": "retirement strategies, scenario analysis, multi-year optimization",
    },
}

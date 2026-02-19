"""Memory models for storing facts and insights across sessions."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MemoryType(str, Enum):
    """Types of memories that can be stored."""

    FACT = "fact"  # Key user information (e.g., "self-employed")
    PREFERENCE = "preference"  # User preferences (e.g., "prefers itemized")
    INSIGHT = "insight"  # Discoveries from analysis
    DECISION = "decision"  # Tax decisions made


class MemoryCategory(str, Enum):
    """Categories for organizing memories."""

    PERSONAL = "personal"  # Name, location, family status
    EMPLOYMENT = "employment"  # Job type, employer, work situation
    INCOME = "income"  # Income sources and amounts
    DEDUCTIONS = "deductions"  # Deductions and expenses
    INVESTMENTS = "investments"  # Investment-related info
    CREDITS = "credits"  # Tax credits eligibility
    PLANNING = "planning"  # Future tax planning decisions
    OTHER = "other"  # Uncategorized


class Memory(BaseModel):
    """Represents a stored memory/fact about the user."""

    id: str = Field(description="Unique identifier for the memory")
    memory_type: MemoryType = Field(description="Type of memory")
    category: MemoryCategory = Field(description="Category for organization")
    content: str = Field(description="The memory content/fact")
    tax_year: int | None = Field(
        default=None,
        description="Tax year this applies to (None for year-agnostic)"
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in this memory (1.0 = explicitly stated)"
    )
    source: str | None = Field(
        default=None,
        description="How this memory was captured (auto/manual)"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(use_enum_values=True)

"""Memory manager for storing and retrieving facts across sessions.

This module provides:
- Auto-extraction of facts from conversations
- Context injection for personalized responses
- Memory CRUD operations
"""

import json
import logging
import uuid
from datetime import datetime

from tax_agent.models.memory import Memory, MemoryCategory, MemoryType
from tax_agent.storage.database import TaxDatabase

logger = logging.getLogger(__name__)

# Prompt for extracting memories from conversations
EXTRACTION_PROMPT = """Analyze this conversation exchange and extract any facts worth remembering about the user.

USER MESSAGE:
{user_message}

ASSISTANT RESPONSE:
{response}

Extract facts as a JSON array. For each fact, provide:
- "type": One of "fact", "preference", "insight", "decision"
- "category": One of "personal", "employment", "income", "deductions", "investments", "credits", "planning", "other"
- "content": A concise statement of the fact (max 100 chars)

Guidelines:
- ONLY extract clear, specific facts that were explicitly stated or confirmed
- Do NOT extract:
  - General tax advice given by the assistant
  - Hypothetical scenarios
  - Questions asked but not answered
  - Information that was already known
- Focus on facts that would be useful in future conversations

Examples of good extractions:
- User says "I'm self-employed": {{"type": "fact", "category": "employment", "content": "Self-employed"}}
- User says "I work from home": {{"type": "fact", "category": "employment", "content": "Works from home"}}
- User decides "I'll do a backdoor Roth": {{"type": "decision", "category": "planning", "content": "Planning backdoor Roth conversion"}}

Return ONLY a JSON array. Return [] if nothing notable to extract.
"""


class MemoryManager:
    """Manages memory storage and retrieval for the tax agent."""

    def __init__(self, db: TaxDatabase):
        """
        Initialize the memory manager.

        Args:
            db: Database instance for storage
        """
        self.db = db

    def get_relevant_memories(
        self,
        tax_year: int | None = None,
        categories: list[MemoryCategory] | None = None,
    ) -> list[Memory]:
        """
        Get memories relevant to the current context.

        Args:
            tax_year: Filter by tax year (also includes year-agnostic memories)
            categories: Filter by specific categories

        Returns:
            List of relevant memories
        """
        if categories:
            # Query each category and combine
            memories = []
            for cat in categories:
                memories.extend(self.db.get_memories(category=cat, tax_year=tax_year))
            return memories
        else:
            return self.db.get_memories(tax_year=tax_year)

    def format_memories_for_context(self, memories: list[Memory]) -> str:
        """
        Format memories as a context string for the agent.

        Args:
            memories: List of memories to format

        Returns:
            Formatted string for injection into agent context
        """
        if not memories:
            return ""

        # Group by type
        by_type: dict[str, list[Memory]] = {}
        for mem in memories:
            mem_type = mem.memory_type
            if mem_type not in by_type:
                by_type[mem_type] = []
            by_type[mem_type].append(mem)

        lines = []

        # Facts first (most important)
        if MemoryType.FACT in by_type:
            facts = by_type[MemoryType.FACT]
            lines.append("**Known facts:**")
            for mem in facts:
                lines.append(f"- {mem.content}")

        # Preferences
        if MemoryType.PREFERENCE in by_type:
            prefs = by_type[MemoryType.PREFERENCE]
            lines.append("\n**Preferences:**")
            for mem in prefs:
                lines.append(f"- {mem.content}")

        # Insights
        if MemoryType.INSIGHT in by_type:
            insights = by_type[MemoryType.INSIGHT]
            lines.append("\n**Previous insights:**")
            for mem in insights[:5]:  # Limit to 5
                lines.append(f"- {mem.content}")

        # Decisions
        if MemoryType.DECISION in by_type:
            decisions = by_type[MemoryType.DECISION]
            lines.append("\n**Decisions made:**")
            for mem in decisions:
                lines.append(f"- {mem.content}")

        return "\n".join(lines)

    def extract_memories_from_response(
        self,
        user_message: str,
        response: str,
        agent=None,
    ) -> list[Memory]:
        """
        Use Claude to extract memory-worthy facts from a conversation exchange.

        Args:
            user_message: The user's message
            response: The assistant's response
            agent: Agent to use for extraction (uses legacy agent if not provided)

        Returns:
            List of Memory objects to store
        """
        # Skip extraction for very short exchanges or commands
        if len(user_message.strip()) < 10 or user_message.strip().startswith("/"):
            return []

        try:
            # Get agent for extraction
            if agent is None:
                from tax_agent.agent import get_agent
                agent = get_agent()

            prompt = EXTRACTION_PROMPT.format(
                user_message=user_message[:1000],  # Limit input size
                response=response[:1500],
            )

            result = agent._call(
                system="You are a fact extraction assistant. Extract structured facts from conversations. Return only valid JSON.",
                user_message=prompt,
                max_tokens=500,
            )

            # Parse JSON response
            # Handle markdown code blocks
            result = result.strip()
            if result.startswith("```"):
                # Remove code block markers
                lines = result.split("\n")
                result = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

            facts = json.loads(result)

            if not isinstance(facts, list):
                return []

            memories = []
            for fact in facts:
                if not isinstance(fact, dict):
                    continue

                try:
                    memory_type = MemoryType(fact.get("type", "fact"))
                    category = MemoryCategory(fact.get("category", "other"))
                    content = fact.get("content", "").strip()

                    if not content or len(content) < 3:
                        continue

                    memory = Memory(
                        id=str(uuid.uuid4()),
                        memory_type=memory_type,
                        category=category,
                        content=content,
                        tax_year=None,  # Auto-extracted are typically year-agnostic
                        confidence=0.8,  # Auto-extracted has slightly lower confidence
                        source="auto",
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                    )
                    memories.append(memory)
                except (ValueError, KeyError) as e:
                    logger.debug(f"Skipping invalid fact: {e}")
                    continue

            return memories

        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse extraction response: {e}")
            return []
        except Exception as e:
            logger.debug(f"Memory extraction failed: {e}")
            return []

    def add_memory(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        category: MemoryCategory = MemoryCategory.OTHER,
        tax_year: int | None = None,
    ) -> Memory:
        """
        Manually add a memory.

        Args:
            content: The memory content
            memory_type: Type of memory
            category: Category for organization
            tax_year: Optional tax year (None for year-agnostic)

        Returns:
            The created Memory object
        """
        memory = Memory(
            id=str(uuid.uuid4()),
            memory_type=memory_type,
            category=category,
            content=content,
            tax_year=tax_year,
            confidence=1.0,  # Manually added has full confidence
            source="manual",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        self.db.save_memory(memory)
        return memory

    def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        return self.db.delete_memory(memory_id)

    def clear_all_memories(self) -> int:
        """Clear all memories. Returns count of deleted memories."""
        return self.db.clear_memories()

    def get_all_memories(self) -> list[Memory]:
        """Get all stored memories."""
        return self.db.get_all_memories()


# Convenience function
def get_memory_manager() -> MemoryManager:
    """Get a memory manager instance with the default database."""
    from tax_agent.storage.database import get_database
    return MemoryManager(get_database())

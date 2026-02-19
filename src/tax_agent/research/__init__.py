"""Tax research module for verifying current tax code."""

from tax_agent.research.tax_researcher import (
    TaxResearcher,
    research_tax_topic,
    verify_current_limits,
)
from tax_agent.research.web_search import BraveSearchClient, BraveSearchError

__all__ = [
    "TaxResearcher",
    "research_tax_topic",
    "verify_current_limits",
    "BraveSearchClient",
    "BraveSearchError",
]

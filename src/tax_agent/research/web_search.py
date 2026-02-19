"""Web search client using Brave Search API for tax research."""

import json
import logging
import os
import time
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# Brave Search API endpoint
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

# Rate limiting: Brave free tier allows 1 req/sec, 2000/month
RATE_LIMIT_INTERVAL = 1.1  # seconds between requests


class BraveSearchError(Exception):
    """Raised when Brave Search API returns an error."""


class BraveSearchClient:
    """
    Client for the Brave Search API, focused on tax research queries.

    Handles API authentication, rate limiting, and result formatting.
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key or self._get_api_key()
        self._last_request_time = 0.0

        if not self._api_key:
            raise BraveSearchError(
                "Brave Search API key not configured. "
                "Set BRAVE_API_KEY environment variable or run: tax-agent config set-brave-key"
            )

    @staticmethod
    def _get_api_key() -> str | None:
        """Get API key from environment or keyring."""
        env_key = os.environ.get("BRAVE_API_KEY")
        if env_key:
            return env_key
        try:
            from tax_agent.config import get_config
            return get_config().get_brave_api_key()
        except Exception:
            return None

    @staticmethod
    def is_available() -> bool:
        """Check if Brave Search is configured and available."""
        if os.environ.get("BRAVE_API_KEY"):
            return True
        try:
            from tax_agent.config import get_config
            return get_config().get_brave_api_key() is not None
        except Exception:
            return False

    def _rate_limit(self) -> None:
        """Enforce rate limiting between API calls."""
        elapsed = time.time() - self._last_request_time
        if elapsed < RATE_LIMIT_INTERVAL:
            time.sleep(RATE_LIMIT_INTERVAL - elapsed)

    def search(self, query: str, count: int = 10) -> list[dict]:
        """
        Execute a web search query.

        Args:
            query: Search query string
            count: Number of results to return (max 20)

        Returns:
            List of search result dicts with keys: title, url, description
        """
        import httpx

        self._rate_limit()

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self._api_key,
        }

        params = {
            "q": query,
            "count": min(count, 20),
            "text_decorations": False,
            "search_lang": "en",
            "country": "us",
        }

        try:
            response = httpx.get(
                BRAVE_SEARCH_URL,
                headers=headers,
                params=params,
                timeout=15.0,
            )
            self._last_request_time = time.time()

            if response.status_code == 429:
                raise BraveSearchError("Rate limit exceeded. Please wait and try again.")
            elif response.status_code == 401:
                raise BraveSearchError("Invalid Brave Search API key.")
            elif response.status_code != 200:
                raise BraveSearchError(
                    f"Brave Search API error: {response.status_code} {response.text[:200]}"
                )

            data = response.json()
            results = []

            for item in data.get("web", {}).get("results", []):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("description", ""),
                })

            return results

        except httpx.TimeoutException:
            raise BraveSearchError("Brave Search request timed out.")
        except httpx.RequestError as e:
            raise BraveSearchError(f"Network error during search: {e}")

    def search_irs(self, topic: str, tax_year: int | None = None) -> list[dict]:
        """Search specifically on IRS.gov for official guidance."""
        year_str = f" {tax_year}" if tax_year else ""
        query = f"site:irs.gov {topic}{year_str}"
        return self.search(query, count=10)

    def search_tax_topic(self, topic: str, tax_year: int | None = None) -> list[dict]:
        """Search for a tax topic across authoritative sources."""
        year_str = f" {tax_year}" if tax_year else ""
        query = f"{topic}{year_str} IRS tax rules"
        return self.search(query, count=10)

    def search_state_tax(self, state: str, topic: str, tax_year: int | None = None) -> list[dict]:
        """Search for state-specific tax information."""
        year_str = f" {tax_year}" if tax_year else ""
        query = f"{state} state tax {topic}{year_str}"
        return self.search(query, count=10)

    def search_tax_law_changes(self, tax_year: int) -> list[dict]:
        """Search for recent tax law changes."""
        query = f"tax law changes {tax_year} IRS new rules"
        return self.search(query, count=15)

    def format_results_for_context(self, results: list[dict], max_results: int = 8) -> str:
        """
        Format search results as context for Claude analysis.

        Args:
            results: List of search result dicts
            max_results: Maximum results to include

        Returns:
            Formatted string for use as AI context
        """
        if not results:
            return "No web search results found."

        lines = ["## Web Search Results\n"]
        for i, result in enumerate(results[:max_results], 1):
            lines.append(f"### Result {i}: {result['title']}")
            lines.append(f"**Source:** {result['url']}")
            lines.append(f"{result['description']}\n")

        return "\n".join(lines)

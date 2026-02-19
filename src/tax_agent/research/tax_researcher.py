"""Tax code research module - uses Brave Search + Claude for current tax rules and updates."""

import json
import logging

from tax_agent.agent import get_agent
from tax_agent.config import get_config

logger = logging.getLogger(__name__)


def _get_search_client():
    """Get a BraveSearchClient if available, otherwise None."""
    try:
        from tax_agent.research.web_search import BraveSearchClient
        if BraveSearchClient.is_available():
            return BraveSearchClient()
    except Exception as e:
        logger.debug(f"Web search not available: {e}")
    return None


def _parse_json_response(response: str) -> dict:
    """Parse a JSON response, stripping markdown fences if present."""
    response = response.strip()
    if response.startswith("```"):
        response = response.split("```")[1]
        if response.startswith("json"):
            response = response[4:]
    return json.loads(response)


class TaxResearcher:
    """
    Researches current tax code, IRS guidance, and recent changes.

    When Brave Search is configured, performs real web searches and feeds
    the results to Claude for analysis. Falls back to Claude's training
    data when web search is unavailable.
    """

    def __init__(self, tax_year: int | None = None):
        config = get_config()
        self.tax_year = tax_year or config.tax_year
        self.agent = get_agent()
        self._search = _get_search_client()

    @property
    def has_web_search(self) -> bool:
        """Whether real web search is available."""
        return self._search is not None

    def research_current_limits(self) -> dict:
        """
        Research current tax year contribution limits and thresholds.

        Returns:
            Dictionary with current limits from IRS sources
        """
        web_context = ""
        if self._search:
            logger.info("Searching web for current IRS limits...")
            results = []
            results.extend(self._search.search_irs(
                "contribution limits standard deduction", self.tax_year
            ))
            results.extend(self._search.search_irs(
                "401k IRA HSA limits", self.tax_year
            ))
            web_context = self._search.format_results_for_context(results, max_results=10)

        system = f"""You are a tax research assistant. Provide the CURRENT official IRS limits for tax year {self.tax_year}.

{"Use the web search results below to verify and supplement your knowledge:" if web_context else "Use your knowledge of official IRS publications:"}

{web_context}

Return accurate, sourced information for:
1. Standard deduction amounts (single, MFJ, HoH)
2. 401(k) contribution limits (regular and catch-up)
3. IRA contribution limits (regular and catch-up)
4. HSA contribution limits (individual and family)
5. FICA wage base (Social Security)
6. Tax bracket thresholds
7. Capital gains rate thresholds
8. Child Tax Credit amounts
9. Earned Income Credit limits
10. SALT deduction cap

For EACH item, provide:
- The current limit/amount
- The source (IRS publication number or announcement)
- Whether it changed from the prior year

Return as JSON with structure:
{{
  "tax_year": {self.tax_year},
  "web_search_used": {"true" if web_context else "false"},
  "limits": {{
    "standard_deduction_single": {{"amount": 14600, "source": "Rev. Proc. 2023-34", "changed": true}},
    ...
  }},
  "recent_changes": ["Description of any notable changes"],
  "sources_checked": ["IRS.gov", "Rev. Proc. 2023-34", ...]
}}

Only return the JSON object."""

        user_message = f"Research the current IRS limits and thresholds for tax year {self.tax_year}."

        response = self.agent._call(system, user_message, max_tokens=3000)

        try:
            return _parse_json_response(response)
        except json.JSONDecodeError:
            return {"error": "Failed to parse research results", "raw": response}

    def research_topic(self, topic: str) -> str:
        """
        Research a specific tax topic.

        Args:
            topic: Tax topic to research (e.g., "RSU taxation", "wash sale rules")

        Returns:
            Research summary with sources
        """
        web_context = ""
        if self._search:
            logger.info(f"Searching web for: {topic}")
            results = self._search.search_tax_topic(topic, self.tax_year)
            irs_results = self._search.search_irs(topic, self.tax_year)
            all_results = results + irs_results
            # Deduplicate by URL
            seen_urls = set()
            unique = []
            for r in all_results:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    unique.append(r)
            web_context = self._search.format_results_for_context(unique, max_results=10)

        system = f"""You are an expert tax researcher for tax year {self.tax_year}.

{"Use the web search results below to provide current, accurate information:" if web_context else "Use your knowledge of tax law:"}

{web_context}

Research the requested topic thoroughly. Your response should include:
1. Current rules and regulations
2. Recent IRS guidance or court cases
3. Common misconceptions
4. Practical implications
5. Specific dollar amounts or thresholds if applicable

Always cite your sources:
- IRS Publications (e.g., Pub 550, Pub 17)
- Revenue Procedures
- Treasury Regulations
- Recent Tax Court cases if relevant
{"- Web sources from the search results above" if web_context else ""}

Be specific and accurate. If something is uncertain or varies by situation, say so."""

        user_message = f"""Research this tax topic: {topic}

Provide current, accurate information with sources. Focus on practical application for individual taxpayers."""

        return self.agent._call(system, user_message, max_tokens=2000)

    def check_for_law_changes(self) -> str:
        """
        Check for recent tax law changes that affect the current tax year.

        Returns:
            Summary of recent changes
        """
        web_context = ""
        if self._search:
            logger.info("Searching web for tax law changes...")
            results = self._search.search_tax_law_changes(self.tax_year)
            web_context = self._search.format_results_for_context(results, max_results=10)

        system = f"""You are a tax law update specialist. Identify tax law changes affecting tax year {self.tax_year}.

{"Use the web search results below for current information:" if web_context else "Use your knowledge of recent tax legislation:"}

{web_context}

Check for:
1. New legislation passed (e.g., Inflation Reduction Act provisions taking effect)
2. IRS rule changes or new guidance
3. Expired provisions that weren't extended
4. Phase-ins or phase-outs of existing provisions
5. Court decisions affecting tax treatment
6. State tax changes (major states)

For each change, provide:
- What changed
- Effective date
- Who is affected
- Dollar impact if quantifiable
- Source/reference

Focus on changes that affect typical W-2 employees and investors."""

        user_message = f"""What are the key tax law changes for {self.tax_year} compared to the prior year?

Focus on changes that would affect:
- Individual taxpayers
- Investment income
- Retirement contributions
- Credits and deductions
- Stock compensation"""

        return self.agent._call(system, user_message, max_tokens=2000)

    def verify_state_rules(self, state: str) -> dict:
        """
        Verify current state tax rules.

        Args:
            state: State code (e.g., "CA", "NY")

        Returns:
            State tax information
        """
        web_context = ""
        if self._search:
            logger.info(f"Searching web for {state} tax rules...")
            results = self._search.search_state_tax(state, "income tax rates brackets", self.tax_year)
            web_context = self._search.format_results_for_context(results, max_results=8)

        system = f"""You are a state tax expert. Research the current tax rules for {state} for tax year {self.tax_year}.

{"Use the web search results below for current information:" if web_context else "Use your knowledge of state tax law:"}

{web_context}

Include:
1. Income tax brackets and rates
2. Standard deduction (if any)
3. Treatment of retirement income
4. Capital gains treatment (same as ordinary or preferential)
5. Notable deductions/credits unique to this state
6. Conformity to federal tax code
7. Remote work rules
8. Any recent changes

Return as JSON:
{{
  "state": "{state}",
  "tax_year": {self.tax_year},
  "web_search_used": {"true" if web_context else "false"},
  "has_income_tax": true,
  "top_rate": 0.00,
  "brackets": [...],
  "standard_deduction": {{...}},
  "capital_gains_treatment": "ordinary or preferential",
  "notable_deductions": [...],
  "notable_credits": [...],
  "federal_conformity": "full, partial, or description",
  "recent_changes": [...],
  "sources": [...]
}}

Only return the JSON object."""

        user_message = f"Research current tax rules for {state} for tax year {self.tax_year}."

        response = self.agent._call(system, user_message, max_tokens=2000)

        try:
            return _parse_json_response(response)
        except json.JSONDecodeError:
            return {"error": "Failed to parse state research", "raw": response}


def research_tax_topic(topic: str, tax_year: int | None = None) -> str:
    """Convenience function to research a tax topic."""
    researcher = TaxResearcher(tax_year)
    return researcher.research_topic(topic)


def verify_current_limits(tax_year: int | None = None) -> dict:
    """Convenience function to verify current IRS limits."""
    researcher = TaxResearcher(tax_year)
    return researcher.research_current_limits()

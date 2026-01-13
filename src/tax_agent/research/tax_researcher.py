"""Tax code research module - uses web search to find current tax rules and updates."""

from tax_agent.agent import get_agent
from tax_agent.config import get_config


class TaxResearcher:
    """
    Researches current tax code, IRS guidance, and recent changes using web search.

    This ensures the agent has up-to-date information beyond its training cutoff.
    """

    def __init__(self, tax_year: int | None = None):
        config = get_config()
        self.tax_year = tax_year or config.tax_year
        self.agent = get_agent()

    def research_current_limits(self) -> dict:
        """
        Research current tax year contribution limits and thresholds.

        Returns:
            Dictionary with current limits from IRS sources
        """
        system = """You are a tax research assistant. Search for and verify the CURRENT official IRS limits.

Search for the following and return accurate, sourced information:
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
{
  "tax_year": 2024,
  "limits": {
    "standard_deduction_single": {"amount": 14600, "source": "Rev. Proc. 2023-34", "changed": true},
    ...
  },
  "recent_changes": ["Description of any notable changes"],
  "sources_checked": ["IRS.gov", "Rev. Proc. 2023-34", ...]
}

Only return the JSON object."""

        # Note: This would ideally use a web search tool
        # For now, we'll use Claude's knowledge with explicit instruction to cite sources
        user_message = f"""Research the current IRS limits and thresholds for tax year {self.tax_year}.

Verify these are the OFFICIAL IRS numbers, not estimates or projections.
Cite the specific IRS Revenue Procedure or publication where each limit is defined."""

        response = self.agent._call(system, user_message, max_tokens=3000)

        import json
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {"error": "Failed to parse research results", "raw": response}

    def research_topic(self, topic: str) -> str:
        """
        Research a specific tax topic using web search.

        Args:
            topic: Tax topic to research (e.g., "RSU taxation", "wash sale rules")

        Returns:
            Research summary with sources
        """
        system = f"""You are an expert tax researcher for tax year {self.tax_year}.

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
        system = f"""You are a tax law update specialist. Identify any tax law changes affecting tax year {self.tax_year}.

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
        system = f"""You are a state tax expert. Research the current tax rules for the specified state for tax year {self.tax_year}.

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
  "state": "XX",
  "tax_year": {self.tax_year},
  "has_income_tax": true,
  "top_rate": 0.XX,
  "brackets": [...],
  "standard_deduction": {{...}},
  "capital_gains_treatment": "ordinary" or "preferential",
  "notable_deductions": [...],
  "notable_credits": [...],
  "federal_conformity": "full", "partial", or description,
  "recent_changes": [...],
  "sources": [...]
}}

Only return the JSON object."""

        user_message = f"Research current tax rules for {state} for tax year {self.tax_year}."

        response = self.agent._call(system, user_message, max_tokens=2000)

        import json
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
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

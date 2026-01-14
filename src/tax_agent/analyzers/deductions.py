"""Deduction finder and tax optimization module with user interview."""

from pathlib import Path
from typing import Any

from tax_agent.agent import get_agent
from tax_agent.config import get_config
from tax_agent.models.documents import DocumentType, TaxDocument
from tax_agent.models.taxpayer import FilingStatus, TaxpayerProfile
from tax_agent.storage.database import get_database
from tax_agent.utils import get_enum_value


def _get_sdk_agent():
    """Get SDK agent if available and enabled."""
    config = get_config()
    if config.use_agent_sdk:
        from tax_agent.agent_sdk import get_sdk_agent, sdk_available
        if sdk_available():
            return get_sdk_agent()
    return None


class TaxOptimizer:
    """
    Claude-powered tax optimization with user interview capability.

    Identifies tax-saving opportunities through intelligent questioning
    and analysis of the user's situation.

    When Agent SDK is enabled, can use tools to:
    - Read source documents for verification
    - Look up current IRS rules and limits
    - Calculate tax scenarios with built-in tax tools
    """

    def __init__(self, tax_year: int | None = None):
        """Initialize the optimizer."""
        config = get_config()
        self.tax_year = tax_year or config.tax_year
        self.db = get_database()
        self.config = config
        self._agent = None
        self._sdk_agent = None

    @property
    def agent(self):
        """Get legacy agent (lazy initialization)."""
        if self._agent is None:
            self._agent = get_agent()
        return self._agent

    @property
    def sdk_agent(self):
        """Get SDK agent if enabled (lazy initialization)."""
        if self._sdk_agent is None and self.config.use_agent_sdk:
            self._sdk_agent = _get_sdk_agent()
        return self._sdk_agent

    def _use_sdk(self) -> bool:
        """Check if SDK should be used."""
        return self.config.use_agent_sdk and self.sdk_agent is not None

    def get_interview_questions(
        self,
        documents: list[TaxDocument] | None = None,
        previous_answers: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Generate interview questions based on documents and previous answers.

        Uses Claude to intelligently determine what questions to ask
        based on the user's tax situation.

        Args:
            documents: List of collected documents
            previous_answers: Previously answered questions

        Returns:
            List of question dictionaries with 'id', 'question', 'type', 'options'
        """
        if documents is None:
            documents = self.db.get_documents(tax_year=self.tax_year)

        # Build context for Claude
        doc_summary = self._build_document_summary(documents)
        answers_summary = self._format_previous_answers(previous_answers or {})

        system = """You are a tax advisor conducting an interview to find tax-saving opportunities.

Based on the taxpayer's documents and any previous answers, generate 3-5 relevant questions to identify:
1. Deductions they might be eligible for
2. Credits they could claim
3. Tax-advantaged accounts they could use
4. Investment tax optimization opportunities
5. Life events that affect taxes (marriage, children, home purchase, etc.)

Pay special attention to:
- RSU and stock compensation situations (vesting, sales, tax withholding)
- Equity compensation from tech companies (ISOs, NSOs, ESPP)
- Home office deductions for remote workers
- State tax implications
- Retirement contributions
- Healthcare costs and HSA eligibility
- Education expenses
- Charitable giving

Return a JSON array of questions. Each question should have:
- "id": Unique identifier
- "question": The question text
- "type": "yes_no", "number", "text", "select", or "multi_select"
- "options": Array of options (for select/multi_select types)
- "relevance": Brief explanation of why this question matters for taxes

Only ask questions that are relevant given the documents and previous answers.
Focus on high-impact opportunities first.

Return ONLY the JSON array, no other text."""

        user_message = f"""Collected Documents:
{doc_summary}

Previous Answers:
{answers_summary}

Generate relevant interview questions to identify tax-saving opportunities."""

        response = self.agent._call(system, user_message)

        # Parse JSON response
        import json
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            # Return default questions if parsing fails
            return self._get_default_questions(documents)

    def _get_default_questions(self, documents: list[TaxDocument]) -> list[dict[str, Any]]:
        """Return default interview questions."""
        questions = [
            {
                "id": "home_owner",
                "question": "Do you own your home?",
                "type": "yes_no",
                "relevance": "Homeowners may deduct mortgage interest and property taxes",
            },
            {
                "id": "retirement_contrib",
                "question": "Did you contribute to retirement accounts (401k, IRA)?",
                "type": "yes_no",
                "relevance": "Retirement contributions may be tax-deductible",
            },
            {
                "id": "health_insurance",
                "question": "What type of health insurance do you have?",
                "type": "select",
                "options": ["Employer-provided", "Marketplace/ACA", "HSA-eligible HDHP", "Medicare", "None"],
                "relevance": "HSA contributions are tax-deductible; marketplace may qualify for credits",
            },
            {
                "id": "work_from_home",
                "question": "Did you work from home this year?",
                "type": "yes_no",
                "relevance": "Self-employed can deduct home office expenses",
            },
            {
                "id": "stock_compensation",
                "question": "Did you receive stock compensation (RSUs, ISOs, ESPP)?",
                "type": "multi_select",
                "options": ["RSUs (Restricted Stock Units)", "ISOs (Incentive Stock Options)", "NSOs (Non-qualified Stock Options)", "ESPP (Employee Stock Purchase Plan)", "None"],
                "relevance": "Stock compensation has complex tax implications",
            },
        ]
        return questions

    def analyze_stock_compensation(
        self,
        compensation_type: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Analyze stock compensation for tax implications.

        Args:
            compensation_type: Type of compensation (RSU, ISO, NSO, ESPP)
            details: Details about the compensation

        Returns:
            Analysis with tax implications and optimization suggestions
        """
        system = """You are an expert in equity compensation taxation. Analyze the stock compensation situation and provide:

1. Tax Treatment: How this type of compensation is taxed
2. Timing Considerations: When taxes are due (vesting, exercise, sale)
3. Withholding Issues: Common withholding gaps with RSUs/options
4. Optimization Strategies: Legal ways to minimize tax burden
5. AMT Implications: Alternative Minimum Tax considerations
6. State Tax: State-specific considerations if mentioned
7. Wash Sale Rules: Applicability and how to avoid issues
8. 83(b) Election: If applicable, discuss pros/cons

For RSUs specifically:
- Taxes are due at vesting (ordinary income)
- Employers often withhold at flat rate (22%) which may be insufficient
- Cost basis is FMV at vesting
- Holding period for capital gains starts at vesting

For ISOs specifically:
- No regular tax at exercise (but AMT implications)
- Qualifying disposition requires 2-year/1-year holding
- Disqualifying disposition taxed as ordinary income

Return a structured JSON response with:
- "tax_treatment": Explanation of how it's taxed
- "immediate_actions": Things to do now
- "estimated_tax_impact": Rough estimate if possible
- "optimization_tips": Specific strategies
- "warnings": Things to watch out for
- "questions_needed": Additional info needed for better analysis

Only return the JSON object."""

        user_message = f"""Stock Compensation Analysis Request:

Type: {compensation_type}
Details: {details}

Provide a comprehensive tax analysis."""

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
            return {"error": "Failed to parse analysis", "raw_response": response}

    def find_deductions(
        self,
        documents: list[TaxDocument] | None = None,
        interview_answers: dict[str, Any] | None = None,
        taxpayer: TaxpayerProfile | None = None,
        use_sdk: bool | None = None,
    ) -> dict[str, Any]:
        """
        Find applicable deductions based on documents and interview.

        When Agent SDK is enabled, this method can:
        - Use web tools to verify current IRS limits
        - Read source documents to verify amounts
        - Use tax calculation tools for accurate estimates

        Args:
            documents: Collected tax documents
            interview_answers: Answers from user interview
            taxpayer: Taxpayer profile
            use_sdk: Override config.use_agent_sdk (None = use config)

        Returns:
            Dictionary with found deductions and recommendations
        """
        if documents is None:
            documents = self.db.get_documents(tax_year=self.tax_year)

        doc_summary = self._build_document_summary(documents)
        answers_summary = self._format_previous_answers(interview_answers or {})
        profile_summary = self._format_taxpayer_profile(taxpayer)

        # Get source directory for SDK tool access
        source_dir = None
        for doc in documents:
            if doc.file_path:
                source_dir = Path(doc.file_path).parent
                break

        # Check if we should use SDK
        should_use_sdk = use_sdk if use_sdk is not None else self._use_sdk()

        if should_use_sdk and self.sdk_agent:
            return self._find_deductions_with_sdk(
                doc_summary, answers_summary, profile_summary, source_dir
            )

        system = """You are an AGGRESSIVE tax optimization expert. Your mission is to find EVERY POSSIBLE way to LEGALLY reduce this taxpayer's tax burden. Be exhaustive and creative.

## MANDATORY ANALYSIS AREAS:

### 1. STANDARD VS ITEMIZED DEEP DIVE
- Calculate BOTH scenarios with actual numbers
- Consider "bunching" strategies (alternate years)
- SALT cap workarounds (pass-through entity elections)
- When itemizing makes sense even if slightly lower

### 2. ABOVE-THE-LINE DEDUCTIONS (These reduce AGI - VERY valuable!)
- Traditional IRA contributions (even partial deductibility helps)
- HSA contributions (triple tax advantage - MAXIMIZE)
- Student loan interest ($2,500 max)
- Self-employment tax deduction (50%)
- Self-employed health insurance
- Educator expenses ($300)
- Moving expenses (military only)

### 3. ITEMIZED DEDUCTIONS - MAXIMIZE EACH:
- **SALT**: Capped at $10K but MUST claim full amount
  - State income tax OR sales tax (whichever higher)
  - Property taxes
  - Consider S-Corp election for SALT workaround
- **Mortgage Interest**: Is it fully deductible?
- **Charitable**: Did they donate appreciated stock? Donor-advised funds?
  - Bunching strategy for alternate years
  - Qualified charitable distributions from IRA if 70.5+
- **Medical**: Only over 7.5% AGI floor, but add up EVERYTHING
  - Insurance premiums, copays, prescriptions, mileage, equipment

### 4. TAX CREDITS - Often worth MORE than deductions!
- **Child Tax Credit**: $2,000/child, partially refundable
- **Child & Dependent Care**: Up to $3,000-$6,000 of expenses
- **Earned Income Credit**: Check eligibility at ALL income levels
- **Education Credits**:
  - AOTC: $2,500 (40% refundable) - BETTER for undergrad
  - LLC: $2,000 non-refundable - for grad school, part-time
- **Retirement Saver's Credit**: Up to 50% of contributions
- **Residential Energy Credits**: Solar, windows, HVAC, EV chargers
- **EV Credit**: Up to $7,500 for new, $4,000 used
- **Foreign Tax Credit**: For international investments

### 5. RETIREMENT CONTRIBUTIONS - TAX-ADVANTAGED SAVINGS
- 401(k): Max $23,000 + $7,500 catch-up (50+)
- IRA: Max $7,000 + $1,000 catch-up
- Backdoor Roth: If income too high for direct Roth
- Mega Backdoor Roth: If plan allows after-tax contributions
- SEP-IRA/Solo 401(k): If any self-employment income

### 6. INVESTMENT TAX OPTIMIZATION
- Tax-loss harvesting: Offset gains with losses
- Asset location: Tax-inefficient investments in tax-advantaged accounts
- Qualified dividends: Ensure proper classification (0%/15%/20% rates)
- Long-term vs short-term: Hold 1+ year for better rates
- Net Investment Income Tax: 3.8% on investment income above thresholds

### 7. BUSINESS/SELF-EMPLOYMENT DEDUCTIONS
- Home office (simplified: $5/sq ft up to 300 sq ft)
- Business mileage (67 cents/mile for 2024)
- Equipment and supplies
- Professional development
- Business portion of phone/internet
- Qualified Business Income deduction (20% of QBI)

### 8. LESS COMMON BUT VALUABLE
- Alimony (pre-2019 divorces)
- Gambling losses (up to winnings)
- Casualty losses (federally declared disasters)
- Jury duty pay given to employer
- Work-related moving expenses (military)

## OUTPUT REQUIREMENTS:
For EACH deduction/credit found, provide:
- **Name**: Specific deduction or credit
- **Estimated Value**: Dollar amount of tax savings (not just deduction amount)
- **Eligibility**: Why they likely qualify
- **Action Required**: Specific steps to claim
- **Documentation**: What records are needed
- **Confidence**: High/Medium/Low

Return JSON with:
- "recommended_deductions": [{name, estimated_value, action_needed, documentation}]
- "recommended_credits": [{name, estimated_value, eligibility, action_needed}]
- "standard_vs_itemized": {recommendation, standard_amount, itemized_amount, reasoning}
- "estimated_total_savings": number (sum of ALL tax savings)
- "action_items": ["Specific step 1", "Specific step 2", ...]
- "planning_tips": ["Next year tip 1", ...]
- "warnings": ["Audit risk or concern 1", ...]
- "missed_opportunities": ["Prior year item 1", ...] (if amendable)

Only return the JSON object. Be AGGRESSIVE - find savings others would miss."""

        user_message = f"""Tax Optimization Analysis:

Documents:
{doc_summary}

Interview Answers:
{answers_summary}

Taxpayer Profile:
{profile_summary}

Find all applicable deductions and credits."""

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
            return {"error": "Failed to parse deductions", "raw_response": response}

    def _find_deductions_with_sdk(
        self,
        doc_summary: str,
        answers_summary: str,
        profile_summary: str,
        source_dir: Path | None,
    ) -> dict[str, Any]:
        """
        Find deductions using Agent SDK with tool access.

        The SDK agent can verify amounts against source documents and
        look up current IRS limits via web tools.
        """
        prompt = f"""Find ALL applicable tax deductions and credits for this taxpayer.

You have access to tools to:
- Read source documents to verify amounts
- Search the web for current IRS limits and rules
- Calculate tax scenarios

Be AGGRESSIVE - find every legal way to reduce their tax burden.

Documents:
{doc_summary}

Interview Answers:
{answers_summary}

Taxpayer Profile:
{profile_summary}

For EACH opportunity found, provide:
- Name and description
- Estimated tax savings (not just deduction amount)
- Action required to claim
- Documentation needed

Return a JSON object with:
- "recommended_deductions": [{{name, estimated_value, action_needed, documentation}}]
- "recommended_credits": [{{name, estimated_value, eligibility, action_needed}}]
- "standard_vs_itemized": {{recommendation, reasoning}}
- "estimated_total_savings": number
- "action_items": ["step1", "step2", ...]
- "warnings": ["concern1", ...]"""

        try:
            result = self.sdk_agent.interactive_query(
                prompt,
                context={"tax_year": self.tax_year},
                source_dir=source_dir,
            )

            # Parse JSON from response
            import json
            result = result.strip()
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]

            # Find JSON object in response
            json_start = result.find("{")
            json_end = result.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(result[json_start:json_end])

            return {"error": "No JSON found in SDK response", "raw_response": result}
        except Exception as e:
            # Fall back to legacy method on error
            import logging
            logging.warning(f"SDK deduction finding failed: {e}")
            return {"error": str(e), "fallback": "Use find_deductions with use_sdk=False"}

    def _build_document_summary(self, documents: list[TaxDocument]) -> str:
        """Build a summary of documents for Claude."""
        if not documents:
            return "No documents collected yet."

        lines = []
        for doc in documents:
            line = f"- {get_enum_value(doc.document_type)} from {doc.issuer_name}"
            data = doc.extracted_data

            if doc.document_type == DocumentType.W2:
                wages = data.get("box_1", 0) or 0
                withheld = data.get("box_2", 0) or 0
                state_wages = data.get("box_16", 0) or 0
                box12 = data.get("box_12_codes", [])
                line += f": Wages ${wages:,.2f}, Federal withheld ${withheld:,.2f}"
                if box12:
                    line += f", Box 12 codes: {box12}"

            elif doc.document_type == DocumentType.FORM_1099_B:
                summary = data.get("summary", {})
                transactions = data.get("transactions", [])
                proceeds = summary.get("total_proceeds", 0) or 0
                st_gain = summary.get("short_term_gain_loss", 0) or 0
                lt_gain = summary.get("long_term_gain_loss", 0) or 0
                line += f": Proceeds ${proceeds:,.2f}, ST gain/loss ${st_gain:,.2f}, LT gain/loss ${lt_gain:,.2f}"
                if transactions:
                    line += f" ({len(transactions)} transactions)"

            elif doc.document_type == DocumentType.FORM_1099_INT:
                interest = data.get("box_1", 0) or 0
                line += f": Interest ${interest:,.2f}"

            elif doc.document_type == DocumentType.FORM_1099_DIV:
                ordinary = data.get("box_1a", 0) or 0
                qualified = data.get("box_1b", 0) or 0
                line += f": Ordinary ${ordinary:,.2f}, Qualified ${qualified:,.2f}"

            lines.append(line)

        return "\n".join(lines)

    def _format_previous_answers(self, answers: dict[str, Any]) -> str:
        """Format interview answers for Claude."""
        if not answers:
            return "No interview completed yet."

        lines = []
        for key, value in answers.items():
            lines.append(f"- {key}: {value}")
        return "\n".join(lines)

    def _format_taxpayer_profile(self, profile: TaxpayerProfile | None) -> str:
        """Format taxpayer profile for Claude."""
        if not profile:
            config = get_config()
            return f"""Filing Status: {config.get('filing_status', 'Not specified')}
State: {config.state or 'Not specified'}"""

        return f"""Filing Status: {get_enum_value(profile.filing_status)}
State: {profile.state}
Dependents: {profile.num_dependents}
Age 65+: {profile.is_65_or_older}
Self-employed: {profile.is_self_employed}
Has HSA: {profile.has_hsa}
Foreign Accounts: {profile.has_foreign_accounts}"""


def run_tax_interview(tax_year: int | None = None) -> dict[str, Any]:
    """
    Convenience function to run interactive tax interview.

    Returns collected answers.
    """
    optimizer = TaxOptimizer(tax_year)
    answers: dict[str, Any] = {}

    questions = optimizer.get_interview_questions()

    print("\n=== Tax Optimization Interview ===\n")
    print("Answer these questions to help identify tax-saving opportunities.\n")

    for q in questions:
        print(f"\n{q['question']}")
        if "relevance" in q:
            print(f"  (Why: {q['relevance']})")

        if q["type"] == "yes_no":
            answer = input("  [y/n]: ").strip().lower()
            answers[q["id"]] = answer in ("y", "yes", "true", "1")

        elif q["type"] == "number":
            answer = input("  Enter amount: $").strip()
            try:
                answers[q["id"]] = float(answer.replace(",", ""))
            except ValueError:
                answers[q["id"]] = 0

        elif q["type"] == "select":
            print("  Options:")
            for i, opt in enumerate(q.get("options", []), 1):
                print(f"    {i}. {opt}")
            answer = input("  Enter number: ").strip()
            try:
                idx = int(answer) - 1
                answers[q["id"]] = q["options"][idx]
            except (ValueError, IndexError):
                answers[q["id"]] = None

        elif q["type"] == "multi_select":
            print("  Options (enter numbers separated by commas):")
            for i, opt in enumerate(q.get("options", []), 1):
                print(f"    {i}. {opt}")
            answer = input("  Enter numbers: ").strip()
            try:
                indices = [int(x.strip()) - 1 for x in answer.split(",")]
                answers[q["id"]] = [q["options"][i] for i in indices if 0 <= i < len(q["options"])]
            except ValueError:
                answers[q["id"]] = []

        else:  # text
            answers[q["id"]] = input("  Answer: ").strip()

    return answers

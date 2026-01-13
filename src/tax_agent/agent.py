"""Claude agent for tax document analysis."""

from tax_agent.config import AI_PROVIDER_ANTHROPIC, AI_PROVIDER_AWS_BEDROCK, get_config

# Model mapping for different providers
# Anthropic API uses direct model IDs, Bedrock uses ARN-style IDs
ANTHROPIC_MODELS = {
    "claude-sonnet-4-5-20250514": "claude-sonnet-4-5-20250514",
    "claude-sonnet-4-20250514": "claude-sonnet-4-20250514",
    "claude-opus-4-20250514": "claude-opus-4-20250514",
}

BEDROCK_MODELS = {
    "claude-sonnet-4-5-20250514": "anthropic.claude-sonnet-4-5-20250514-v1:0",
    "claude-sonnet-4-20250514": "anthropic.claude-sonnet-4-20250514-v1:0",
    "claude-opus-4-20250514": "anthropic.claude-opus-4-20250514-v1:0",
}


class TaxAgent:
    """Claude-powered agent for tax document processing and analysis."""

    def __init__(self, model: str | None = None):
        """
        Initialize the tax agent.

        Supports both Anthropic API and AWS Bedrock as providers.

        Args:
            model: Claude model to use. Defaults to config setting.
        """
        config = get_config()
        self.provider = config.ai_provider
        self.config = config

        # Default to Claude Sonnet 4.5
        base_model = model or config.get("model", "claude-sonnet-4-5-20250514")

        if self.provider == AI_PROVIDER_AWS_BEDROCK:
            self._init_bedrock(base_model)
        else:
            self._init_anthropic(base_model)

    def _init_anthropic(self, base_model: str) -> None:
        """Initialize with Anthropic API."""
        from anthropic import Anthropic

        api_key = self.config.get_api_key()
        if not api_key:
            raise ValueError("Anthropic API key not configured. Run 'tax-agent init' first.")

        self.client = Anthropic(api_key=api_key)
        self.model = ANTHROPIC_MODELS.get(base_model, base_model)

    def _init_bedrock(self, base_model: str) -> None:
        """Initialize with AWS Bedrock."""
        import boto3
        from anthropic import AnthropicBedrock

        # Get AWS credentials - try keyring first, then fall back to environment/IAM
        access_key, secret_key = self.config.get_aws_credentials()
        region = self.config.aws_region

        if access_key and secret_key:
            # Use explicit credentials from keyring
            self.client = AnthropicBedrock(
                aws_access_key=access_key,
                aws_secret_key=secret_key,
                aws_region=region,
            )
        else:
            # Fall back to default AWS credential chain (env vars, IAM role, etc.)
            self.client = AnthropicBedrock(aws_region=region)

        self.model = BEDROCK_MODELS.get(base_model, f"anthropic.{base_model}-v1:0")

    def _call(
        self,
        system: str,
        user_message: str,
        max_tokens: int = 4096,
    ) -> str:
        """
        Make a call to the Claude API.

        Args:
            system: System prompt
            user_message: User message
            max_tokens: Maximum tokens in response

        Returns:
            Response text
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )

        return response.content[0].text

    def classify_document(self, text: str) -> dict:
        """
        Classify a tax document and identify its type.

        Args:
            text: Extracted text from the document

        Returns:
            Dictionary with document classification
        """
        system = """You are a tax document classifier. Analyze the provided text and identify what type of tax document it is.

Respond with a JSON object containing:
- document_type: One of: W2, 1099_INT, 1099_DIV, 1099_B, 1099_NEC, 1099_MISC, 1099_R, 1099_G, 1099_K, 1098, 1098_T, 1098_E, 5498, K1, UNKNOWN
- confidence: A number from 0 to 1 indicating your confidence
- issuer_name: The name of the entity that issued this document (employer, bank, etc.)
- tax_year: The tax year this document is for (e.g., 2024)
- reasoning: Brief explanation of why you classified it this way

Only respond with the JSON object, no other text."""

        user_message = f"Classify this tax document:\n\n{text[:8000]}"  # Limit text length

        response = self._call(system, user_message)

        # Parse JSON response
        import json
        try:
            # Clean up response in case of markdown code blocks
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "document_type": "UNKNOWN",
                "confidence": 0.0,
                "issuer_name": "Unknown",
                "tax_year": None,
                "reasoning": "Failed to parse classification response",
            }

    def extract_w2_data(self, text: str) -> dict:
        """Extract structured data from a W-2 form."""
        system = """You are a tax document data extractor specializing in W-2 forms.

Extract all relevant data from the W-2 and return a JSON object with these fields:
- employer_name: Name of the employer
- employer_ein: Employer EIN (XX-XXXXXXX format)
- employer_address: Full employer address
- employee_ssn_last4: Last 4 digits of employee SSN only
- employee_name: Employee name
- box_1: Wages, tips, other compensation (number)
- box_2: Federal income tax withheld (number)
- box_3: Social security wages (number)
- box_4: Social security tax withheld (number)
- box_5: Medicare wages and tips (number)
- box_6: Medicare tax withheld (number)
- box_7: Social security tips (number or null)
- box_10: Dependent care benefits (number or null)
- box_12_codes: Array of box 12 codes and amounts, e.g., [{"code": "D", "amount": 1000}]
- box_13_statutory: Boolean for statutory employee
- box_13_retirement: Boolean for retirement plan
- box_13_sick_pay: Boolean for third-party sick pay
- box_15_state: State abbreviation
- box_16: State wages (number)
- box_17: State income tax (number)
- box_18: Local wages (number or null)
- box_19: Local income tax (number or null)
- box_20: Locality name (string or null)

Use null for any field you cannot find. Only output the JSON object."""

        user_message = f"Extract W-2 data from:\n\n{text}"
        response = self._call(system, user_message)

        import json
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {}

    def extract_1099_int_data(self, text: str) -> dict:
        """Extract structured data from a 1099-INT form."""
        system = """You are a tax document data extractor specializing in 1099-INT forms.

Extract all relevant data and return a JSON object with:
- payer_name: Name of the payer (bank, institution)
- payer_ein: Payer's TIN
- recipient_ssn_last4: Last 4 digits of recipient SSN only
- recipient_name: Recipient name
- box_1: Interest income (number)
- box_2: Early withdrawal penalty (number or null)
- box_3: Interest on US Savings Bonds (number or null)
- box_4: Federal income tax withheld (number or null)
- box_5: Investment expenses (number or null)
- box_6: Foreign tax paid (number or null)
- box_8: Tax-exempt interest (number or null)
- box_9: Private activity bond interest (number or null)
- state: State abbreviation if present
- state_tax_withheld: State tax withheld (number or null)

Use null for any field you cannot find. Only output the JSON object."""

        user_message = f"Extract 1099-INT data from:\n\n{text}"
        response = self._call(system, user_message)

        import json
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {}

    def extract_1099_div_data(self, text: str) -> dict:
        """Extract structured data from a 1099-DIV form."""
        system = """You are a tax document data extractor specializing in 1099-DIV forms.

Extract all relevant data and return a JSON object with:
- payer_name: Name of the payer
- payer_ein: Payer's TIN
- recipient_ssn_last4: Last 4 digits of recipient SSN only
- recipient_name: Recipient name
- box_1a: Total ordinary dividends (number)
- box_1b: Qualified dividends (number or null)
- box_2a: Total capital gain distributions (number or null)
- box_2b: Unrecap. Sec. 1250 gain (number or null)
- box_2c: Section 1202 gain (number or null)
- box_2d: Collectibles (28%) gain (number or null)
- box_2e: Section 897 ordinary dividends (number or null)
- box_2f: Section 897 capital gain (number or null)
- box_3: Nondividend distributions (number or null)
- box_4: Federal income tax withheld (number or null)
- box_5: Section 199A dividends (number or null)
- box_6: Investment expenses (number or null)
- box_7: Foreign tax paid (number or null)
- box_11: FATCA filing requirement (boolean)
- box_12: Exempt-interest dividends (number or null)
- box_13: Private activity bond interest (number or null)
- state: State abbreviation if present
- state_tax_withheld: State tax withheld (number or null)

Use null for any field you cannot find. Only output the JSON object."""

        user_message = f"Extract 1099-DIV data from:\n\n{text}"
        response = self._call(system, user_message)

        import json
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {}

    def extract_1099_b_data(self, text: str) -> dict:
        """Extract structured data from a 1099-B form."""
        system = """You are a tax document data extractor specializing in 1099-B forms (brokerage statements).

These forms contain investment transactions. Extract data and return a JSON object with:
- payer_name: Name of the broker
- payer_ein: Broker's TIN
- recipient_ssn_last4: Last 4 digits of recipient SSN only
- recipient_name: Recipient name
- transactions: Array of transactions, each with:
  - description: Security description
  - date_acquired: Date acquired (YYYY-MM-DD or "Various")
  - date_sold: Date sold (YYYY-MM-DD)
  - proceeds: Sale proceeds (number)
  - cost_basis: Cost or other basis (number or null)
  - wash_sale_loss: Wash sale loss disallowed (number or null)
  - gain_loss: Gain or loss amount (number or null)
  - term: "short" or "long" or null
  - covered: true if basis reported to IRS, false otherwise
- summary:
  - total_proceeds: Total proceeds from all sales
  - total_cost_basis: Total cost basis (if available)
  - short_term_gain_loss: Net short-term gain/loss
  - long_term_gain_loss: Net long-term gain/loss
- federal_tax_withheld: Federal tax withheld (number or null)

Use null for any field you cannot find. Only output the JSON object."""

        user_message = f"Extract 1099-B data from:\n\n{text}"
        response = self._call(system, user_message, max_tokens=8000)

        import json
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {}

    def analyze_tax_implications(self, documents_summary: str, taxpayer_info: str) -> str:
        """
        Analyze tax implications based on collected documents.

        Args:
            documents_summary: Summary of all collected documents
            taxpayer_info: Taxpayer profile information

        Returns:
            Analysis text
        """
        system = """You are an AGGRESSIVE tax advisor whose primary mission is to MINIMIZE the taxpayer's tax burden through every legal means available. Leave no stone unturned.

Your analysis MUST include:

1. **INCOME ANALYSIS** - Identify ALL income sources. Look for:
   - Unreported income that could trigger IRS matching
   - Income that might be excludable or deferrable
   - Opportunities to shift income timing

2. **WITHHOLDING GAPS** - Be AGGRESSIVE here:
   - RSU withholding is often insufficient (22% flat vs actual bracket)
   - Calculate exact under/over withholding amounts
   - Recommend estimated payment adjustments

3. **DEDUCTION MAXIMIZATION** - Find EVERY possible deduction:
   - Standard vs itemized - run the numbers both ways
   - Above-the-line deductions (IRA, HSA, student loan)
   - Bunching strategies for itemized deductions
   - State tax deduction optimization (SALT cap workarounds)
   - Home office deductions (even partial)
   - Investment interest expense
   - Charitable giving strategies (donor-advised funds, appreciated stock)

4. **CREDIT HUNTING** - Aggressively identify ALL credits:
   - Child Tax Credit and Additional CTC
   - Earned Income Credit (check eligibility even for higher earners)
   - Education credits (AOTC, LLC)
   - Retirement Saver's Credit
   - Child and Dependent Care Credit
   - Energy credits (EV, solar, home improvements)
   - Foreign Tax Credit

5. **INVESTMENT TAX OPTIMIZATION**:
   - Tax-loss harvesting opportunities
   - Wash sale violations to avoid
   - Qualified dividend vs ordinary income
   - Long-term vs short-term gain positioning
   - Net Investment Income Tax (NIIT) planning

6. **RETIREMENT OPTIMIZATION**:
   - Max out 401(k) contributions
   - Backdoor Roth opportunities
   - Traditional vs Roth analysis
   - Mega backdoor Roth if available

7. **STATE TAX STRATEGIES**:
   - State-specific deductions and credits
   - Remote work tax implications
   - Multi-state issues

8. **IMMEDIATE ACTION ITEMS** - Specific, numbered steps with dollar estimates

9. **POTENTIAL SAVINGS SUMMARY** - Total up ALL potential tax savings identified

Be SPECIFIC with dollar amounts. If you can save them $50, mention it. The goal is MAXIMUM tax efficiency within legal bounds."""

        user_message = f"""Taxpayer Information:
{taxpayer_info}

Collected Documents Summary:
{documents_summary}

Please analyze the tax implications."""

        return self._call(system, user_message, max_tokens=4000)

    def review_tax_return(self, return_text: str, source_documents: str) -> str:
        """
        Review a completed tax return against source documents.

        Args:
            return_text: Text extracted from the tax return
            source_documents: Summary of source documents

        Returns:
            Review findings
        """
        system = """You are an EXPERT IRS auditor and tax optimization specialist conducting a thorough review. Your job is to find EVERY error, EVERY missed opportunity, and EVERY potential problem.

## CRITICAL CHECKS - Review with extreme diligence:

### 1. INCOME VERIFICATION (IRS will match these!)
- Cross-check EVERY W-2 Box 1 amount against Line 1
- Verify ALL 1099-INT interest income (banks report to IRS)
- Confirm ALL 1099-DIV dividends (ordinary AND qualified)
- Check 1099-B proceeds match Schedule D
- Look for MISSING income sources (IRS notices for omissions)
- Verify state income reporting consistency

### 2. MATH ERROR DETECTION
- Verify all addition on Schedule 1
- Check AGI calculation
- Confirm tax table lookup or computation
- Verify credit calculations
- Check refund/amount owed arithmetic

### 3. AGGRESSIVE DEDUCTION REVIEW
- Is standard deduction vs itemized OPTIMAL?
- Are ALL above-the-line deductions claimed?
- For itemized: SALT capped at $10K?
- Mortgage interest properly reported?
- Charitable deductions with proper documentation thresholds?
- Medical expenses over 7.5% AGI floor?

### 4. CREDIT OPTIMIZATION (Often missed!)
- Child Tax Credit - is it maximized?
- Earned Income Credit - even partial eligibility?
- Education credits - AOTC vs LLC optimization?
- Child Care Credit claimed?
- Retirement Saver's Credit eligible?
- Foreign Tax Credit for international investments?
- EV/Energy credits claimed?

### 5. INVESTMENT TAX ISSUES
- Long-term vs short-term classification CORRECT?
- Wash sales properly reported?
- Cost basis accurate (especially for RSUs)?
- Qualified dividend treatment applied?
- Capital loss carryforward used?
- Net Investment Income Tax (NIIT) correctly calculated if applicable?

### 6. FILING STATUS OPTIMIZATION
- Is current filing status OPTIMAL?
- Head of Household vs Single eligibility?
- Married Filing Separately ever beneficial?

### 7. COMPLIANCE RED FLAGS
- Large deductions relative to income
- Home office claims
- Excessive charitable giving
- Unusual capital losses
- Round number reporting

## OUTPUT FORMAT:
For EACH finding, provide:
- **SEVERITY**: ERROR (must fix) / WARNING (investigate) / OPPORTUNITY (money left on table)
- **CATEGORY**: income/deduction/credit/compliance/optimization
- **ISSUE**: Clear description
- **EXPECTED**: What it should be
- **ACTUAL**: What the return shows
- **TAX IMPACT**: Dollar amount at stake
- **ACTION**: Specific fix or optimization

Be AGGRESSIVE in finding issues. If something seems off, flag it. Better to over-report than miss savings."""

        user_message = f"""Source Documents:
{source_documents}

Tax Return:
{return_text}

Please review this return for errors and optimization opportunities."""

        return self._call(system, user_message, max_tokens=4000)


    def validate_documents_cross_reference(self, documents_data: list[dict]) -> dict:
        """
        Cross-validate data across multiple tax documents for consistency.

        Args:
            documents_data: List of document dictionaries with type and extracted_data

        Returns:
            Validation results with issues and recommendations
        """
        import json

        system = """You are an expert IRS document auditor specializing in cross-document validation.

Analyze these tax documents for CONSISTENCY and COMPLETENESS. Look for:

## 1. INCOME CONSISTENCY
- Do W-2 wages match across multiple employers correctly?
- Is total SS wages under the annual limit ($168,600 for 2024)?
- Do 1099 totals add up to reported income?
- Are there duplicate documents (same EIN, same amounts)?

## 2. WITHHOLDING VERIFICATION
- Does federal withholding seem reasonable for the income level?
- Is SS tax ~6.2% of SS wages (capped at SS wage base)?
- Is Medicare tax ~1.45% of Medicare wages?
- Are there withholding discrepancies between documents?

## 3. MISSING DOCUMENT DETECTION
Based on the documents provided, identify what might be MISSING:
- W-2 reported but no corresponding state wages?
- Investment income but no 1099-B for capital gains?
- Interest/dividends mentioned but source document missing?
- Self-employment income indicators without 1099-NEC?

## 4. RED FLAGS FOR IRS MATCHING
The IRS receives copies of all these documents. Flag anything that could trigger a notice:
- Employer EIN validity
- Round number amounts (suspicious)
- Unusual patterns (very high withholding, etc.)
- SSN consistency across documents

## 5. DATA QUALITY ISSUES
- Missing EINs or invalid formats
- Inconsistent name spellings
- Address discrepancies
- Tax year mismatches

Return a JSON object with:
{
  "validation_status": "pass" | "warnings" | "errors",
  "consistency_score": 0.0-1.0,
  "issues": [
    {
      "severity": "error" | "warning" | "info",
      "category": "income" | "withholding" | "missing_doc" | "irs_matching" | "data_quality",
      "description": "detailed description",
      "documents_affected": ["doc_id1", "doc_id2"],
      "recommended_action": "what to do"
    }
  ],
  "missing_documents": [
    {
      "document_type": "type",
      "reason": "why we suspect it's missing",
      "importance": "high" | "medium" | "low"
    }
  ],
  "summary": {
    "total_wages": number,
    "total_federal_withholding": number,
    "total_state_withholding": number,
    "total_interest_income": number,
    "total_dividend_income": number,
    "total_capital_gains": number,
    "documents_reviewed": number
  }
}

Only output the JSON object."""

        docs_summary = json.dumps(documents_data, indent=2, default=str)
        user_message = f"""Validate these tax documents for consistency and completeness:

{docs_summary}

Perform cross-document validation and identify any issues."""

        response = self._call(system, user_message, max_tokens=4000)

        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "validation_status": "error",
                "consistency_score": 0.0,
                "issues": [{"severity": "error", "description": "Failed to parse validation response"}],
                "missing_documents": [],
                "summary": {}
            }

    def assess_audit_risk(self, return_summary: dict, documents_summary: dict) -> dict:
        """
        Assess the audit risk for a tax return.

        Args:
            return_summary: Summary of tax return data
            documents_summary: Summary of source documents

        Returns:
            Audit risk assessment with scores and recommendations
        """
        import json

        system = """You are an expert in IRS audit selection criteria and tax compliance.

Analyze this tax return for AUDIT RISK. The IRS uses various factors to select returns for examination.

## AUDIT TRIGGER FACTORS TO EVALUATE:

### 1. DIF SCORE INDICATORS (Discriminant Function)
- Deduction-to-income ratio (industry norms)
- Schedule C profit margins vs industry averages
- Large charitable contributions relative to income
- High unreimbursed employee expenses
- Excessive home office deductions

### 2. HIGH-RISK CATEGORIES
- Self-employment income (Schedule C)
- Large cash businesses
- Foreign bank accounts (FBAR)
- Complex investment transactions
- Cryptocurrency activity
- Rental property losses

### 3. MATHEMATICAL RED FLAGS
- Round numbers throughout
- Deductions at exact thresholds
- Unusual AGI breakpoints
- Credits at phase-out boundaries

### 4. DOCUMENT MATCHING RISK
- All W-2s and 1099s must match IRS records
- Missing income sources = automatic notice
- Employer/payer info accuracy

### 5. COMPARATIVE ANALYSIS
- Income vs lifestyle indicators
- Year-over-year changes
- Industry comparisons

## OUTPUT FORMAT:
Return a JSON object:
{
  "overall_risk_score": 1-10 (1=very low, 10=certain audit),
  "risk_level": "low" | "moderate" | "elevated" | "high",
  "audit_probability_estimate": "percentage estimate with reasoning",
  "risk_factors": [
    {
      "factor": "description",
      "risk_contribution": 1-10,
      "category": "dif_score" | "income" | "deductions" | "credits" | "compliance",
      "explanation": "why this increases risk",
      "mitigation": "how to reduce this risk"
    }
  ],
  "protective_factors": [
    {
      "factor": "description",
      "explanation": "why this reduces risk"
    }
  ],
  "documentation_recommendations": [
    {
      "item": "what to document",
      "reason": "why it's important",
      "priority": "high" | "medium" | "low"
    }
  ],
  "immediate_concerns": ["list of issues needing immediate attention"],
  "summary": "2-3 sentence overall assessment"
}

Only output the JSON object."""

        user_message = f"""Assess audit risk for this tax situation:

TAX RETURN SUMMARY:
{json.dumps(return_summary, indent=2, default=str)}

SOURCE DOCUMENTS:
{json.dumps(documents_summary, indent=2, default=str)}

Evaluate audit risk and provide recommendations."""

        response = self._call(system, user_message, max_tokens=4000)

        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "overall_risk_score": 5,
                "risk_level": "unknown",
                "error": "Failed to parse audit risk assessment"
            }

    def compare_filing_scenarios(self, income_data: dict, deductions_data: dict, tax_year: int) -> dict:
        """
        Compare different filing scenarios to find optimal strategy.

        Args:
            income_data: Income information
            deductions_data: Deduction information
            tax_year: Tax year

        Returns:
            Scenario comparison with recommendations
        """
        import json

        system = f"""You are a tax optimization expert. Compare different filing scenarios to find the OPTIMAL tax strategy for {tax_year}.

## SCENARIOS TO COMPARE:

### 1. FILING STATUS COMPARISON
- Single
- Married Filing Jointly (if applicable)
- Married Filing Separately (if applicable)
- Head of Household (if qualifying)
- Qualifying Surviving Spouse (if applicable)

For each applicable status, calculate:
- Standard deduction amount
- Tax bracket thresholds
- Credit eligibility/phase-outs
- AMT implications

### 2. STANDARD VS ITEMIZED DEDUCTION
Calculate both options:
- Standard deduction for filing status
- Total itemized deductions (SALT capped at $10K, mortgage interest, charitable, medical over 7.5% AGI)
- Difference and recommendation

### 3. INCOME TIMING STRATEGIES
- Defer income to next year (if beneficial)
- Accelerate income to current year
- Roth conversion considerations

### 4. DEDUCTION BUNCHING
- Bunch itemized deductions in alternating years
- Charitable contribution timing
- Medical procedure timing

### 5. CREDIT OPTIMIZATION
- Which credits are available under each scenario?
- Phase-out impacts by filing status

## OUTPUT FORMAT:
Return a JSON object:
{{
  "optimal_strategy": {{
    "filing_status": "recommended status",
    "deduction_method": "standard" | "itemized",
    "estimated_tax": number,
    "estimated_refund_or_owed": number,
    "key_reasons": ["reason1", "reason2"]
  }},
  "scenario_comparison": [
    {{
      "scenario_name": "description",
      "filing_status": "status",
      "deduction_method": "method",
      "estimated_tax": number,
      "effective_rate": "percentage",
      "vs_optimal_difference": number,
      "pros": ["pro1", "pro2"],
      "cons": ["con1", "con2"]
    }}
  ],
  "timing_recommendations": [
    {{
      "action": "description",
      "tax_impact": number,
      "deadline": "date or description",
      "priority": "high" | "medium" | "low"
    }}
  ],
  "bunching_analysis": {{
    "current_year_itemized_total": number,
    "threshold_for_bunching": number,
    "bunching_benefit": number,
    "recommended_strategy": "description"
  }},
  "warnings": ["important considerations"],
  "summary": "2-3 sentence recommendation"
}}

Only output the JSON object."""

        user_message = f"""Compare filing scenarios for this taxpayer:

INCOME DATA:
{json.dumps(income_data, indent=2, default=str)}

DEDUCTION DATA:
{json.dumps(deductions_data, indent=2, default=str)}

TAX YEAR: {tax_year}

Find the optimal filing strategy."""

        response = self._call(system, user_message, max_tokens=4000)

        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "optimal_strategy": {},
                "scenario_comparison": [],
                "error": "Failed to parse scenario comparison"
            }

    def analyze_investment_taxes(self, transactions: list[dict], holdings: list[dict] | None = None) -> dict:
        """
        Deep analysis of investment tax implications.

        Args:
            transactions: List of buy/sell transactions
            holdings: Current holdings (optional)

        Returns:
            Investment tax analysis with optimization strategies
        """
        import json

        system = """You are an expert in investment taxation, capital gains, and portfolio tax optimization.

Analyze these investment transactions for tax implications and optimization opportunities.

## ANALYSIS AREAS:

### 1. CAPITAL GAINS CLASSIFICATION
- Categorize each sale as short-term (<1 year) or long-term
- Calculate net short-term and long-term gains/losses
- Identify misclassification risks

### 2. WASH SALE DETECTION
- Identify transactions within 30-day wash sale window
- Calculate disallowed losses
- Flag potential future wash sale risks
- Recommend waiting periods before repurchasing

### 3. TAX-LOSS HARVESTING OPPORTUNITIES
- Identify unrealized losses in holdings
- Calculate potential tax savings from harvesting
- Suggest similar replacement securities
- Consider wash sale rule timing

### 4. QUALIFIED DIVIDEND ANALYSIS
- Identify dividends eligible for preferential rates
- Holding period verification
- Calculate tax savings from qualified vs ordinary treatment

### 5. NET INVESTMENT INCOME TAX (NIIT)
- Calculate if 3.8% NIIT applies
- Threshold analysis
- Strategies to minimize NIIT

### 6. COST BASIS OPTIMIZATION
- Specific identification opportunities
- FIFO vs average cost implications
- Lot selection strategies

### 7. ESTIMATED TAX IMPACT
- Calculate total capital gains tax
- Breakdown by term and rate
- State tax implications

## OUTPUT FORMAT:
Return a JSON object:
{
  "capital_gains_summary": {
    "short_term_gains": number,
    "short_term_losses": number,
    "net_short_term": number,
    "long_term_gains": number,
    "long_term_losses": number,
    "net_long_term": number,
    "total_net_gain_loss": number
  },
  "wash_sales": [
    {
      "security": "name",
      "sale_date": "date",
      "repurchase_date": "date",
      "disallowed_loss": number,
      "action_required": "description"
    }
  ],
  "harvesting_opportunities": [
    {
      "security": "name",
      "current_loss": number,
      "tax_savings_estimate": number,
      "replacement_suggestions": ["similar security"],
      "wash_sale_free_date": "date"
    }
  ],
  "niit_analysis": {
    "applies": boolean,
    "estimated_niit": number,
    "threshold_buffer": number,
    "mitigation_strategies": ["strategy"]
  },
  "estimated_tax": {
    "short_term_tax": number,
    "long_term_tax": number,
    "niit": number,
    "total_federal": number,
    "effective_rate": "percentage"
  },
  "optimization_actions": [
    {
      "action": "description",
      "potential_savings": number,
      "deadline": "date or description",
      "priority": "high" | "medium" | "low"
    }
  ],
  "warnings": ["important alerts"],
  "summary": "overall assessment"
}

Only output the JSON object."""

        data = {
            "transactions": transactions,
            "current_holdings": holdings or []
        }

        user_message = f"""Analyze these investment transactions for tax optimization:

{json.dumps(data, indent=2, default=str)}

Provide comprehensive investment tax analysis."""

        response = self._call(system, user_message, max_tokens=5000)

        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "capital_gains_summary": {},
                "wash_sales": [],
                "error": "Failed to parse investment analysis"
            }

    def identify_missing_documents(self, collected_docs: list[dict], tax_profile: dict) -> dict:
        """
        Use AI to identify potentially missing tax documents.

        Args:
            collected_docs: List of collected document summaries
            tax_profile: Taxpayer profile information

        Returns:
            List of potentially missing documents with importance
        """
        import json

        system = """You are a tax document collection specialist. Based on the taxpayer's profile and collected documents, identify what documents are LIKELY MISSING.

## DOCUMENT DETECTION LOGIC:

### 1. BASED ON COLLECTED DOCUMENTS
If they have:
- W-2 → Should have state W-2 copy (if in income tax state)
- 1099-DIV → Should have 1099-B if they sold mutual funds
- 1099-B with sales → Should have cost basis statements
- Multiple banks → Check for missing 1099-INT from each
- Brokerage account → Should have consolidated 1099

### 2. BASED ON TAXPAYER PROFILE
If they:
- Own a home → Should have 1098 (mortgage interest), property tax records
- Have kids → Should have SSN cards, dependent documentation
- Went to college → Should have 1098-T
- Have student loans → Should have 1098-E
- Are self-employed → Should have 1099-NEC, 1099-K, expense records
- Have rental property → Should have rent rolls, expense records
- Retired → Should have 1099-R, SSA-1099
- Have HSA → Should have 5498-SA, 1099-SA
- Contributed to charity → Should have receipts over $250

### 3. COMMON OVERSIGHTS
- State tax refund from prior year → 1099-G
- Unemployment → 1099-G
- Gambling winnings → W-2G
- Sold property → 1099-S
- Debt forgiveness → 1099-C
- Health insurance marketplace → 1095-A

## OUTPUT FORMAT:
Return a JSON object:
{
  "likely_missing": [
    {
      "document_type": "type",
      "reason": "why it's likely missing",
      "importance": "critical" | "high" | "medium" | "low",
      "irs_matching_risk": boolean,
      "typical_source": "where to get this document",
      "deadline_concern": "any time sensitivity"
    }
  ],
  "collection_completeness_score": 0.0-1.0,
  "ready_to_file": boolean,
  "blocking_documents": ["documents needed before filing"],
  "nice_to_have_documents": ["optional but beneficial"],
  "verification_suggestions": [
    {
      "check": "what to verify",
      "how": "how to verify it"
    }
  ],
  "summary": "overall assessment of document collection status"
}

Only output the JSON object."""

        user_message = f"""Identify missing documents for this taxpayer:

COLLECTED DOCUMENTS:
{json.dumps(collected_docs, indent=2, default=str)}

TAXPAYER PROFILE:
{json.dumps(tax_profile, indent=2, default=str)}

What documents are likely missing?"""

        response = self._call(system, user_message, max_tokens=3000)

        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "likely_missing": [],
                "collection_completeness_score": 0.5,
                "error": "Failed to parse missing documents analysis"
            }

    def deep_document_analysis(self, document_type: str, extracted_data: dict, raw_text: str) -> dict:
        """
        Perform deep AI analysis of a single document.

        Args:
            document_type: Type of document (W2, 1099-INT, etc.)
            extracted_data: Already extracted structured data
            raw_text: Original OCR text

        Returns:
            Deep analysis with insights and potential issues
        """
        import json

        system = f"""You are an expert tax document analyst performing a DEEP REVIEW of a {document_type} document.

Go beyond basic extraction to find:

## 1. DATA QUALITY ASSESSMENT
- Are all expected fields present?
- Do the numbers make mathematical sense?
- Are there any OCR errors likely?
- Is the formatting consistent?

## 2. TAX IMPLICATIONS
- What does this document mean for the taxpayer's taxes?
- Are there any special elections or treatments indicated?
- What lines of the tax return does this affect?

## 3. RED FLAGS & ANOMALIES
- Unusual amounts or patterns
- Missing required information
- Potential employer/payer errors
- Compliance concerns

## 4. CROSS-REFERENCE REQUIREMENTS
- What other documents should accompany this?
- What additional information is needed?
- IRS matching considerations

## 5. OPTIMIZATION OPPORTUNITIES
- Any tax planning implications?
- Timing considerations?
- Related deductions or credits?

## 6. SPECIFIC CHECKS FOR {document_type}
{"- W-2: Check box 12 codes for retirement contributions, verify SS/Medicare calculations" if document_type == "W2" else ""}
{"- 1099-INT: Verify tax-exempt interest treatment, check for early withdrawal penalties" if document_type == "1099_INT" else ""}
{"- 1099-DIV: Check qualified dividend classification, verify capital gains distributions" if document_type == "1099_DIV" else ""}
{"- 1099-B: Verify cost basis, check term classification, look for wash sale reporting" if document_type == "1099_B" else ""}

## OUTPUT FORMAT:
Return a JSON object:
{{
  "analysis_confidence": 0.0-1.0,
  "data_quality": {{
    "completeness_score": 0.0-1.0,
    "accuracy_concerns": ["concern1", "concern2"],
    "likely_ocr_errors": ["potential error"],
    "fields_needing_verification": ["field1", "field2"]
  }},
  "tax_implications": {{
    "primary_impact": "description of main tax impact",
    "affected_forms": ["Form 1040 Line X", "Schedule Y"],
    "estimated_tax_impact": number or null,
    "special_treatments": ["any special tax treatments"]
  }},
  "red_flags": [
    {{
      "issue": "description",
      "severity": "high" | "medium" | "low",
      "recommended_action": "what to do"
    }}
  ],
  "cross_reference_needs": [
    {{
      "document_type": "type",
      "reason": "why needed"
    }}
  ],
  "optimization_opportunities": [
    {{
      "opportunity": "description",
      "potential_benefit": "estimated benefit",
      "action_required": "what to do"
    }}
  ],
  "key_insights": ["insight1", "insight2"],
  "summary": "2-3 sentence overall assessment"
}}

Only output the JSON object."""

        user_message = f"""Perform deep analysis of this {document_type}:

EXTRACTED DATA:
{json.dumps(extracted_data, indent=2, default=str)}

RAW TEXT:
{raw_text[:6000]}

Provide comprehensive analysis."""

        response = self._call(system, user_message, max_tokens=3000)

        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "analysis_confidence": 0.0,
                "error": "Failed to parse deep analysis"
            }

    def generate_tax_planning_recommendations(self, current_year_data: dict, profile: dict) -> dict:
        """
        Generate forward-looking tax planning recommendations.

        Args:
            current_year_data: Current year tax situation
            profile: Taxpayer profile

        Returns:
            Tax planning recommendations for current and future years
        """
        import json

        system = """You are a proactive tax planning strategist. Based on this taxpayer's current situation, generate ACTIONABLE tax planning recommendations.

## PLANNING AREAS:

### 1. IMMEDIATE ACTIONS (Before Year End)
- Retirement contribution maximization
- Tax-loss harvesting
- Charitable giving timing
- Income deferral opportunities
- Expense acceleration

### 2. ESTIMATED TAX PLANNING
- Are quarterly payments needed?
- Safe harbor calculations
- Penalty avoidance strategies

### 3. RETIREMENT OPTIMIZATION
- 401(k) contribution strategy
- IRA contributions (Traditional vs Roth)
- Backdoor Roth opportunities
- Mega backdoor Roth if available
- Required Minimum Distributions (if applicable)

### 4. INVESTMENT TAX MANAGEMENT
- Asset location optimization
- Tax-efficient fund selection
- Capital gains management
- Dividend timing

### 5. LIFE EVENT PLANNING
- Marriage/divorce implications
- Home purchase/sale
- Job changes
- Business start/sale

### 6. MULTI-YEAR PROJECTIONS
- Income smoothing strategies
- Bracket management
- Credit phase-out planning
- AMT planning

## OUTPUT FORMAT:
Return a JSON object:
{
  "immediate_actions": [
    {
      "action": "description",
      "deadline": "date",
      "estimated_benefit": number,
      "steps": ["step1", "step2"],
      "priority": "critical" | "high" | "medium"
    }
  ],
  "quarterly_estimated_taxes": {
    "required": boolean,
    "next_payment_due": "date",
    "recommended_amount": number,
    "safe_harbor_method": "description"
  },
  "retirement_strategy": {
    "recommended_401k_contribution": number,
    "recommended_ira_contribution": number,
    "ira_type_recommendation": "Traditional" | "Roth" | "Both",
    "backdoor_roth_eligible": boolean,
    "additional_recommendations": ["rec1", "rec2"]
  },
  "investment_strategy": [
    {
      "recommendation": "description",
      "rationale": "why",
      "estimated_annual_benefit": number
    }
  ],
  "next_year_projections": {
    "estimated_income": number,
    "estimated_tax": number,
    "key_planning_opportunities": ["opp1", "opp2"]
  },
  "long_term_strategies": [
    {
      "strategy": "description",
      "timeline": "when to implement",
      "cumulative_benefit": "estimated lifetime benefit"
    }
  ],
  "warnings": ["important considerations"],
  "summary": "overall planning recommendation"
}

Only output the JSON object."""

        user_message = f"""Generate tax planning recommendations:

CURRENT YEAR DATA:
{json.dumps(current_year_data, indent=2, default=str)}

TAXPAYER PROFILE:
{json.dumps(profile, indent=2, default=str)}

Provide comprehensive tax planning guidance."""

        response = self._call(system, user_message, max_tokens=4000)

        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "immediate_actions": [],
                "error": "Failed to parse tax planning recommendations"
            }


# Global agent instance
_agent: TaxAgent | None = None


def get_agent() -> TaxAgent:
    """Get the global tax agent instance."""
    global _agent
    if _agent is None:
        _agent = TaxAgent()
    return _agent

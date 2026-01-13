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


# Global agent instance
_agent: TaxAgent | None = None


def get_agent() -> TaxAgent:
    """Get the global tax agent instance."""
    global _agent
    if _agent is None:
        _agent = TaxAgent()
    return _agent

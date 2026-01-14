"""Tax calculation tools for the Claude Agent SDK.

These tools can be used as MCP tools when the Agent SDK is available,
or called directly as utility functions.
"""

from datetime import datetime
from typing import Any


# 2024 Tax Brackets (Federal)
TAX_BRACKETS_2024 = {
    "single": [
        (11600, 0.10),
        (47150, 0.12),
        (100525, 0.22),
        (191950, 0.24),
        (243725, 0.32),
        (609350, 0.35),
        (float("inf"), 0.37),
    ],
    "married_filing_jointly": [
        (23200, 0.10),
        (94300, 0.12),
        (201050, 0.22),
        (383900, 0.24),
        (487450, 0.32),
        (731200, 0.35),
        (float("inf"), 0.37),
    ],
    "married_filing_separately": [
        (11600, 0.10),
        (47150, 0.12),
        (100525, 0.22),
        (191950, 0.24),
        (243725, 0.32),
        (365600, 0.35),
        (float("inf"), 0.37),
    ],
    "head_of_household": [
        (16550, 0.10),
        (63100, 0.12),
        (100500, 0.22),
        (191950, 0.24),
        (243700, 0.32),
        (609350, 0.35),
        (float("inf"), 0.37),
    ],
}

# 2025 Tax Brackets (Federal) - projected/estimated
TAX_BRACKETS_2025 = {
    "single": [
        (11925, 0.10),
        (48475, 0.12),
        (103350, 0.22),
        (197300, 0.24),
        (250525, 0.32),
        (626350, 0.35),
        (float("inf"), 0.37),
    ],
    "married_filing_jointly": [
        (23850, 0.10),
        (96950, 0.12),
        (206700, 0.22),
        (394600, 0.24),
        (501050, 0.32),
        (751600, 0.35),
        (float("inf"), 0.37),
    ],
    "married_filing_separately": [
        (11925, 0.10),
        (48475, 0.12),
        (103350, 0.22),
        (197300, 0.24),
        (250525, 0.32),
        (375800, 0.35),
        (float("inf"), 0.37),
    ],
    "head_of_household": [
        (17000, 0.10),
        (64850, 0.12),
        (103350, 0.22),
        (197300, 0.24),
        (250500, 0.32),
        (626350, 0.35),
        (float("inf"), 0.37),
    ],
}

# Standard Deductions
STANDARD_DEDUCTIONS = {
    2024: {
        "single": 14600,
        "married_filing_jointly": 29200,
        "married_filing_separately": 14600,
        "head_of_household": 21900,
        "additional_65_or_blind_single": 1950,
        "additional_65_or_blind_married": 1550,
    },
    2025: {
        "single": 15000,
        "married_filing_jointly": 30000,
        "married_filing_separately": 15000,
        "head_of_household": 22500,
        "additional_65_or_blind_single": 2000,
        "additional_65_or_blind_married": 1600,
    },
}

# Contribution Limits
CONTRIBUTION_LIMITS = {
    2024: {
        "401k": {"regular": 23000, "catch_up": 7500, "catch_up_age": 50},
        "403b": {"regular": 23000, "catch_up": 7500, "catch_up_age": 50},
        "ira": {"regular": 7000, "catch_up": 1000, "catch_up_age": 50},
        "roth_ira": {"regular": 7000, "catch_up": 1000, "catch_up_age": 50},
        "simple_ira": {"regular": 16000, "catch_up": 3500, "catch_up_age": 50},
        "hsa_individual": {"regular": 4150, "catch_up": 1000, "catch_up_age": 55},
        "hsa_family": {"regular": 8300, "catch_up": 1000, "catch_up_age": 55},
        "fsa_health": {"regular": 3200},
        "fsa_dependent_care": {"regular": 5000},
    },
    2025: {
        "401k": {"regular": 23500, "catch_up": 7500, "catch_up_age": 50},
        "403b": {"regular": 23500, "catch_up": 7500, "catch_up_age": 50},
        "ira": {"regular": 7000, "catch_up": 1000, "catch_up_age": 50},
        "roth_ira": {"regular": 7000, "catch_up": 1000, "catch_up_age": 50},
        "simple_ira": {"regular": 16500, "catch_up": 3500, "catch_up_age": 50},
        "hsa_individual": {"regular": 4300, "catch_up": 1000, "catch_up_age": 55},
        "hsa_family": {"regular": 8550, "catch_up": 1000, "catch_up_age": 55},
        "fsa_health": {"regular": 3300},
        "fsa_dependent_care": {"regular": 5000},
    },
}

# Social Security Wage Base
SS_WAGE_BASE = {
    2024: 168600,
    2025: 176100,
}

# FICA Rates
FICA_RATES = {
    "social_security": 0.062,
    "medicare": 0.0145,
    "additional_medicare": 0.009,  # On wages over $200k single / $250k married
}


def get_tax_brackets(
    tax_year: int | None = None,
    filing_status: str = "single",
) -> list[tuple[float, float]]:
    """
    Get federal tax brackets for a given year and filing status.

    Args:
        tax_year: Tax year (defaults to current year)
        filing_status: Filing status (single, married_filing_jointly, etc.)

    Returns:
        List of (threshold, rate) tuples
    """
    year = tax_year or datetime.now().year
    brackets = TAX_BRACKETS_2025 if year >= 2025 else TAX_BRACKETS_2024

    # Normalize filing status
    status = filing_status.lower().replace(" ", "_").replace("-", "_")

    return brackets.get(status, brackets["single"])


def get_standard_deduction(
    tax_year: int | None = None,
    filing_status: str = "single",
    age_65_or_older: bool = False,
    blind: bool = False,
) -> float:
    """
    Get the standard deduction for a given year and filing status.

    Args:
        tax_year: Tax year (defaults to current year)
        filing_status: Filing status
        age_65_or_older: Whether taxpayer is 65 or older
        blind: Whether taxpayer is blind

    Returns:
        Standard deduction amount
    """
    year = tax_year or datetime.now().year
    deductions = STANDARD_DEDUCTIONS.get(year, STANDARD_DEDUCTIONS[2024])

    # Normalize filing status
    status = filing_status.lower().replace(" ", "_").replace("-", "_")

    base = deductions.get(status, deductions["single"])

    # Add additional amounts for age 65+ or blind
    additional = 0
    if age_65_or_older or blind:
        if status in ["single", "head_of_household"]:
            additional_per = deductions["additional_65_or_blind_single"]
        else:
            additional_per = deductions["additional_65_or_blind_married"]

        if age_65_or_older:
            additional += additional_per
        if blind:
            additional += additional_per

    return base + additional


def calculate_federal_tax(
    taxable_income: float,
    filing_status: str = "single",
    tax_year: int | None = None,
) -> dict[str, Any]:
    """
    Calculate federal income tax for given taxable income.

    Args:
        taxable_income: Taxable income after deductions
        filing_status: Filing status
        tax_year: Tax year (defaults to current year)

    Returns:
        Dictionary with tax breakdown
    """
    brackets = get_tax_brackets(tax_year, filing_status)

    tax = 0.0
    breakdown = []
    remaining_income = taxable_income
    prev_threshold = 0

    for threshold, rate in brackets:
        if remaining_income <= 0:
            break

        bracket_income = min(remaining_income, threshold - prev_threshold)
        bracket_tax = bracket_income * rate

        if bracket_income > 0:
            breakdown.append({
                "bracket": f"{prev_threshold:,.0f} - {threshold:,.0f}",
                "rate": f"{rate:.0%}",
                "income_in_bracket": bracket_income,
                "tax": bracket_tax,
            })

        tax += bracket_tax
        remaining_income -= bracket_income
        prev_threshold = threshold

    effective_rate = (tax / taxable_income * 100) if taxable_income > 0 else 0

    return {
        "taxable_income": taxable_income,
        "filing_status": filing_status,
        "tax_year": tax_year or datetime.now().year,
        "total_tax": tax,
        "effective_rate": f"{effective_rate:.2f}%",
        "marginal_rate": f"{brackets[-1][1]:.0%}" if taxable_income > 0 else "0%",
        "breakdown": breakdown,
    }


def check_contribution_limits(
    account_type: str,
    age: int = 30,
    tax_year: int | None = None,
) -> dict[str, Any]:
    """
    Check IRS contribution limits for retirement/savings accounts.

    Args:
        account_type: Type of account (401k, ira, hsa_individual, etc.)
        age: Taxpayer's age for catch-up eligibility
        tax_year: Tax year (defaults to current year)

    Returns:
        Dictionary with limit information
    """
    year = tax_year or datetime.now().year
    limits = CONTRIBUTION_LIMITS.get(year, CONTRIBUTION_LIMITS[2024])

    # Normalize account type
    account = account_type.lower().replace(" ", "_").replace("-", "_")

    if account not in limits:
        return {
            "error": f"Unknown account type: {account_type}",
            "available_types": list(limits.keys()),
        }

    limit_info = limits[account]
    base_limit = limit_info["regular"]
    catch_up_amount = limit_info.get("catch_up", 0)
    catch_up_age = limit_info.get("catch_up_age", 999)

    eligible_for_catch_up = age >= catch_up_age
    total_limit = base_limit + (catch_up_amount if eligible_for_catch_up else 0)

    return {
        "account_type": account_type,
        "tax_year": year,
        "base_limit": base_limit,
        "catch_up_amount": catch_up_amount if eligible_for_catch_up else 0,
        "catch_up_eligible": eligible_for_catch_up,
        "catch_up_age_threshold": catch_up_age,
        "total_limit": total_limit,
        "your_age": age,
    }


def detect_wash_sales(
    transactions: list[dict],
) -> dict[str, Any]:
    """
    Detect potential wash sale violations in transaction history.

    A wash sale occurs when you sell a security at a loss and buy
    substantially identical securities within 30 days before or after.

    Args:
        transactions: List of transaction dicts with:
            - description: Security name/identifier
            - date_acquired: Purchase date (YYYY-MM-DD)
            - date_sold: Sale date (YYYY-MM-DD) - only for sales
            - proceeds: Sale amount
            - cost_basis: Cost basis
            - gain_loss: Gain or loss amount

    Returns:
        Dictionary with wash sale analysis
    """
    from datetime import datetime, timedelta

    wash_sales = []
    total_disallowed = 0.0

    # Find all sales at a loss
    sales_at_loss = [
        t for t in transactions
        if t.get("date_sold") and t.get("gain_loss", 0) < 0
    ]

    # Find all purchases
    purchases = [
        t for t in transactions
        if t.get("date_acquired") and not t.get("date_sold")
    ]

    for sale in sales_at_loss:
        try:
            sale_date = datetime.strptime(sale["date_sold"], "%Y-%m-%d")
            security = sale.get("description", "").lower()
            loss_amount = abs(sale.get("gain_loss", 0))

            # Look for purchases of same security within 30-day window
            for purchase in purchases:
                if security not in purchase.get("description", "").lower():
                    continue

                try:
                    purchase_date = datetime.strptime(
                        purchase["date_acquired"], "%Y-%m-%d"
                    )
                    days_diff = abs((sale_date - purchase_date).days)

                    if days_diff <= 30:
                        wash_sales.append({
                            "security": sale.get("description"),
                            "sale_date": sale["date_sold"],
                            "sale_loss": loss_amount,
                            "purchase_date": purchase["date_acquired"],
                            "days_apart": days_diff,
                            "disallowed_loss": loss_amount,
                            "wash_sale_free_date": (
                                sale_date + timedelta(days=31)
                            ).strftime("%Y-%m-%d"),
                        })
                        total_disallowed += loss_amount
                        break  # Only count once per sale
                except (ValueError, KeyError):
                    continue
        except (ValueError, KeyError):
            continue

    return {
        "wash_sales_found": len(wash_sales),
        "total_disallowed_loss": total_disallowed,
        "wash_sales": wash_sales,
        "transactions_analyzed": len(transactions),
        "recommendation": (
            "Review flagged transactions. Disallowed losses are added to cost basis "
            "of replacement shares." if wash_sales else "No wash sales detected."
        ),
    }


def calculate_fica_taxes(
    wages: float,
    self_employment_income: float = 0,
    filing_status: str = "single",
    tax_year: int | None = None,
) -> dict[str, Any]:
    """
    Calculate FICA taxes (Social Security and Medicare).

    Args:
        wages: W-2 wages subject to FICA
        self_employment_income: Self-employment income
        filing_status: For additional Medicare tax threshold
        tax_year: Tax year

    Returns:
        Dictionary with FICA tax breakdown
    """
    year = tax_year or datetime.now().year
    ss_wage_base = SS_WAGE_BASE.get(year, SS_WAGE_BASE[2024])

    # Social Security on wages (up to wage base)
    ss_wages = min(wages, ss_wage_base)
    ss_tax_employee = ss_wages * FICA_RATES["social_security"]

    # Medicare on all wages
    medicare_wages = wages
    medicare_tax = medicare_wages * FICA_RATES["medicare"]

    # Additional Medicare Tax threshold
    additional_medicare_threshold = (
        250000 if "married_filing_jointly" in filing_status.lower()
        else 200000
    )

    additional_medicare = 0.0
    if wages > additional_medicare_threshold:
        additional_medicare = (
            (wages - additional_medicare_threshold) *
            FICA_RATES["additional_medicare"]
        )

    # Self-employment tax (if applicable)
    se_tax = 0.0
    if self_employment_income > 0:
        # SE tax is on 92.35% of SE income
        se_income_for_tax = self_employment_income * 0.9235
        se_ss_income = min(se_income_for_tax, max(0, ss_wage_base - wages))
        se_tax = (
            se_ss_income * (FICA_RATES["social_security"] * 2) +
            se_income_for_tax * (FICA_RATES["medicare"] * 2)
        )

    total_fica = ss_tax_employee + medicare_tax + additional_medicare + se_tax

    return {
        "tax_year": year,
        "social_security": {
            "wages_subject": ss_wages,
            "wage_base": ss_wage_base,
            "tax": ss_tax_employee,
            "rate": f"{FICA_RATES['social_security']:.2%}",
        },
        "medicare": {
            "wages_subject": medicare_wages,
            "tax": medicare_tax,
            "rate": f"{FICA_RATES['medicare']:.2%}",
        },
        "additional_medicare": {
            "threshold": additional_medicare_threshold,
            "wages_over_threshold": max(0, wages - additional_medicare_threshold),
            "tax": additional_medicare,
            "rate": f"{FICA_RATES['additional_medicare']:.2%}",
        },
        "self_employment_tax": se_tax,
        "total_fica": total_fica,
    }


# MCP Tool Definitions (for use with Claude Agent SDK)
# These define the tool schemas for the SDK

MCP_TOOL_DEFINITIONS = [
    {
        "name": "calculate_federal_tax",
        "description": "Calculate federal income tax for given taxable income and filing status",
        "input_schema": {
            "type": "object",
            "properties": {
                "taxable_income": {
                    "type": "number",
                    "description": "Taxable income after deductions",
                },
                "filing_status": {
                    "type": "string",
                    "enum": ["single", "married_filing_jointly", "married_filing_separately", "head_of_household"],
                    "description": "Tax filing status",
                },
                "tax_year": {
                    "type": "integer",
                    "description": "Tax year (defaults to current year)",
                },
            },
            "required": ["taxable_income"],
        },
    },
    {
        "name": "check_contribution_limits",
        "description": "Check IRS contribution limits for retirement and savings accounts",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_type": {
                    "type": "string",
                    "enum": ["401k", "403b", "ira", "roth_ira", "simple_ira", "hsa_individual", "hsa_family", "fsa_health", "fsa_dependent_care"],
                    "description": "Type of account",
                },
                "age": {
                    "type": "integer",
                    "description": "Taxpayer's age for catch-up eligibility",
                },
                "tax_year": {
                    "type": "integer",
                    "description": "Tax year (defaults to current year)",
                },
            },
            "required": ["account_type"],
        },
    },
    {
        "name": "detect_wash_sales",
        "description": "Detect potential wash sale violations in investment transactions",
        "input_schema": {
            "type": "object",
            "properties": {
                "transactions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "date_acquired": {"type": "string"},
                            "date_sold": {"type": "string"},
                            "proceeds": {"type": "number"},
                            "cost_basis": {"type": "number"},
                            "gain_loss": {"type": "number"},
                        },
                    },
                    "description": "List of buy/sell transactions",
                },
            },
            "required": ["transactions"],
        },
    },
    {
        "name": "get_standard_deduction",
        "description": "Get the standard deduction for a filing status and year",
        "input_schema": {
            "type": "object",
            "properties": {
                "filing_status": {
                    "type": "string",
                    "enum": ["single", "married_filing_jointly", "married_filing_separately", "head_of_household"],
                },
                "tax_year": {"type": "integer"},
                "age_65_or_older": {"type": "boolean"},
                "blind": {"type": "boolean"},
            },
            "required": ["filing_status"],
        },
    },
]

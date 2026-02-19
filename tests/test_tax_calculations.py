"""Tests for tax calculation tools (pure math, no API mocking needed)."""

import pytest

from tax_agent.tools.tax_calculations import (
    TAX_BRACKETS_2024,
    TAX_BRACKETS_2025,
    STANDARD_DEDUCTIONS,
    CONTRIBUTION_LIMITS,
    SS_WAGE_BASE,
    FICA_RATES,
    get_tax_brackets,
    get_standard_deduction,
    calculate_federal_tax,
    check_contribution_limits,
    detect_wash_sales,
    calculate_fica_taxes,
)


class TestGetTaxBrackets:
    """Tests for get_tax_brackets()."""

    def test_single_2024(self):
        brackets = get_tax_brackets(2024, "single")
        assert brackets == TAX_BRACKETS_2024["single"]

    def test_mfj_2024(self):
        brackets = get_tax_brackets(2024, "married_filing_jointly")
        assert brackets == TAX_BRACKETS_2024["married_filing_jointly"]

    def test_mfs_2024(self):
        brackets = get_tax_brackets(2024, "married_filing_separately")
        assert brackets == TAX_BRACKETS_2024["married_filing_separately"]

    def test_hoh_2024(self):
        brackets = get_tax_brackets(2024, "head_of_household")
        assert brackets == TAX_BRACKETS_2024["head_of_household"]

    def test_2025_uses_2025_brackets(self):
        brackets = get_tax_brackets(2025, "single")
        assert brackets == TAX_BRACKETS_2025["single"]

    def test_status_normalization_spaces(self):
        brackets = get_tax_brackets(2024, "married filing jointly")
        assert brackets == TAX_BRACKETS_2024["married_filing_jointly"]

    def test_status_normalization_dashes(self):
        brackets = get_tax_brackets(2024, "married-filing-jointly")
        assert brackets == TAX_BRACKETS_2024["married_filing_jointly"]

    def test_status_normalization_case(self):
        brackets = get_tax_brackets(2024, "Single")
        assert brackets == TAX_BRACKETS_2024["single"]

    def test_unknown_status_defaults_to_single(self):
        brackets = get_tax_brackets(2024, "unknown_status")
        assert brackets == TAX_BRACKETS_2024["single"]

    def test_pre_2025_uses_2024(self):
        brackets = get_tax_brackets(2023, "single")
        assert brackets == TAX_BRACKETS_2024["single"]


class TestGetStandardDeduction:
    """Tests for get_standard_deduction()."""

    def test_single_2024(self):
        assert get_standard_deduction(2024, "single") == 14600

    def test_mfj_2024(self):
        assert get_standard_deduction(2024, "married_filing_jointly") == 29200

    def test_mfs_2024(self):
        assert get_standard_deduction(2024, "married_filing_separately") == 14600

    def test_hoh_2024(self):
        assert get_standard_deduction(2024, "head_of_household") == 21900

    def test_single_2025(self):
        assert get_standard_deduction(2025, "single") == 15000

    def test_mfj_2025(self):
        assert get_standard_deduction(2025, "married_filing_jointly") == 30000

    def test_single_65_plus(self):
        # Single + 65+ = 14600 + 1950 = 16550
        assert get_standard_deduction(2024, "single", age_65_or_older=True) == 16550

    def test_single_blind(self):
        # Single + blind = 14600 + 1950 = 16550
        assert get_standard_deduction(2024, "single", blind=True) == 16550

    def test_single_65_plus_and_blind(self):
        # Single + 65+ + blind = 14600 + 1950 + 1950 = 18500
        assert get_standard_deduction(2024, "single", age_65_or_older=True, blind=True) == 18500

    def test_married_65_plus(self):
        # MFJ + 65+ = 29200 + 1550 = 30750
        assert get_standard_deduction(2024, "married_filing_jointly", age_65_or_older=True) == 30750

    def test_married_65_plus_and_blind(self):
        # MFJ + 65+ + blind = 29200 + 1550 + 1550 = 32300
        assert get_standard_deduction(2024, "married_filing_jointly", age_65_or_older=True, blind=True) == 32300

    def test_hoh_65_plus(self):
        # HOH + 65+ = 21900 + 1950 = 23850 (uses single additional)
        assert get_standard_deduction(2024, "head_of_household", age_65_or_older=True) == 23850

    def test_unknown_year_falls_back_to_2024(self):
        assert get_standard_deduction(2020, "single") == 14600


class TestCalculateFederalTax:
    """Tests for calculate_federal_tax()."""

    def test_zero_income(self):
        result = calculate_federal_tax(0, "single", 2024)
        assert result["total_tax"] == 0.0
        assert result["effective_rate"] == "0.00%"

    def test_single_50k(self):
        # $50,000 single 2024:
        # $11,600 * 10% = $1,160
        # $35,550 * 12% = $4,266  (from 11,600 to 47,150)
        # $2,850 * 22% = $627     (from 47,150 to 50,000)
        # Total = $6,053
        result = calculate_federal_tax(50000, "single", 2024)
        assert abs(result["total_tax"] - 6053) < 1

    def test_single_100k(self):
        # $100,000 single 2024:
        # $11,600 * 10% = $1,160
        # $35,550 * 12% = $4,266
        # $53,375 * 22% = $11,742.50  (from 47,150 to 100,525)
        # But only $52,850 in 22% bracket (100k - 47,150)
        # $52,850 * 22% = $11,627
        # Total = $1,160 + $4,266 + $11,627 = $17,053
        result = calculate_federal_tax(100000, "single", 2024)
        assert abs(result["total_tax"] - 17053) < 1

    def test_mfj_100k(self):
        # $100,000 MFJ 2024:
        # $23,200 * 10% = $2,320
        # $71,100 * 12% = $8,532  (from 23,200 to 94,300)
        # $5,700 * 22% = $1,254   (from 94,300 to 100,000)
        # Total = $12,106
        result = calculate_federal_tax(100000, "married_filing_jointly", 2024)
        assert abs(result["total_tax"] - 12106) < 1

    def test_single_in_10_percent_bracket(self):
        # $10,000 single - all in 10% bracket
        result = calculate_federal_tax(10000, "single", 2024)
        assert abs(result["total_tax"] - 1000) < 1

    def test_breakdown_structure(self):
        result = calculate_federal_tax(50000, "single", 2024)
        assert "breakdown" in result
        assert len(result["breakdown"]) == 3  # 10%, 12%, 22% brackets
        assert result["breakdown"][0]["rate"] == "10%"
        assert result["breakdown"][1]["rate"] == "12%"
        assert result["breakdown"][2]["rate"] == "22%"

    def test_effective_rate_reasonable(self):
        result = calculate_federal_tax(75000, "single", 2024)
        rate = float(result["effective_rate"].rstrip("%"))
        assert 10 < rate < 22  # Should be between 10% bracket and marginal 22%

    def test_hoh_vs_single_lower_tax(self):
        """HOH should pay less tax than single on same income."""
        single = calculate_federal_tax(80000, "single", 2024)
        hoh = calculate_federal_tax(80000, "head_of_household", 2024)
        assert hoh["total_tax"] < single["total_tax"]

    def test_very_high_income(self):
        result = calculate_federal_tax(1000000, "single", 2024)
        rate = float(result["effective_rate"].rstrip("%"))
        assert rate < 37  # Effective should be less than top marginal
        assert rate > 30  # But pretty high for $1M

    def test_2025_brackets(self):
        result_2024 = calculate_federal_tax(50000, "single", 2024)
        result_2025 = calculate_federal_tax(50000, "single", 2025)
        # 2025 has wider brackets, so tax should be slightly lower
        assert result_2025["total_tax"] <= result_2024["total_tax"]


class TestCheckContributionLimits:
    """Tests for check_contribution_limits()."""

    def test_401k_under_50(self):
        result = check_contribution_limits("401k", age=30, tax_year=2024)
        assert result["base_limit"] == 23000
        assert result["catch_up_eligible"] is False
        assert result["total_limit"] == 23000

    def test_401k_over_50(self):
        result = check_contribution_limits("401k", age=55, tax_year=2024)
        assert result["base_limit"] == 23000
        assert result["catch_up_eligible"] is True
        assert result["catch_up_amount"] == 7500
        assert result["total_limit"] == 30500

    def test_401k_exactly_50(self):
        result = check_contribution_limits("401k", age=50, tax_year=2024)
        assert result["catch_up_eligible"] is True

    def test_ira_under_50(self):
        result = check_contribution_limits("ira", age=40, tax_year=2024)
        assert result["base_limit"] == 7000
        assert result["total_limit"] == 7000

    def test_ira_over_50(self):
        result = check_contribution_limits("ira", age=55, tax_year=2024)
        assert result["total_limit"] == 8000  # 7000 + 1000

    def test_roth_ira(self):
        result = check_contribution_limits("roth_ira", age=30, tax_year=2024)
        assert result["base_limit"] == 7000

    def test_hsa_individual(self):
        result = check_contribution_limits("hsa_individual", age=40, tax_year=2024)
        assert result["base_limit"] == 4150
        assert result["catch_up_eligible"] is False

    def test_hsa_individual_55_plus(self):
        result = check_contribution_limits("hsa_individual", age=55, tax_year=2024)
        assert result["catch_up_eligible"] is True
        assert result["total_limit"] == 5150  # 4150 + 1000

    def test_hsa_family(self):
        result = check_contribution_limits("hsa_family", age=40, tax_year=2024)
        assert result["base_limit"] == 8300

    def test_fsa_health_no_catch_up(self):
        result = check_contribution_limits("fsa_health", age=60, tax_year=2024)
        assert result["base_limit"] == 3200
        assert result["catch_up_eligible"] is False  # FSA has no catch-up

    def test_fsa_dependent_care(self):
        result = check_contribution_limits("fsa_dependent_care", age=30, tax_year=2024)
        assert result["base_limit"] == 5000

    def test_unknown_account_type(self):
        result = check_contribution_limits("crypto_ira", age=30, tax_year=2024)
        assert "error" in result
        assert "available_types" in result

    def test_2025_limits(self):
        result = check_contribution_limits("401k", age=30, tax_year=2025)
        assert result["base_limit"] == 23500  # 2025 limit


class TestDetectWashSales:
    """Tests for detect_wash_sales()."""

    def test_no_wash_sale(self):
        transactions = [
            {
                "description": "AAPL",
                "date_sold": "2024-03-15",
                "date_acquired": "2024-01-01",
                "proceeds": 900,
                "cost_basis": 1000,
                "gain_loss": -100,
            },
            {
                "description": "AAPL",
                "date_acquired": "2024-05-01",  # 47 days after sale - no wash
            },
        ]
        result = detect_wash_sales(transactions)
        assert result["wash_sales_found"] == 0
        assert result["total_disallowed_loss"] == 0.0

    def test_wash_sale_detected(self):
        transactions = [
            {
                "description": "AAPL",
                "date_sold": "2024-03-15",
                "date_acquired": "2024-01-01",
                "proceeds": 900,
                "cost_basis": 1000,
                "gain_loss": -100,
            },
            {
                "description": "AAPL",
                "date_acquired": "2024-03-20",  # 5 days after - wash sale!
            },
        ]
        result = detect_wash_sales(transactions)
        assert result["wash_sales_found"] == 1
        assert result["total_disallowed_loss"] == 100.0
        assert result["wash_sales"][0]["days_apart"] == 5

    def test_wash_sale_purchase_before_sale(self):
        """Wash sale also applies to purchases 30 days BEFORE the sale."""
        transactions = [
            {
                "description": "MSFT",
                "date_sold": "2024-06-15",
                "date_acquired": "2024-01-01",
                "proceeds": 800,
                "cost_basis": 1000,
                "gain_loss": -200,
            },
            {
                "description": "MSFT",
                "date_acquired": "2024-06-01",  # 14 days before sale - wash sale
            },
        ]
        result = detect_wash_sales(transactions)
        assert result["wash_sales_found"] == 1

    def test_exactly_30_days_is_wash_sale(self):
        transactions = [
            {
                "description": "GOOG",
                "date_sold": "2024-04-01",
                "date_acquired": "2024-01-01",
                "proceeds": 900,
                "cost_basis": 1000,
                "gain_loss": -100,
            },
            {
                "description": "GOOG",
                "date_acquired": "2024-05-01",  # Exactly 30 days
            },
        ]
        result = detect_wash_sales(transactions)
        assert result["wash_sales_found"] == 1

    def test_31_days_not_wash_sale(self):
        transactions = [
            {
                "description": "GOOG",
                "date_sold": "2024-04-01",
                "date_acquired": "2024-01-01",
                "proceeds": 900,
                "cost_basis": 1000,
                "gain_loss": -100,
            },
            {
                "description": "GOOG",
                "date_acquired": "2024-05-02",  # 31 days - safe
            },
        ]
        result = detect_wash_sales(transactions)
        assert result["wash_sales_found"] == 0

    def test_different_securities_not_wash_sale(self):
        transactions = [
            {
                "description": "AAPL",
                "date_sold": "2024-03-15",
                "date_acquired": "2024-01-01",
                "proceeds": 900,
                "cost_basis": 1000,
                "gain_loss": -100,
            },
            {
                "description": "GOOG",
                "date_acquired": "2024-03-16",  # Different security
            },
        ]
        result = detect_wash_sales(transactions)
        assert result["wash_sales_found"] == 0

    def test_gain_not_wash_sale(self):
        """Sales at a gain are not wash sales."""
        transactions = [
            {
                "description": "AAPL",
                "date_sold": "2024-03-15",
                "date_acquired": "2024-01-01",
                "proceeds": 1100,
                "cost_basis": 1000,
                "gain_loss": 100,  # Gain, not loss
            },
            {
                "description": "AAPL",
                "date_acquired": "2024-03-16",
            },
        ]
        result = detect_wash_sales(transactions)
        assert result["wash_sales_found"] == 0

    def test_empty_transactions(self):
        result = detect_wash_sales([])
        assert result["wash_sales_found"] == 0
        assert result["transactions_analyzed"] == 0

    def test_malformed_dates_skipped(self):
        transactions = [
            {
                "description": "AAPL",
                "date_sold": "bad-date",
                "gain_loss": -100,
            },
            {
                "description": "AAPL",
                "date_acquired": "2024-03-16",
            },
        ]
        result = detect_wash_sales(transactions)
        assert result["wash_sales_found"] == 0  # Skipped, not crashed

    def test_multiple_wash_sales(self):
        transactions = [
            {
                "description": "AAPL",
                "date_sold": "2024-03-15",
                "date_acquired": "2024-01-01",
                "proceeds": 900,
                "cost_basis": 1000,
                "gain_loss": -100,
            },
            {
                "description": "AAPL",
                "date_acquired": "2024-03-20",
            },
            {
                "description": "MSFT",
                "date_sold": "2024-06-01",
                "date_acquired": "2024-03-01",
                "proceeds": 400,
                "cost_basis": 600,
                "gain_loss": -200,
            },
            {
                "description": "MSFT",
                "date_acquired": "2024-06-10",
            },
        ]
        result = detect_wash_sales(transactions)
        assert result["wash_sales_found"] == 2
        assert result["total_disallowed_loss"] == 300.0


class TestCalculateFicaTaxes:
    """Tests for calculate_fica_taxes()."""

    def test_basic_wages(self):
        result = calculate_fica_taxes(75000, tax_year=2024)
        ss = result["social_security"]
        med = result["medicare"]

        assert ss["wages_subject"] == 75000
        assert abs(ss["tax"] - 75000 * 0.062) < 0.01
        assert abs(med["tax"] - 75000 * 0.0145) < 0.01

    def test_wages_above_ss_base(self):
        result = calculate_fica_taxes(200000, tax_year=2024)
        ss = result["social_security"]
        med = result["medicare"]

        # SS capped at wage base
        assert ss["wages_subject"] == 168600
        assert abs(ss["tax"] - 168600 * 0.062) < 0.01

        # Medicare on all wages
        assert med["wages_subject"] == 200000

    def test_additional_medicare_single(self):
        result = calculate_fica_taxes(250000, filing_status="single", tax_year=2024)
        add_med = result["additional_medicare"]

        assert add_med["threshold"] == 200000
        assert add_med["wages_over_threshold"] == 50000
        assert abs(add_med["tax"] - 50000 * 0.009) < 0.01

    def test_additional_medicare_mfj(self):
        result = calculate_fica_taxes(300000, filing_status="married_filing_jointly", tax_year=2024)
        add_med = result["additional_medicare"]

        assert add_med["threshold"] == 250000
        assert add_med["wages_over_threshold"] == 50000

    def test_no_additional_medicare_under_threshold(self):
        result = calculate_fica_taxes(150000, filing_status="single", tax_year=2024)
        assert result["additional_medicare"]["tax"] == 0.0

    def test_self_employment_tax(self):
        result = calculate_fica_taxes(0, self_employment_income=100000, tax_year=2024)
        assert result["self_employment_tax"] > 0

        # SE tax on 92.35% of income
        se_income = 100000 * 0.9235
        expected_ss = se_income * 0.124  # 6.2% * 2
        expected_med = se_income * 0.029  # 1.45% * 2
        assert abs(result["self_employment_tax"] - (expected_ss + expected_med)) < 1

    def test_se_tax_with_wages_reduces_ss(self):
        """SE SS tax should only apply to remaining room under wage base."""
        result = calculate_fica_taxes(
            160000,
            self_employment_income=50000,
            tax_year=2024,
        )
        # Wage base is 168600. With 160000 wages, only 8600 of SE income subject to SS
        se_income = 50000 * 0.9235
        ss_room = max(0, 168600 - 160000)
        se_ss_base = min(se_income, ss_room)
        expected_se_ss = se_ss_base * 0.124
        expected_se_med = se_income * 0.029
        assert abs(result["self_employment_tax"] - (expected_se_ss + expected_se_med)) < 1

    def test_zero_income(self):
        result = calculate_fica_taxes(0, tax_year=2024)
        assert result["total_fica"] == 0.0

    def test_2025_wage_base(self):
        result = calculate_fica_taxes(200000, tax_year=2025)
        assert result["social_security"]["wage_base"] == 176100

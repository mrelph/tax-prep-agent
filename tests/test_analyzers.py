"""Tests for tax analyzers."""

import pytest

from tax_agent.models.documents import DocumentType, TaxDocument
from tax_agent.models.taxpayer import FilingStatus


class TestTaxCalculations:
    """Tests for tax calculation logic."""

    def test_tax_bracket_calculation_single(self):
        """Test tax bracket calculation for single filer."""
        from tax_agent.analyzers.implications import TaxAnalyzer

        # Create analyzer and test bracket calculation
        analyzer = TaxAnalyzer(2024)

        # Test with known income amounts
        brackets = analyzer.rules["brackets"]["single"]

        # $50,000 income should be:
        # $11,600 * 10% = $1,160
        # $38,400 * 12% = $4,608 (remaining in 12% bracket)
        # Total = $5,768
        tax = analyzer._calculate_tax_from_brackets(50000, brackets)
        assert abs(tax - 5768) < 1  # Allow small floating point difference

    def test_tax_bracket_calculation_mfj(self):
        """Test tax bracket calculation for married filing jointly."""
        from tax_agent.analyzers.implications import TaxAnalyzer

        analyzer = TaxAnalyzer(2024)
        brackets = analyzer.rules["brackets"]["married_filing_jointly"]

        # $100,000 income should be:
        # $23,200 * 10% = $2,320
        # $71,100 * 12% = $8,532 (rest up to $94,300)
        # $5,700 * 22% = $1,254 (rest up to $100,000)
        # Total = $12,106
        tax = analyzer._calculate_tax_from_brackets(100000, brackets)
        assert abs(tax - 12106) < 1

    def test_standard_deduction_values(self):
        """Test standard deduction values for 2024."""
        from tax_agent.analyzers.implications import load_tax_rules

        rules = load_tax_rules(2024)

        assert rules["standard_deduction"]["single"] == 14600
        assert rules["standard_deduction"]["married_filing_jointly"] == 29200
        assert rules["standard_deduction"]["head_of_household"] == 21900

    def test_income_summary_calculation(self):
        """Test income summary calculation from documents."""
        from tax_agent.analyzers.implications import TaxAnalyzer

        analyzer = TaxAnalyzer(2024)

        # Create mock documents
        w2_doc = TaxDocument(
            id="w2-1",
            tax_year=2024,
            document_type=DocumentType.W2,
            issuer_name="Employer",
            raw_text="",
            file_hash="hash1",
            extracted_data={"box_1": 75000.00, "box_2": 12500.00},
        )

        int_doc = TaxDocument(
            id="int-1",
            tax_year=2024,
            document_type=DocumentType.FORM_1099_INT,
            issuer_name="Bank",
            raw_text="",
            file_hash="hash2",
            extracted_data={"box_1": 500.00},
        )

        documents = [w2_doc, int_doc]
        income = analyzer.calculate_income_summary(documents)

        assert income["wages"] == 75000.00
        assert income["interest"] == 500.00
        assert income["dividends_ordinary"] == 0.0

    def test_withholding_calculation(self):
        """Test withholding calculation from documents."""
        from tax_agent.analyzers.implications import TaxAnalyzer

        analyzer = TaxAnalyzer(2024)

        w2_doc = TaxDocument(
            id="w2-1",
            tax_year=2024,
            document_type=DocumentType.W2,
            issuer_name="Employer",
            raw_text="",
            file_hash="hash1",
            extracted_data={
                "box_2": 12500.00,
                "box_4": 4650.00,
                "box_6": 1087.50,
                "box_17": 4500.00,
            },
        )

        withholding = analyzer.calculate_withholding([w2_doc])

        assert withholding["federal"] == 12500.00
        assert withholding["social_security"] == 4650.00
        assert withholding["medicare"] == 1087.50
        assert withholding["state"] == 4500.00


class TestCapitalGains:
    """Tests for capital gains calculations."""

    def test_long_term_capital_gains_rates(self):
        """Test long-term capital gains rate brackets."""
        from tax_agent.analyzers.implications import load_tax_rules

        rules = load_tax_rules(2024)
        ltcg = rules["capital_gains"]["long_term"]["single"]

        # 0% rate up to $47,025 for single filers
        assert ltcg[0]["rate"] == 0.00
        assert ltcg[0]["max"] == 47025

        # 15% rate from $47,025 to $518,900
        assert ltcg[1]["rate"] == 0.15

        # 20% rate above $518,900
        assert ltcg[2]["rate"] == 0.20

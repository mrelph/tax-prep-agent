"""Tests for tax summary report generation."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tax_agent.reports import (
    _fmt,
    _generate_checklist,
    _pct,
    generate_tax_summary,
    generate_tax_summary_pdf,
)


@pytest.fixture
def sample_analysis():
    """Sample analysis output matching TaxAnalyzer.generate_analysis()."""
    return {
        "tax_year": 2024,
        "filing_status": "single",
        "documents_count": 4,
        "documents_by_type": {
            "W2": 1,
            "1099-INT": 1,
            "1099-DIV": 1,
            "1099-B": 1,
        },
        "income_summary": {
            "wages": 85000.00,
            "interest": 1200.00,
            "dividends_ordinary": 3500.00,
            "dividends_qualified": 2800.00,
            "capital_gains_short": 500.00,
            "capital_gains_long": 4200.00,
            "other": 0.0,
        },
        "total_income": 94400.00,
        "withholding_summary": {
            "federal": 14000.00,
            "state": 5100.00,
            "social_security": 5270.00,
            "medicare": 1232.50,
        },
        "tax_estimate": {
            "total_income": 94400.00,
            "taxable_income": 79800.00,
            "taxable_ordinary_income": 72800.00,
            "standard_deduction": 14600.00,
            "ordinary_income_tax": 11894.00,
            "capital_gains_income": 7000.00,
            "capital_gains_tax": 0.00,
            "total_tax": 11894.00,
        },
        "refund_or_owed": 2106.00,
        "estimated_refund": 2106.00,
        "estimated_owed": 0,
    }


class TestFormatHelpers:
    """Tests for formatting helper functions."""

    def test_fmt_positive(self):
        assert _fmt(1234.56) == "$1,234.56"

    def test_fmt_zero(self):
        assert _fmt(0) == "$0.00"

    def test_fmt_negative(self):
        assert _fmt(-500.00) == "-$500.00"

    def test_fmt_large(self):
        assert _fmt(1000000.00) == "$1,000,000.00"

    def test_pct(self):
        assert _pct(12.5) == "12.5%"

    def test_pct_zero(self):
        assert _pct(0) == "0.0%"


class TestGenerateTaxSummary:
    """Tests for Markdown report generation."""

    def test_contains_title(self, sample_analysis):
        report = generate_tax_summary(sample_analysis)
        assert "Tax Preparation Summary" in report
        assert "2024" in report

    def test_contains_filing_status(self, sample_analysis):
        report = generate_tax_summary(sample_analysis)
        assert "Single" in report

    def test_contains_bottom_line(self, sample_analysis):
        report = generate_tax_summary(sample_analysis)
        assert "Estimated Federal Refund" in report
        assert "$2,106.00" in report

    def test_contains_income_table(self, sample_analysis):
        report = generate_tax_summary(sample_analysis)
        assert "Income Summary" in report
        assert "$85,000.00" in report  # wages
        assert "$1,200.00" in report   # interest

    def test_contains_tax_calculation(self, sample_analysis):
        report = generate_tax_summary(sample_analysis)
        assert "Federal Tax Calculation" in report
        assert "$14,600.00" in report  # standard deduction
        assert "$11,894.00" in report  # total tax

    def test_contains_withholding(self, sample_analysis):
        report = generate_tax_summary(sample_analysis)
        assert "Withholding" in report
        assert "$14,000.00" in report  # federal withholding

    def test_contains_document_inventory(self, sample_analysis):
        report = generate_tax_summary(sample_analysis)
        assert "Document Inventory" in report
        assert "W2" in report

    def test_contains_checklist(self, sample_analysis):
        report = generate_tax_summary(sample_analysis)
        assert "Preparation Checklist" in report

    def test_contains_disclaimer(self, sample_analysis):
        report = generate_tax_summary(sample_analysis)
        assert "informational purposes only" in report

    def test_owed_instead_of_refund(self, sample_analysis):
        sample_analysis["refund_or_owed"] = -800.00
        report = generate_tax_summary(sample_analysis)
        assert "Estimated Federal Tax Owed" in report
        assert "$800.00" in report

    def test_break_even(self, sample_analysis):
        sample_analysis["refund_or_owed"] = 0
        report = generate_tax_summary(sample_analysis)
        assert "break even" in report

    def test_taxpayer_info_included(self, sample_analysis):
        report = generate_tax_summary(
            sample_analysis,
            taxpayer_info={"state": "CA", "dependents": 2},
        )
        assert "CA" in report
        assert "2" in report

    def test_effective_rate_shown(self, sample_analysis):
        report = generate_tax_summary(sample_analysis)
        # 11894 / 94400 = 12.6%
        assert "12.6%" in report

    def test_review_findings_included(self, sample_analysis):
        reviews = [{
            "findings": [{
                "severity": "warning",
                "title": "High withholding",
                "description": "Federal withholding may be too high.",
                "recommendation": "Consider adjusting W-4.",
            }]
        }]
        report = generate_tax_summary(sample_analysis, reviews=reviews)
        assert "Review Findings" in report
        assert "High withholding" in report
        assert "adjusting W-4" in report

    def test_capital_gains_tax_shown_when_nonzero(self, sample_analysis):
        sample_analysis["tax_estimate"]["capital_gains_tax"] = 630.00
        report = generate_tax_summary(sample_analysis)
        assert "Capital Gains Tax" in report
        assert "$630.00" in report

    def test_other_income_shown(self, sample_analysis):
        sample_analysis["income_summary"]["other"] = 5000.00
        report = generate_tax_summary(sample_analysis)
        assert "Other Income" in report
        assert "$5,000.00" in report


class TestGenerateChecklist:
    """Tests for checklist generation."""

    def test_w2_collected(self, sample_analysis):
        items = _generate_checklist(sample_analysis, None, None)
        w2_items = [i for i in items if "W-2" in i]
        assert any("[x]" in i for i in w2_items)

    def test_income_collected(self, sample_analysis):
        items = _generate_checklist(sample_analysis, None, None)
        assert any("[x]" in i and "Income documents" in i for i in items)

    def test_withholding_available(self, sample_analysis):
        items = _generate_checklist(sample_analysis, None, None)
        assert any("[x]" in i and "withholding" in i for i in items)

    def test_not_reviewed_yet(self, sample_analysis):
        items = _generate_checklist(sample_analysis, None, None)
        assert any("[ ]" in i and "not yet reviewed" in i for i in items)

    def test_reviewed_no_errors(self, sample_analysis):
        reviews = [{"findings": [{"severity": "info", "title": "ok"}]}]
        items = _generate_checklist(sample_analysis, None, reviews)
        assert any("[x]" in i and "no errors" in i for i in items)

    def test_reviewed_with_errors(self, sample_analysis):
        reviews = [{"findings": [{"severity": "error", "title": "bad"}]}]
        items = _generate_checklist(sample_analysis, None, reviews)
        assert any("[ ]" in i and "1 error" in i for i in items)

    def test_missing_1098_noted(self, sample_analysis):
        items = _generate_checklist(sample_analysis, None, None)
        assert any("1098" in i and "[ ]" in i for i in items)

    def test_no_income_unchecked(self):
        empty_analysis = {
            "income_summary": {"wages": 0, "interest": 0, "dividends_ordinary": 0,
                              "dividends_qualified": 0, "capital_gains_short": 0,
                              "capital_gains_long": 0, "other": 0},
            "documents_by_type": {},
            "withholding_summary": {"federal": 0},
        }
        items = _generate_checklist(empty_analysis, None, None)
        assert any("[ ]" in i and "No income" in i for i in items)


class TestGeneratePDF:
    """Tests for PDF report generation."""

    def test_pdf_generates_file(self, sample_analysis, tmp_path):
        output = tmp_path / "test_report.pdf"
        result = generate_tax_summary_pdf(sample_analysis, output)
        assert result.exists()
        assert result.suffix == ".pdf"
        assert result.stat().st_size > 0

    def test_pdf_adds_extension(self, sample_analysis, tmp_path):
        output = tmp_path / "test_report"
        result = generate_tax_summary_pdf(sample_analysis, output)
        assert str(result).endswith(".pdf")

    def test_pdf_with_taxpayer_info(self, sample_analysis, tmp_path):
        output = tmp_path / "report.pdf"
        result = generate_tax_summary_pdf(
            sample_analysis, output,
            taxpayer_info={"state": "NY"},
        )
        assert result.exists()

    def test_pdf_with_reviews(self, sample_analysis, tmp_path):
        reviews = [{
            "findings": [
                {"severity": "error", "title": "Missing schedule", "description": "Schedule C required."},
                {"severity": "warning", "title": "Rounding", "description": "Minor rounding."},
            ]
        }]
        output = tmp_path / "report.pdf"
        result = generate_tax_summary_pdf(sample_analysis, output, reviews=reviews)
        assert result.exists()

    def test_pdf_owed_scenario(self, sample_analysis, tmp_path):
        sample_analysis["refund_or_owed"] = -1500.00
        output = tmp_path / "report.pdf"
        result = generate_tax_summary_pdf(sample_analysis, output)
        assert result.exists()

    def test_pdf_zero_capital_gains(self, sample_analysis, tmp_path):
        sample_analysis["income_summary"]["capital_gains_short"] = 0
        sample_analysis["income_summary"]["capital_gains_long"] = 0
        output = tmp_path / "report.pdf"
        result = generate_tax_summary_pdf(sample_analysis, output)
        assert result.exists()

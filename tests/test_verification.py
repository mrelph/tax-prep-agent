"""Tests for verification.py (OutputVerifier logic, mocking get_agent/get_config)."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def verifier():
    """Create an OutputVerifier with mocked dependencies."""
    with patch("tax_agent.verification.get_agent") as mock_agent, \
         patch("tax_agent.verification.get_config") as mock_config:
        mock_config.return_value.tax_year = 2024
        from tax_agent.verification import OutputVerifier
        v = OutputVerifier()
        yield v


class TestVerifyW2:
    """Tests for OutputVerifier._verify_w2()."""

    def test_valid_w2_no_issues(self, verifier):
        data = {
            "box_1": 75000,
            "box_3": 75000,
            "box_4": 4650,   # 6.2% of 75000
            "box_5": 75000,
            "box_6": 1087.50,  # 1.45% of 75000
        }
        issues = verifier._verify_w2(data)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_ss_wages_exceeds_total_wages(self, verifier):
        data = {
            "box_1": 50000,
            "box_3": 80000,  # SS wages > total wages by more than 10%
        }
        issues = verifier._verify_w2(data)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 1
        assert "SS wages" in errors[0]["issue"]

    def test_ss_wages_slightly_above_ok(self, verifier):
        """Within 10% tolerance should not be error."""
        data = {
            "box_1": 75000,
            "box_3": 80000,  # Only 6.7% above - within 10% tolerance
            "box_4": 4960,
        }
        issues = verifier._verify_w2(data)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_ss_tax_mismatch_warning(self, verifier):
        data = {
            "box_1": 75000,
            "box_3": 75000,
            "box_4": 3000,  # Should be ~4650 (6.2%), way off
        }
        issues = verifier._verify_w2(data)
        warnings = [i for i in issues if i["severity"] == "warning"]
        assert any("SS tax" in w["issue"] for w in warnings)

    def test_medicare_tax_mismatch_warning(self, verifier):
        data = {
            "box_1": 75000,
            "box_5": 75000,
            "box_6": 500,  # Should be ~1087.50 (1.45%), way off
        }
        issues = verifier._verify_w2(data)
        warnings = [i for i in issues if i["severity"] == "warning"]
        assert any("Medicare" in w["issue"] for w in warnings)

    def test_zero_wages_no_issues(self, verifier):
        data = {"box_1": 0, "box_3": 0, "box_4": 0}
        issues = verifier._verify_w2(data)
        assert len(issues) == 0

    def test_null_values_no_crash(self, verifier):
        data = {"box_1": None, "box_3": None}
        issues = verifier._verify_w2(data)
        assert len(issues) == 0


class TestVerify1099B:
    """Tests for OutputVerifier._verify_1099b()."""

    def test_matching_summary(self, verifier):
        data = {
            "transactions": [
                {"proceeds": 5000},
                {"proceeds": 3000},
            ],
            "summary": {"total_proceeds": 8000},
        }
        issues = verifier._verify_1099b(data)
        assert len(issues) == 0

    def test_mismatched_summary(self, verifier):
        data = {
            "transactions": [
                {"proceeds": 5000},
                {"proceeds": 3000},
            ],
            "summary": {"total_proceeds": 10000},  # Wrong
        }
        issues = verifier._verify_1099b(data)
        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 1
        assert "proceeds" in errors[0]["issue"].lower()

    def test_within_tolerance(self, verifier):
        data = {
            "transactions": [
                {"proceeds": 5000},
                {"proceeds": 3000.50},
            ],
            "summary": {"total_proceeds": 8000},  # Off by 0.50 - within $1
        }
        issues = verifier._verify_1099b(data)
        assert len(issues) == 0

    def test_no_transactions_no_issue(self, verifier):
        data = {"transactions": [], "summary": {}}
        issues = verifier._verify_1099b(data)
        assert len(issues) == 0

    def test_null_proceeds_treated_as_zero(self, verifier):
        data = {
            "transactions": [
                {"proceeds": None},
                {"proceeds": 5000},
            ],
            "summary": {"total_proceeds": 5000},
        }
        issues = verifier._verify_1099b(data)
        assert len(issues) == 0


class TestVerifyTaxCalculation:
    """Tests for OutputVerifier.verify_tax_calculation()."""

    def test_reasonable_rate(self, verifier):
        result = verifier.verify_tax_calculation(100000, 17000, "single")
        assert result["verified"] is True
        assert len(result["issues"]) == 0

    def test_zero_income(self, verifier):
        result = verifier.verify_tax_calculation(0, 0, "single")
        assert result["verified"] is True

    def test_negative_rate_error(self, verifier):
        result = verifier.verify_tax_calculation(100000, -5000, "single")
        assert result["verified"] is False
        errors = [i for i in result["issues"] if i["severity"] == "error"]
        assert len(errors) == 1

    def test_rate_too_high_warning(self, verifier):
        result = verifier.verify_tax_calculation(100000, 45000, "single")
        assert len(result["issues"]) > 0
        assert any("exceeds" in i["issue"] for i in result["issues"])

    def test_rate_too_low_warning(self, verifier):
        result = verifier.verify_tax_calculation(100000, 2000, "single")
        assert len(result["issues"]) > 0
        assert any("too low" in i["issue"] for i in result["issues"])

    def test_low_rate_ok_for_low_income(self, verifier):
        # $30,000 income with $2000 tax = 6.7% - should be fine
        result = verifier.verify_tax_calculation(30000, 2000, "single")
        assert len(result["issues"]) == 0


class TestVerifyExtractedData:
    """Tests for OutputVerifier.verify_extracted_data()."""

    def test_values_found_in_source(self, verifier):
        data = {"box_1": 75000, "box_2": 12500}
        raw_text = "Box 1: $75,000.00\nBox 2: $12,500.00"
        result = verifier.verify_extracted_data("W2", data, raw_text)
        assert result["verified"] is True
        assert result["confidence"] > 0

    def test_values_not_in_source_warning(self, verifier):
        data = {"box_1": 99999}  # Not in source text
        raw_text = "Box 1: $75,000.00"
        result = verifier.verify_extracted_data("OTHER", data, raw_text)
        assert len(result["issues"]) > 0
        assert result["issues"][0]["severity"] == "warning"

    def test_small_values_not_flagged(self, verifier):
        """Values <= 100 should not be flagged even if missing from source."""
        data = {"box_4": 50}
        raw_text = "Some text without the number 50"
        result = verifier.verify_extracted_data("OTHER", data, raw_text)
        # Small values (<= 100) should not be flagged
        warnings = [i for i in result["issues"] if "not found" in i.get("issue", "")]
        assert len(warnings) == 0

    def test_null_values_skipped(self, verifier):
        data = {"box_1": None, "box_2": None}
        raw_text = "Anything"
        result = verifier.verify_extracted_data("OTHER", data, raw_text)
        assert len(result["issues"]) == 0

    def test_empty_data_half_confidence(self, verifier):
        result = verifier.verify_extracted_data("OTHER", {}, "text")
        assert result["confidence"] == 0.5

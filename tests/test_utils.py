"""Tests for utils.py and additional model coverage."""

import pytest
from datetime import datetime
from enum import Enum

from tax_agent.utils import get_enum_value
from tax_agent.models.documents import (
    DocumentType,
    TaxDocument,
    get_document_folder,
    group_documents_by_folder,
    group_documents_by_year_and_folder,
    SOURCE_DOCUMENTS,
    TAX_RETURNS,
)
from tax_agent.models.returns import (
    ReviewFinding,
    ReviewSeverity,
    TaxReturnReview,
    TaxReturnSummary,
    ReturnType,
)


class TestGetEnumValue:
    """Tests for get_enum_value()."""

    def test_enum_returns_value(self):
        assert get_enum_value(DocumentType.W2) == "W2"

    def test_enum_1099(self):
        assert get_enum_value(DocumentType.FORM_1099_INT) == "1099_INT"

    def test_string_returns_string(self):
        assert get_enum_value("W2") == "W2"

    def test_none_returns_empty(self):
        assert get_enum_value(None) == ""

    def test_int_returns_string(self):
        assert get_enum_value(2024) == "2024"

    def test_custom_enum(self):
        class Color(Enum):
            RED = "red"
        assert get_enum_value(Color.RED) == "red"


class TestGetDocumentFolder:
    """Tests for get_document_folder()."""

    def test_w2_folder(self):
        assert get_document_folder(DocumentType.W2) == "Income/Employment"

    def test_w2g_folder(self):
        assert get_document_folder(DocumentType.W2_G) == "Income/Employment"

    def test_1099_int_folder(self):
        assert get_document_folder(DocumentType.FORM_1099_INT) == "Income/Investments"

    def test_1099_div_folder(self):
        assert get_document_folder(DocumentType.FORM_1099_DIV) == "Income/Investments"

    def test_1099_b_folder(self):
        assert get_document_folder(DocumentType.FORM_1099_B) == "Income/Investments"

    def test_1099_nec_folder(self):
        assert get_document_folder(DocumentType.FORM_1099_NEC) == "Income/Self-Employment"

    def test_1099_misc_folder(self):
        assert get_document_folder(DocumentType.FORM_1099_MISC) == "Income/Self-Employment"

    def test_k1_folder(self):
        assert get_document_folder(DocumentType.K1) == "Income/Self-Employment"

    def test_1099_r_folder(self):
        assert get_document_folder(DocumentType.FORM_1099_R) == "Income/Retirement"

    def test_1099_g_folder(self):
        assert get_document_folder(DocumentType.FORM_1099_G) == "Income/Government"

    def test_1098_folder(self):
        assert get_document_folder(DocumentType.FORM_1098) == "Deductions/Mortgage"

    def test_1098_t_folder(self):
        assert get_document_folder(DocumentType.FORM_1098_T) == "Deductions/Education"

    def test_1098_e_folder(self):
        assert get_document_folder(DocumentType.FORM_1098_E) == "Deductions/Education"

    def test_5498_folder(self):
        assert get_document_folder(DocumentType.FORM_5498) == "Deductions/Retirement"

    def test_1040_folder(self):
        assert get_document_folder(DocumentType.FORM_1040) == "Returns/Federal"

    def test_schedule_a_folder(self):
        assert get_document_folder(DocumentType.SCHEDULE_A) == "Returns/Schedules"

    def test_state_return_folder(self):
        assert get_document_folder(DocumentType.STATE_RETURN) == "Returns/State"

    def test_unknown_returns_other(self):
        assert get_document_folder(DocumentType.UNKNOWN) == "Other"

    def test_string_input(self):
        assert get_document_folder("W2") == "Income/Employment"

    def test_invalid_string_returns_other(self):
        assert get_document_folder("NOT_A_REAL_TYPE") == "Other"


class TestGroupDocumentsByFolder:
    """Tests for group_documents_by_folder()."""

    def _make_doc(self, doc_type, issuer="Test", year=2024):
        return TaxDocument(
            id=f"test-{doc_type}",
            tax_year=year,
            document_type=doc_type,
            issuer_name=issuer,
            raw_text="",
            file_hash=f"hash-{doc_type}",
        )

    def test_empty_list(self):
        result = group_documents_by_folder([])
        assert result == {}

    def test_single_doc(self):
        docs = [self._make_doc(DocumentType.W2)]
        result = group_documents_by_folder(docs)
        assert "Income/Employment" in result
        assert len(result["Income/Employment"]) == 1

    def test_multiple_folders(self):
        docs = [
            self._make_doc(DocumentType.W2),
            self._make_doc(DocumentType.FORM_1099_INT),
            self._make_doc(DocumentType.FORM_1098),
        ]
        result = group_documents_by_folder(docs)
        assert len(result) == 3
        assert "Income/Employment" in result
        assert "Income/Investments" in result
        assert "Deductions/Mortgage" in result

    def test_same_folder_grouped(self):
        docs = [
            self._make_doc(DocumentType.W2, issuer="Employer1"),
            self._make_doc(DocumentType.W2_G, issuer="Casino"),
        ]
        result = group_documents_by_folder(docs)
        assert len(result["Income/Employment"]) == 2


class TestGroupDocumentsByYearAndFolder:
    """Tests for group_documents_by_year_and_folder()."""

    def _make_doc(self, doc_type, year=2024):
        return TaxDocument(
            id=f"test-{doc_type}-{year}",
            tax_year=year,
            document_type=doc_type,
            issuer_name="Test",
            raw_text="",
            file_hash=f"hash-{doc_type}-{year}",
        )

    def test_empty_list(self):
        result = group_documents_by_year_and_folder([])
        assert result == {}

    def test_single_year(self):
        docs = [self._make_doc(DocumentType.W2, 2024)]
        result = group_documents_by_year_and_folder(docs)
        assert 2024 in result
        assert "Income/Employment" in result[2024]

    def test_multiple_years(self):
        docs = [
            self._make_doc(DocumentType.W2, 2023),
            self._make_doc(DocumentType.W2, 2024),
        ]
        result = group_documents_by_year_and_folder(docs)
        assert 2023 in result
        assert 2024 in result


class TestDocumentSets:
    """Tests for SOURCE_DOCUMENTS and TAX_RETURNS sets."""

    def test_w2_is_source(self):
        assert DocumentType.W2 in SOURCE_DOCUMENTS

    def test_1040_is_return(self):
        assert DocumentType.FORM_1040 in TAX_RETURNS

    def test_no_overlap(self):
        assert len(SOURCE_DOCUMENTS & TAX_RETURNS) == 0

    def test_unknown_in_neither(self):
        assert DocumentType.UNKNOWN not in SOURCE_DOCUMENTS
        assert DocumentType.UNKNOWN not in TAX_RETURNS


class TestTaxReturnReview:
    """Tests for TaxReturnReview model."""

    def _make_review(self):
        return TaxReturnReview(
            id="review-1",
            return_summary=TaxReturnSummary(
                return_type=ReturnType.FEDERAL_1040,
                tax_year=2024,
            ),
        )

    def _make_finding(self, severity):
        return ReviewFinding(
            severity=severity,
            category="income",
            title="Test finding",
            description="Test description",
        )

    def test_add_error_increments_count(self):
        review = self._make_review()
        review.add_finding(self._make_finding(ReviewSeverity.ERROR))
        assert review.errors_count == 1
        assert review.warnings_count == 0

    def test_add_warning_increments_count(self):
        review = self._make_review()
        review.add_finding(self._make_finding(ReviewSeverity.WARNING))
        assert review.warnings_count == 1
        assert review.errors_count == 0

    def test_add_suggestion_increments_count(self):
        review = self._make_review()
        review.add_finding(self._make_finding(ReviewSeverity.SUGGESTION))
        assert review.suggestions_count == 1

    def test_add_info_no_increment(self):
        review = self._make_review()
        review.add_finding(self._make_finding(ReviewSeverity.INFO))
        assert review.errors_count == 0
        assert review.warnings_count == 0
        assert review.suggestions_count == 0

    def test_has_critical_issues_true(self):
        review = self._make_review()
        review.add_finding(self._make_finding(ReviewSeverity.ERROR))
        assert review.has_critical_issues is True

    def test_has_critical_issues_false(self):
        review = self._make_review()
        review.add_finding(self._make_finding(ReviewSeverity.WARNING))
        assert review.has_critical_issues is False

    def test_has_critical_issues_empty(self):
        review = self._make_review()
        assert review.has_critical_issues is False

    def test_multiple_findings(self):
        review = self._make_review()
        review.add_finding(self._make_finding(ReviewSeverity.ERROR))
        review.add_finding(self._make_finding(ReviewSeverity.ERROR))
        review.add_finding(self._make_finding(ReviewSeverity.WARNING))
        review.add_finding(self._make_finding(ReviewSeverity.SUGGESTION))
        assert review.errors_count == 2
        assert review.warnings_count == 1
        assert review.suggestions_count == 1
        assert len(review.findings) == 4

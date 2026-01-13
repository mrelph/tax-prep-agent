"""Tests for data models."""

import pytest
from datetime import datetime

from tax_agent.models.documents import DocumentType, TaxDocument, W2Data
from tax_agent.models.taxpayer import FilingStatus, TaxpayerProfile, Dependent


class TestDocumentType:
    """Tests for DocumentType enum."""

    def test_document_types_exist(self):
        """Verify all expected document types exist."""
        assert DocumentType.W2 == "W2"
        assert DocumentType.FORM_1099_INT == "1099_INT"
        assert DocumentType.FORM_1099_DIV == "1099_DIV"
        assert DocumentType.FORM_1099_B == "1099_B"
        assert DocumentType.UNKNOWN == "UNKNOWN"

    def test_document_type_from_string(self):
        """Test creating DocumentType from string."""
        assert DocumentType("W2") == DocumentType.W2
        assert DocumentType("1099_INT") == DocumentType.FORM_1099_INT


class TestTaxDocument:
    """Tests for TaxDocument model."""

    def test_create_tax_document(self):
        """Test creating a basic tax document."""
        doc = TaxDocument(
            id="test-123",
            tax_year=2024,
            document_type=DocumentType.W2,
            issuer_name="Acme Corp",
            raw_text="Sample text",
            file_hash="abc123",
        )

        assert doc.id == "test-123"
        assert doc.tax_year == 2024
        assert doc.document_type == DocumentType.W2
        assert doc.issuer_name == "Acme Corp"
        assert doc.confidence_score == 0.0
        assert doc.needs_review is False

    def test_document_with_extracted_data(self):
        """Test document with extracted data."""
        doc = TaxDocument(
            id="test-456",
            tax_year=2024,
            document_type=DocumentType.W2,
            issuer_name="Acme Corp",
            raw_text="Sample text",
            file_hash="def456",
            extracted_data={"box_1": 75000.00, "box_2": 12500.00},
        )

        assert doc.extracted_data["box_1"] == 75000.00
        assert doc.extracted_data["box_2"] == 12500.00


class TestTaxpayerProfile:
    """Tests for TaxpayerProfile model."""

    def test_create_profile(self):
        """Test creating a taxpayer profile."""
        profile = TaxpayerProfile(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            state="CA",
        )

        assert profile.tax_year == 2024
        assert profile.filing_status == FilingStatus.SINGLE
        assert profile.state == "CA"
        assert profile.num_dependents == 0

    def test_profile_with_dependents(self):
        """Test profile with dependents."""
        profile = TaxpayerProfile(
            tax_year=2024,
            filing_status=FilingStatus.HEAD_OF_HOUSEHOLD,
            state="NY",
            dependents=[
                Dependent(name="Child One", relationship="son"),
                Dependent(name="Child Two", relationship="daughter"),
            ],
        )

        assert profile.num_dependents == 2

    def test_age_calculation(self):
        """Test age calculation from date of birth."""
        profile = TaxpayerProfile(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            state="TX",
            date_of_birth="1990-06-15",
        )

        assert profile.age == 34
        assert profile.is_65_or_older is False

    def test_65_or_older(self):
        """Test 65+ detection."""
        profile = TaxpayerProfile(
            tax_year=2024,
            filing_status=FilingStatus.SINGLE,
            state="FL",
            date_of_birth="1955-01-01",
        )

        assert profile.is_65_or_older is True


class TestW2Data:
    """Tests for W2Data model."""

    def test_create_w2_data(self):
        """Test creating W2 data."""
        w2 = W2Data(
            box_1=75000.00,
            box_2=12500.00,
            box_3=75000.00,
            box_4=4650.00,
            box_5=75000.00,
            box_6=1087.50,
        )

        assert w2.wages_tips_other == 75000.00
        assert w2.federal_income_tax_withheld == 12500.00
        assert w2.social_security_wages == 75000.00

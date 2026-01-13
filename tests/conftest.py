"""Pytest configuration and fixtures."""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_w2_text():
    """Sample W-2 text for testing."""
    return """
    Form W-2 Wage and Tax Statement 2024

    Employer Information:
    Acme Corporation
    123 Main Street
    Anytown, ST 12345
    EIN: 12-3456789

    Employee Information:
    John Doe
    456 Oak Avenue
    Somewhere, ST 67890
    SSN: XXX-XX-1234

    Box 1: Wages, tips, other compensation: $75,000.00
    Box 2: Federal income tax withheld: $12,500.00
    Box 3: Social security wages: $75,000.00
    Box 4: Social security tax withheld: $4,650.00
    Box 5: Medicare wages and tips: $75,000.00
    Box 6: Medicare tax withheld: $1,087.50
    Box 15: State: CA
    Box 16: State wages: $75,000.00
    Box 17: State income tax: $4,500.00
    """


@pytest.fixture
def sample_1099_int_text():
    """Sample 1099-INT text for testing."""
    return """
    Form 1099-INT Interest Income 2024

    PAYER'S name: First National Bank
    PAYER'S TIN: 98-7654321

    RECIPIENT'S name: John Doe
    RECIPIENT'S TIN: XXX-XX-1234

    Box 1: Interest income: $1,234.56
    Box 4: Federal income tax withheld: $0.00
    """


@pytest.fixture
def mock_config(temp_dir, monkeypatch):
    """Create a mock configuration for testing."""
    config_dir = temp_dir / ".tax-agent"
    config_dir.mkdir(parents=True)

    # Set environment to use temp directory
    monkeypatch.setenv("TAX_AGENT_CONFIG_DIR", str(config_dir))

    return config_dir


@pytest.fixture
def sample_pdf_path(temp_dir):
    """Create a sample PDF file path (actual PDF creation would need PyMuPDF)."""
    pdf_path = temp_dir / "sample.pdf"
    # Just create an empty file for path testing
    pdf_path.touch()
    return pdf_path

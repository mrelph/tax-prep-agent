"""Tests for storage/encryption.py (pure functions, minimal mocking)."""

import tempfile
from pathlib import Path

import pytest

from tax_agent.storage.encryption import (
    derive_key,
    hash_content,
    hash_file,
    redact_ein,
    redact_sensitive_data,
    redact_ssn,
)


class TestDeriveKey:
    """Tests for derive_key()."""

    def test_deterministic_with_same_salt(self):
        salt = b"fixed_salt_for_testing_1234567890"
        key1, _ = derive_key("password123", salt)
        key2, _ = derive_key("password123", salt)
        assert key1 == key2

    def test_different_passwords_different_keys(self):
        salt = b"fixed_salt_for_testing_1234567890"
        key1, _ = derive_key("password1", salt)
        key2, _ = derive_key("password2", salt)
        assert key1 != key2

    def test_different_salts_different_keys(self):
        key1, _ = derive_key("password", b"salt_one_1234567890123456")
        key2, _ = derive_key("password", b"salt_two_1234567890123456")
        assert key1 != key2

    def test_random_salt_when_none(self):
        _, salt1 = derive_key("password")
        _, salt2 = derive_key("password")
        assert salt1 != salt2  # Random salt each time

    def test_key_length_32_bytes(self):
        key, _ = derive_key("password")
        assert len(key) == 32

    def test_salt_returned(self):
        _, salt = derive_key("password")
        assert isinstance(salt, bytes)
        assert len(salt) == 32


class TestHashContent:
    """Tests for hash_content()."""

    def test_known_hash(self):
        # SHA-256 of empty bytes
        assert hash_content(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_hello_world(self):
        result = hash_content(b"hello world")
        assert len(result) == 64  # 32 bytes = 64 hex chars
        assert result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"

    def test_deterministic(self):
        assert hash_content(b"test data") == hash_content(b"test data")

    def test_different_content_different_hash(self):
        assert hash_content(b"data1") != hash_content(b"data2")


class TestHashFile:
    """Tests for hash_file()."""

    def test_known_file_content(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test content for hashing")
            f.flush()
            file_hash = hash_file(f.name)

        expected = hash_content(b"test content for hashing")
        assert file_hash == expected

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.flush()
            file_hash = hash_file(f.name)

        assert file_hash == hash_content(b"")

    def test_same_content_same_hash(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f1:
            f1.write(b"identical content")
            f1.flush()
            hash1 = hash_file(f1.name)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f2:
            f2.write(b"identical content")
            f2.flush()
            hash2 = hash_file(f2.name)

        assert hash1 == hash2


class TestRedactSSN:
    """Tests for redact_ssn()."""

    def test_dashed_ssn(self):
        assert redact_ssn("SSN: 123-45-6789") == "SSN: [SSN REDACTED]"

    def test_spaced_ssn(self):
        assert redact_ssn("SSN: 123 45 6789") == "SSN: [SSN REDACTED]"

    def test_bare_nine_digits(self):
        assert redact_ssn("SSN: 123456789") == "SSN: [SSN REDACTED]"

    def test_multiple_ssns(self):
        text = "Employee SSN: 123-45-6789, Spouse: 987-65-4321"
        result = redact_ssn(text)
        assert "123-45-6789" not in result
        assert "987-65-4321" not in result
        assert result.count("[SSN REDACTED]") == 2

    def test_no_ssn_unchanged(self):
        text = "No sensitive data here. Box 1: $75,000.00"
        assert redact_ssn(text) == text

    def test_partial_ssn_unchanged(self):
        # Last 4 digits only should not be redacted (less than 9 digits)
        text = "Last 4: 6789"
        assert redact_ssn(text) == text

    def test_already_redacted(self):
        text = "SSN: XXX-XX-1234"
        result = redact_ssn(text)
        assert "XXX-XX-1234" in result  # Not numeric, should be unchanged


class TestRedactEIN:
    """Tests for redact_ein()."""

    def test_ein_redacted(self):
        assert redact_ein("EIN: 12-3456789") == "EIN: [EIN REDACTED]"

    def test_multiple_eins(self):
        text = "Employer EIN: 12-3456789, Payer EIN: 98-7654321"
        result = redact_ein(text)
        assert "12-3456789" not in result
        assert "98-7654321" not in result

    def test_no_ein_unchanged(self):
        text = "No EIN here, just a phone: 555-123-4567"
        assert redact_ein(text) == text

    def test_ssn_not_redacted_by_ein(self):
        # SSN format (XXX-XX-XXXX) should NOT match EIN pattern (XX-XXXXXXX)
        text = "SSN: 123-45-6789"
        assert redact_ein(text) == text


class TestRedactSensitiveData:
    """Tests for redact_sensitive_data()."""

    def test_both_redacted(self):
        text = "SSN: 123-45-6789, EIN: 12-3456789"
        result = redact_sensitive_data(text)
        assert "[SSN REDACTED]" in result
        assert "[EIN REDACTED]" in result

    def test_ssn_only(self):
        text = "SSN: 123-45-6789, EIN: 12-3456789"
        result = redact_sensitive_data(text, redact_ssn_flag=True, redact_ein_flag=False)
        assert "[SSN REDACTED]" in result
        assert "12-3456789" in result  # EIN kept

    def test_ein_only(self):
        text = "SSN: 123-45-6789, EIN: 12-3456789"
        result = redact_sensitive_data(text, redact_ssn_flag=False, redact_ein_flag=True)
        assert "123-45-6789" in result  # SSN kept
        assert "[EIN REDACTED]" in result

    def test_both_off(self):
        text = "SSN: 123-45-6789, EIN: 12-3456789"
        result = redact_sensitive_data(text, redact_ssn_flag=False, redact_ein_flag=False)
        assert result == text

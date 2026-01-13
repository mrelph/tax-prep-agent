"""Encryption utilities for the tax agent."""

import hashlib
import secrets
from base64 import b64decode, b64encode


def derive_key(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """
    Derive an encryption key from a password using PBKDF2.

    Returns:
        Tuple of (derived_key, salt)
    """
    if salt is None:
        salt = secrets.token_bytes(32)

    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations=600000,  # OWASP recommended minimum
        dklen=32,
    )
    return key, salt


def hash_file(file_path: str) -> str:
    """
    Compute SHA-256 hash of a file.

    Args:
        file_path: Path to the file

    Returns:
        Hex-encoded SHA-256 hash
    """
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def hash_content(content: bytes) -> str:
    """
    Compute SHA-256 hash of content.

    Args:
        content: Bytes to hash

    Returns:
        Hex-encoded SHA-256 hash
    """
    return hashlib.sha256(content).hexdigest()


def redact_ssn(text: str) -> str:
    """
    Redact Social Security Numbers from text.

    Replaces patterns like XXX-XX-XXXX or XXXXXXXXX with [SSN REDACTED].
    """
    import re

    # Pattern for SSN with dashes
    pattern_dashed = r"\b\d{3}-\d{2}-\d{4}\b"
    # Pattern for SSN without dashes
    pattern_nodash = r"\b\d{9}\b"

    text = re.sub(pattern_dashed, "[SSN REDACTED]", text)
    text = re.sub(pattern_nodash, "[SSN REDACTED]", text)
    return text


def redact_ein(text: str) -> str:
    """
    Redact Employer Identification Numbers from text.

    Replaces patterns like XX-XXXXXXX with [EIN REDACTED].
    """
    import re

    pattern = r"\b\d{2}-\d{7}\b"
    return re.sub(pattern, "[EIN REDACTED]", text)


def redact_sensitive_data(text: str, redact_ssn_flag: bool = True, redact_ein_flag: bool = True) -> str:
    """
    Redact sensitive data from text before sending to AI.

    Args:
        text: Text to redact
        redact_ssn_flag: Whether to redact SSNs
        redact_ein_flag: Whether to redact EINs

    Returns:
        Redacted text
    """
    if redact_ssn_flag:
        text = redact_ssn(text)
    if redact_ein_flag:
        text = redact_ein(text)
    return text

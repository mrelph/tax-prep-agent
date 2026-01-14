"""Utility functions for the tax agent."""

from enum import Enum
from typing import Any


def get_enum_value(value: Any) -> str:
    """
    Get string value from an enum or return as-is if already a string.

    This handles cases where enum values may be serialized to strings
    when stored in the database and retrieved later.

    Args:
        value: An enum instance or string

    Returns:
        The string value
    """
    if isinstance(value, Enum):
        return value.value
    return str(value) if value is not None else ""

"""Custom MCP tools for tax calculations and analysis."""

from tax_agent.tools.tax_calculations import (
    calculate_federal_tax,
    check_contribution_limits,
    detect_wash_sales,
    get_tax_brackets,
    get_standard_deduction,
)

__all__ = [
    "calculate_federal_tax",
    "check_contribution_limits",
    "detect_wash_sales",
    "get_tax_brackets",
    "get_standard_deduction",
]

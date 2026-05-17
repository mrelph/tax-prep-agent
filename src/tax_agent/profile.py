"""Taxpayer profile helpers."""

from tax_agent.config import get_config
from tax_agent.models.taxpayer import TaxpayerProfile


def get_profile(tax_year: int | None = None) -> TaxpayerProfile | None:
    """
    Get the taxpayer profile for the given tax year.

    Args:
        tax_year: Tax year to get profile for (defaults to config)

    Returns:
        TaxpayerProfile or None if not set
    """
    from tax_agent.storage.database import get_database

    config = get_config()
    year = tax_year or config.tax_year

    try:
        db = get_database()
        return db.get_taxpayer_profile(year)
    except Exception:
        return None


def get_profile_summary(tax_year: int | None = None) -> str:
    """
    Get a text summary of the taxpayer profile.

    Args:
        tax_year: Tax year to get profile for (defaults to config)

    Returns:
        Profile summary string
    """
    profile = get_profile(tax_year)

    if not profile:
        return "No taxpayer profile configured."

    lines = [
        f"Tax Year: {profile.tax_year}",
        f"Filing Status: {profile.filing_status.value if profile.filing_status else 'Not set'}",
        f"State: {profile.state or 'Not set'}",
    ]

    if profile.dependents:
        lines.append(f"Dependents: {len(profile.dependents)}")

    if profile.is_self_employed:
        lines.append("Self-employed: Yes")

    if profile.has_hsa:
        lines.append("Has HSA: Yes")

    return "\n".join(lines)

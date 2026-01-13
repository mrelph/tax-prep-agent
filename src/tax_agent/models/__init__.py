"""Data models for tax documents, taxpayer profiles, and returns."""

from tax_agent.models.documents import DocumentType, TaxDocument
from tax_agent.models.taxpayer import FilingStatus, TaxpayerProfile

__all__ = ["DocumentType", "TaxDocument", "FilingStatus", "TaxpayerProfile"]

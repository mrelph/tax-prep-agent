"""Tax document models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(str, Enum):
    """Types of tax documents supported."""

    # Source documents (used to prepare returns)
    W2 = "W2"
    W2_G = "W2_G"  # Gambling winnings
    FORM_1099_INT = "1099_INT"  # Interest income
    FORM_1099_DIV = "1099_DIV"  # Dividend income
    FORM_1099_B = "1099_B"  # Brokerage/stock sales
    FORM_1099_NEC = "1099_NEC"  # Non-employee compensation
    FORM_1099_MISC = "1099_MISC"  # Miscellaneous income
    FORM_1099_R = "1099_R"  # Retirement distributions
    FORM_1099_G = "1099_G"  # Government payments (unemployment, tax refunds)
    FORM_1099_K = "1099_K"  # Payment card transactions
    FORM_1098 = "1098"  # Mortgage interest
    FORM_1098_T = "1098_T"  # Tuition statement
    FORM_1098_E = "1098_E"  # Student loan interest
    FORM_5498 = "5498"  # IRA contributions
    K1 = "K1"  # Partnership/S-corp income

    # Completed tax returns (for review)
    FORM_1040 = "1040"  # Federal individual income tax return
    FORM_1040_SR = "1040_SR"  # Federal return for seniors
    FORM_1040_NR = "1040_NR"  # Non-resident alien return
    FORM_1040_X = "1040_X"  # Amended return
    SCHEDULE_A = "SCHEDULE_A"  # Itemized deductions
    SCHEDULE_B = "SCHEDULE_B"  # Interest and dividends
    SCHEDULE_C = "SCHEDULE_C"  # Business income
    SCHEDULE_D = "SCHEDULE_D"  # Capital gains
    SCHEDULE_E = "SCHEDULE_E"  # Rental/royalty income
    SCHEDULE_SE = "SCHEDULE_SE"  # Self-employment tax
    STATE_RETURN = "STATE_RETURN"  # State income tax return

    UNKNOWN = "UNKNOWN"


# Helper to categorize document types
SOURCE_DOCUMENTS = {
    DocumentType.W2, DocumentType.W2_G,
    DocumentType.FORM_1099_INT, DocumentType.FORM_1099_DIV, DocumentType.FORM_1099_B,
    DocumentType.FORM_1099_NEC, DocumentType.FORM_1099_MISC, DocumentType.FORM_1099_R,
    DocumentType.FORM_1099_G, DocumentType.FORM_1099_K,
    DocumentType.FORM_1098, DocumentType.FORM_1098_T, DocumentType.FORM_1098_E,
    DocumentType.FORM_5498, DocumentType.K1,
}

TAX_RETURNS = {
    DocumentType.FORM_1040, DocumentType.FORM_1040_SR, DocumentType.FORM_1040_NR,
    DocumentType.FORM_1040_X,
    DocumentType.SCHEDULE_A, DocumentType.SCHEDULE_B, DocumentType.SCHEDULE_C,
    DocumentType.SCHEDULE_D, DocumentType.SCHEDULE_E, DocumentType.SCHEDULE_SE,
    DocumentType.STATE_RETURN,
}

# Virtual folder categories for document organization
DOCUMENT_CATEGORIES: dict[str, set[DocumentType]] = {
    # Income documents
    "Income/Employment": {DocumentType.W2, DocumentType.W2_G},
    "Income/Investments": {
        DocumentType.FORM_1099_INT,
        DocumentType.FORM_1099_DIV,
        DocumentType.FORM_1099_B,
    },
    "Income/Self-Employment": {
        DocumentType.FORM_1099_NEC,
        DocumentType.FORM_1099_MISC,
        DocumentType.K1,
    },
    "Income/Retirement": {DocumentType.FORM_1099_R},
    "Income/Government": {DocumentType.FORM_1099_G, DocumentType.FORM_1099_K},
    # Deduction documents
    "Deductions/Mortgage": {DocumentType.FORM_1098},
    "Deductions/Education": {DocumentType.FORM_1098_T, DocumentType.FORM_1098_E},
    "Deductions/Retirement": {DocumentType.FORM_5498},
    # Tax returns
    "Returns/Federal": {
        DocumentType.FORM_1040,
        DocumentType.FORM_1040_SR,
        DocumentType.FORM_1040_NR,
        DocumentType.FORM_1040_X,
    },
    "Returns/Schedules": {
        DocumentType.SCHEDULE_A,
        DocumentType.SCHEDULE_B,
        DocumentType.SCHEDULE_C,
        DocumentType.SCHEDULE_D,
        DocumentType.SCHEDULE_E,
        DocumentType.SCHEDULE_SE,
    },
    "Returns/State": {DocumentType.STATE_RETURN},
}


def get_document_folder(doc_type: DocumentType | str) -> str:
    """Get the virtual folder path for a document type."""
    if isinstance(doc_type, str):
        try:
            doc_type = DocumentType(doc_type)
        except ValueError:
            return "Other"

    for folder, types in DOCUMENT_CATEGORIES.items():
        if doc_type in types:
            return folder
    return "Other"


def group_documents_by_folder(
    docs: list["TaxDocument"],
) -> dict[str, list["TaxDocument"]]:
    """Group documents by their virtual folder category."""
    by_folder: dict[str, list[TaxDocument]] = {}
    for doc in docs:
        folder = get_document_folder(doc.document_type)
        if folder not in by_folder:
            by_folder[folder] = []
        by_folder[folder].append(doc)
    return by_folder


def group_documents_by_year_and_folder(
    docs: list["TaxDocument"],
) -> dict[int, dict[str, list["TaxDocument"]]]:
    """Group documents by year, then by folder category."""
    by_year: dict[int, dict[str, list[TaxDocument]]] = {}
    for doc in docs:
        year = doc.tax_year
        folder = get_document_folder(doc.document_type)

        if year not in by_year:
            by_year[year] = {}
        if folder not in by_year[year]:
            by_year[year][folder] = []
        by_year[year][folder].append(doc)
    return by_year


class TaxDocument(BaseModel):
    """Represents a tax document collected from the user."""

    id: str = Field(description="Unique identifier for the document")
    tax_year: int = Field(description="Tax year this document applies to")
    document_type: DocumentType = Field(description="Type of tax document")
    issuer_name: str = Field(description="Name of the entity that issued this document")
    issuer_ein: str | None = Field(default=None, description="Employer/Payer EIN")
    recipient_ssn_last4: str | None = Field(
        default=None, description="Last 4 digits of recipient SSN (for verification)"
    )
    raw_text: str = Field(description="Raw text extracted from the document")
    extracted_data: dict[str, Any] = Field(
        default_factory=dict, description="Structured data extracted from the document"
    )
    file_path: str | None = Field(default=None, description="Original file path")
    file_hash: str = Field(description="SHA-256 hash of the original file")
    confidence_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence in extraction accuracy"
    )
    needs_review: bool = Field(
        default=False, description="Flag indicating if manual review is needed"
    )
    tags: list[str] = Field(
        default_factory=list, description="User-defined tags for document organization"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(use_enum_values=True)


class W2Data(BaseModel):
    """Structured data specific to W-2 forms."""

    wages_tips_other: float = Field(alias="box_1", description="Box 1: Wages, tips, other")
    federal_income_tax_withheld: float = Field(alias="box_2", description="Box 2: Federal tax")
    social_security_wages: float = Field(alias="box_3", description="Box 3: SS wages")
    social_security_tax_withheld: float = Field(alias="box_4", description="Box 4: SS tax")
    medicare_wages: float = Field(alias="box_5", description="Box 5: Medicare wages")
    medicare_tax_withheld: float = Field(alias="box_6", description="Box 6: Medicare tax")
    social_security_tips: float | None = Field(
        default=None, alias="box_7", description="Box 7: SS tips"
    )
    allocated_tips: float | None = Field(
        default=None, alias="box_8", description="Box 8: Allocated tips"
    )
    dependent_care_benefits: float | None = Field(
        default=None, alias="box_10", description="Box 10: Dependent care"
    )
    nonqualified_plans: float | None = Field(
        default=None, alias="box_11", description="Box 11: Nonqualified plans"
    )
    state: str | None = Field(default=None, alias="box_15", description="Box 15: State")
    state_wages: float | None = Field(
        default=None, alias="box_16", description="Box 16: State wages"
    )
    state_income_tax: float | None = Field(
        default=None, alias="box_17", description="Box 17: State tax"
    )
    local_wages: float | None = Field(
        default=None, alias="box_18", description="Box 18: Local wages"
    )
    local_income_tax: float | None = Field(
        default=None, alias="box_19", description="Box 19: Local tax"
    )


class Form1099IntData(BaseModel):
    """Structured data specific to 1099-INT forms."""

    interest_income: float = Field(alias="box_1", description="Box 1: Interest income")
    early_withdrawal_penalty: float | None = Field(
        default=None, alias="box_2", description="Box 2: Early withdrawal penalty"
    )
    interest_on_us_savings_bonds: float | None = Field(
        default=None, alias="box_3", description="Box 3: Interest on US savings bonds"
    )
    federal_income_tax_withheld: float | None = Field(
        default=None, alias="box_4", description="Box 4: Federal tax withheld"
    )
    investment_expenses: float | None = Field(
        default=None, alias="box_5", description="Box 5: Investment expenses"
    )
    foreign_tax_paid: float | None = Field(
        default=None, alias="box_6", description="Box 6: Foreign tax paid"
    )
    tax_exempt_interest: float | None = Field(
        default=None, alias="box_8", description="Box 8: Tax-exempt interest"
    )
    state: str | None = Field(default=None, description="State")
    state_tax_withheld: float | None = Field(default=None, description="State tax withheld")


class Form1099DivData(BaseModel):
    """Structured data specific to 1099-DIV forms."""

    ordinary_dividends: float = Field(alias="box_1a", description="Box 1a: Ordinary dividends")
    qualified_dividends: float | None = Field(
        default=None, alias="box_1b", description="Box 1b: Qualified dividends"
    )
    capital_gain_distributions: float | None = Field(
        default=None, alias="box_2a", description="Box 2a: Capital gain distributions"
    )
    unrecap_section_1250_gain: float | None = Field(
        default=None, alias="box_2b", description="Box 2b: Unrecap. Sec. 1250 gain"
    )
    section_1202_gain: float | None = Field(
        default=None, alias="box_2c", description="Box 2c: Section 1202 gain"
    )
    collectibles_gain: float | None = Field(
        default=None, alias="box_2d", description="Box 2d: Collectibles (28%) gain"
    )
    nondividend_distributions: float | None = Field(
        default=None, alias="box_3", description="Box 3: Nondividend distributions"
    )
    federal_income_tax_withheld: float | None = Field(
        default=None, alias="box_4", description="Box 4: Federal tax withheld"
    )
    foreign_tax_paid: float | None = Field(
        default=None, alias="box_7", description="Box 7: Foreign tax paid"
    )
    exempt_interest_dividends: float | None = Field(
        default=None, alias="box_12", description="Box 12: Exempt-interest dividends"
    )


class Form1099BTransaction(BaseModel):
    """A single transaction from a 1099-B form."""

    description: str = Field(description="Description of property sold")
    date_acquired: str | None = Field(default=None, description="Date acquired")
    date_sold: str = Field(description="Date sold")
    proceeds: float = Field(description="Proceeds from sale")
    cost_basis: float | None = Field(default=None, description="Cost or other basis")
    wash_sale_loss_disallowed: float | None = Field(
        default=None, description="Wash sale loss disallowed"
    )
    gain_loss: float | None = Field(default=None, description="Gain or loss")
    is_short_term: bool | None = Field(default=None, description="Short-term vs long-term")
    is_covered: bool = Field(default=True, description="Whether basis reported to IRS")


class Form1099BData(BaseModel):
    """Structured data specific to 1099-B forms."""

    transactions: list[Form1099BTransaction] = Field(
        default_factory=list, description="List of transactions"
    )
    total_proceeds: float = Field(default=0.0, description="Total proceeds")
    total_cost_basis: float | None = Field(default=None, description="Total cost basis")
    total_wash_sale_disallowed: float | None = Field(
        default=None, description="Total wash sale losses disallowed"
    )
    federal_income_tax_withheld: float | None = Field(
        default=None, description="Federal tax withheld"
    )

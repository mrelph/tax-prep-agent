"""Tax return models for review functionality."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ReturnType(str, Enum):
    """Type of tax return."""

    FEDERAL_1040 = "federal_1040"
    STATE = "state"


class ReviewSeverity(str, Enum):
    """Severity level for review findings."""

    ERROR = "error"  # Definite mistake that needs correction
    WARNING = "warning"  # Potential issue that should be investigated
    SUGGESTION = "suggestion"  # Optimization opportunity
    INFO = "info"  # Informational note


class ReviewFinding(BaseModel):
    """A finding from tax return review."""

    severity: ReviewSeverity
    category: str = Field(description="Category of finding (e.g., 'income', 'deduction', 'credit')")
    title: str = Field(description="Brief title of the finding")
    description: str = Field(description="Detailed description of the issue")
    line_reference: str | None = Field(
        default=None, description="Reference to specific line on form"
    )
    expected_value: str | None = Field(default=None, description="What the value should be")
    actual_value: str | None = Field(default=None, description="What the value is on the return")
    potential_impact: float | None = Field(
        default=None, description="Estimated tax impact in dollars"
    )
    source_document_id: str | None = Field(
        default=None, description="ID of related source document"
    )
    recommendation: str | None = Field(default=None, description="Recommended action")


class TaxReturnSummary(BaseModel):
    """Summary of a tax return extracted for review."""

    return_type: ReturnType
    tax_year: int
    filing_status: str | None = None

    # Income
    total_income: float | None = None
    wages: float | None = None
    interest_income: float | None = None
    dividend_income: float | None = None
    capital_gains: float | None = None
    other_income: float | None = None

    # Adjustments
    total_adjustments: float | None = None
    agi: float | None = None  # Adjusted Gross Income

    # Deductions
    standard_deduction: float | None = None
    itemized_deductions: float | None = None
    deduction_used: str | None = Field(
        default=None, description="'standard' or 'itemized'"
    )
    taxable_income: float | None = None

    # Tax and credits
    tax_before_credits: float | None = None
    total_credits: float | None = None
    other_taxes: float | None = None
    total_tax: float | None = None

    # Payments and refund
    total_payments: float | None = None
    federal_withholding: float | None = None
    estimated_payments: float | None = None
    refund_amount: float | None = None
    amount_owed: float | None = None

    # State-specific (if state return)
    state: str | None = None
    state_taxable_income: float | None = None
    state_tax: float | None = None
    state_withholding: float | None = None
    state_refund: float | None = None
    state_amount_owed: float | None = None


class TaxReturnReview(BaseModel):
    """Complete review of a tax return."""

    id: str
    return_summary: TaxReturnSummary
    findings: list[ReviewFinding] = Field(default_factory=list)
    overall_assessment: str | None = Field(
        default=None, description="Overall assessment of the return"
    )
    errors_count: int = 0
    warnings_count: int = 0
    suggestions_count: int = 0
    estimated_additional_refund: float | None = Field(
        default=None, description="Potential additional refund if suggestions followed"
    )
    reviewed_at: datetime = Field(default_factory=datetime.now)
    source_documents_checked: list[str] = Field(
        default_factory=list, description="IDs of source documents used in review"
    )

    def add_finding(self, finding: ReviewFinding) -> None:
        """Add a finding and update counts."""
        self.findings.append(finding)
        if finding.severity == ReviewSeverity.ERROR:
            self.errors_count += 1
        elif finding.severity == ReviewSeverity.WARNING:
            self.warnings_count += 1
        elif finding.severity == ReviewSeverity.SUGGESTION:
            self.suggestions_count += 1

    @property
    def has_critical_issues(self) -> bool:
        """Check if there are any errors."""
        return self.errors_count > 0

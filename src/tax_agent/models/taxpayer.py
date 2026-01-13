"""Taxpayer profile models."""

from enum import Enum

from pydantic import BaseModel, Field


class FilingStatus(str, Enum):
    """IRS filing status options."""

    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "married_filing_jointly"
    MARRIED_FILING_SEPARATELY = "married_filing_separately"
    HEAD_OF_HOUSEHOLD = "head_of_household"
    QUALIFYING_SURVIVING_SPOUSE = "qualifying_surviving_spouse"


class Dependent(BaseModel):
    """Information about a dependent."""

    name: str = Field(description="Name of the dependent")
    relationship: str = Field(description="Relationship to taxpayer")
    date_of_birth: str | None = Field(default=None, description="Date of birth (YYYY-MM-DD)")
    ssn_last4: str | None = Field(default=None, description="Last 4 of SSN")
    months_lived_with_you: int = Field(default=12, ge=0, le=12)
    is_student: bool = Field(default=False)
    is_disabled: bool = Field(default=False)


class TaxpayerProfile(BaseModel):
    """Profile information for the taxpayer."""

    tax_year: int = Field(description="Tax year this profile applies to")
    filing_status: FilingStatus = Field(description="IRS filing status")
    state: str = Field(description="State of residence (2-letter code)")
    city: str | None = Field(default=None, description="City of residence")

    # Personal info (for tax calculations, not stored with PII)
    date_of_birth: str | None = Field(default=None, description="Date of birth (YYYY-MM-DD)")
    is_blind: bool = Field(default=False, description="Legally blind")
    spouse_date_of_birth: str | None = Field(
        default=None, description="Spouse DOB if married filing jointly"
    )
    spouse_is_blind: bool = Field(default=False)

    # Dependents
    dependents: list[Dependent] = Field(default_factory=list)

    # Residence info
    months_in_state: int = Field(default=12, ge=0, le=12, description="Months lived in state")
    is_part_year_resident: bool = Field(default=False)
    previous_state: str | None = Field(
        default=None, description="Previous state if part-year resident"
    )

    # Special situations
    is_self_employed: bool = Field(default=False)
    has_hsa: bool = Field(default=False, description="Has Health Savings Account")
    has_foreign_accounts: bool = Field(
        default=False, description="Has foreign bank accounts (FBAR)"
    )
    is_covered_by_employer_retirement: bool = Field(
        default=False, description="Covered by employer retirement plan"
    )

    @property
    def age(self) -> int | None:
        """Calculate age based on date of birth and tax year."""
        if not self.date_of_birth:
            return None
        birth_year = int(self.date_of_birth.split("-")[0])
        return self.tax_year - birth_year

    @property
    def is_65_or_older(self) -> bool:
        """Check if taxpayer is 65 or older."""
        age = self.age
        return age is not None and age >= 65

    @property
    def spouse_is_65_or_older(self) -> bool:
        """Check if spouse is 65 or older."""
        if not self.spouse_date_of_birth:
            return False
        birth_year = int(self.spouse_date_of_birth.split("-")[0])
        return (self.tax_year - birth_year) >= 65

    @property
    def num_dependents(self) -> int:
        """Count of dependents."""
        return len(self.dependents)

    class Config:
        use_enum_values = True

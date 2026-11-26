from enum import StrEnum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class DocumentType(StrEnum):
    LOAN = 'loan_agreement'
    PASSBOOK = 'bank_passbook'
    SCHEME = 'government_scheme_letter'
    SCHEDULE = 'repayment_schedule'
    UNKNOWN = 'unknown'


class Bilingual(Contract):
    en: str
    kn: str


DISCLAIMER = Bilingual(
    en='Educational/explanatory aid, not certified legal or financial advice; verify with official bank/lender representatives.',
    kn='ಇದು ಶೈಕ್ಷಣಿಕ ವಿವರಣೆಯ ಸಹಾಯ ಮಾತ್ರ; ಪ್ರಮಾಣೀಕೃತ ಕಾನೂನು ಅಥವಾ ಹಣಕಾಸು ಸಲಹೆಯಲ್ಲ. ಅಧಿಕೃತ ಬ್ಯಾಂಕ್ ಅಥವಾ ಸಾಲದಾತರ ಪ್ರತಿನಿಧಿಗಳೊಂದಿಗೆ ಪರಿಶೀಲಿಸಿ.')


class Classification(Contract):
    document_type: DocumentType
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]


class FinancialFields(Contract):
    principal: float | None = Field(default=None, ge=0)
    interest_rate: float | None = Field(default=None, ge=0)
    interest_basis: Literal['flat', 'reducing', 'effective', 'unknown'] = 'unknown'
    rate_period: Literal['annual', 'monthly', 'unknown'] = 'unknown'
    tenure: float | None = Field(default=None, ge=0, description='Months, only when units are explicit')
    instalment_amount: float | None = Field(default=None, ge=0)
    fees: float | None = Field(default=None, ge=0)
    penalties: float | None = Field(default=None, ge=0, description='Currency charges only, not percentages')
    insurance_charges: float | None = Field(default=None, ge=0)
    lender_present: bool = False
    microfinance_stated: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    blank_fields: list[str] = Field(default_factory=list)
    evidence: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class RedFlag(Contract):
    rule_id: str
    severity: Literal['high', 'medium', 'review']
    reason: Bilingual
    evidence: str
    reference_ids: list[str]
    applicability: str = 'Review prompt; verify document completeness, lender category and loan date.'


class RBIReference(Contract):
    id: str
    title: str
    summary: str
    url: str
    section: str
    scope: str
    verified_on: str
    keywords: list[str]


class Explanation(Contract):
    summary: Bilingual
    steps: list[Bilingual] = Field(min_length=3, max_length=5)
    fact_ids: list[str]
    reference_ids: list[str]
    mode: Literal['external_grounded', 'offline_template', 'fallback_template']


class AudioResult(Contract):
    status: Literal['available', 'unavailable']
    mime_type: str | None = None
    base64: str | None = None
    message: str | None = None


class AnalysisResult(Contract):
    classification: Classification
    redacted_text: str
    redaction_counts: dict[str, int]
    fields: FinancialFields
    red_flags: list[RedFlag]
    rbi_citations: list[RBIReference]
    explanation: Explanation
    audio: AudioResult
    disclaimer: Bilingual = DISCLAIMER
    stage_timings_ms: dict[str, float]
    warnings: list[str]

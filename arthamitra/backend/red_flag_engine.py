"""Auditable review rules, never LLM-produced legal conclusions.

RF01 annual rate > configured heuristic; RF02 flat basis without APR;
RF03 explicit upfront deduction; RF04 explicit mandatory insurance;
RF05 penal interest clause; RF06 positive prepayment charge;
RF07 missing lender in agreement; RF08 explicitly blank fields;
RF09 missing core fields; RF10 KFS not found in agreement;
RF11 late charge on entire principal; RF12 missing rate period.
Missing-page signals do not establish absence from a complete agreement.
"""
import re
from backend.schemas import Bilingual, DocumentType, FinancialFields, RedFlag

REASONS = {
    'RF01': ('The stated annual rate exceeds the configured review threshold; this threshold is not an RBI cap.', 'ನಮೂದಿಸಿದ ವಾರ್ಷಿಕ ಬಡ್ಡಿ ದರವು ಪರಿಶೀಲನಾ ಮಿತಿಗಿಂತ ಹೆಚ್ಚಿದೆ. ಈ ಮಿತಿ ಆರ್‌ಬಿಐ ನಿಗದಿಪಡಿಸಿದ ಗರಿಷ್ಠ ದರವಲ್ಲ.'),
    'RF02': ('A flat rate is stated without an APR figure; ask for the total annual cost.', 'ಒಟ್ಟು ವಾರ್ಷಿಕ ವೆಚ್ಚದ ದರವಿಲ್ಲದೆ ಫ್ಲಾಟ್ ಬಡ್ಡಿ ದರ ನೀಡಲಾಗಿದೆ. ಒಟ್ಟು ವಾರ್ಷಿಕ ವೆಚ್ಚವನ್ನು ಕೇಳಿ.'),
    'RF03': ('An upfront deduction is stated; ask how much money will actually be disbursed.', 'ಮುಂಗಡ ಕಡಿತ ಉಲ್ಲೇಖಿಸಲಾಗಿದೆ. ಕೈಗೆ ಸಿಗುವ ನಿಜವಾದ ಮೊತ್ತವನ್ನು ಕೇಳಿ.'),
    'RF04': ('Insurance is described as compulsory; ask about consent, coverage and separate charges.', 'ವಿಮೆಯನ್ನು ಕಡ್ಡಾಯವೆಂದು ಹೇಳಲಾಗಿದೆ. ಒಪ್ಪಿಗೆ, ರಕ್ಷಣೆ ಮತ್ತು ಪ್ರತ್ಯೇಕ ಶುಲ್ಕದ ಬಗ್ಗೆ ಕೇಳಿ.'),
    'RF05': ('A penal-interest clause is present; ask whether it adds interest instead of a disclosed charge.', 'ದಂಡದ ಬಡ್ಡಿಯ ಷರತ್ತು ಇದೆ. ಪ್ರತ್ಯೇಕ ಶುಲ್ಕದ ಬದಲು ಹೆಚ್ಚುವರಿ ಬಡ್ಡಿ ಹಾಕಲಾಗುತ್ತದೆಯೇ ಎಂದು ಕೇಳಿ.'),
    'RF06': ('A prepayment charge is stated; ask which rule permits it for this loan.', 'ಮುಂಗಡ ಮರುಪಾವತಿ ಶುಲ್ಕ ಉಲ್ಲೇಖಿಸಲಾಗಿದೆ. ಈ ಸಾಲಕ್ಕೆ ಅದನ್ನು ಅನುಮತಿಸುವ ನಿಯಮವನ್ನು ಕೇಳಿ.'),
    'RF07': ('Lender details were not found in the supplied agreement text; check all pages.', 'ನೀಡಿದ ಒಪ್ಪಂದದ ಪಠ್ಯದಲ್ಲಿ ಸಾಲದಾತರ ವಿವರಗಳು ಕಂಡುಬಂದಿಲ್ಲ. ಎಲ್ಲಾ ಪುಟಗಳನ್ನು ಪರಿಶೀಲಿಸಿ.'),
    'RF08': ('Explicitly blank fields were found; have them completed and verified before signing.', 'ಖಾಲಿ ಜಾಗಗಳು ಕಂಡುಬಂದಿವೆ. ಸಹಿ ಮಾಡುವ ಮೊದಲು ಅವುಗಳನ್ನು ತುಂಬಿಸಿ ಪರಿಶೀಲಿಸಿ.'),
    'RF09': ('Some core loan fields could not be extracted; verify the original document.', 'ಸಾಲದ ಕೆಲವು ಮುಖ್ಯ ವಿವರಗಳನ್ನು ಓದಲು ಸಾಧ್ಯವಾಗಿಲ್ಲ. ಮೂಲ ದಾಖಲೆಯನ್ನು ಪರಿಶೀಲಿಸಿ.'),
    'RF10': ('A KFS was not identified in the supplied agreement text; request it if applicable.', 'ನೀಡಿದ ಒಪ್ಪಂದದಲ್ಲಿ ಮುಖ್ಯ ಅಂಶಗಳ ಪತ್ರ ಕಂಡುಬಂದಿಲ್ಲ. ಅನ್ವಯಿಸಿದರೆ ಅದನ್ನು ಕೇಳಿ.'),
    'RF11': ('Late charges appear to apply to the entire loan; ask whether only the overdue amount is charged.', 'ವಿಳಂಬ ಶುಲ್ಕವನ್ನು ಸಂಪೂರ್ಣ ಸಾಲದ ಮೇಲೆ ಹಾಕುವ ಉಲ್ಲೇಖವಿದೆ. ಬಾಕಿಯಾದ ಕಂತಿನ ಮೇಲಷ್ಟೇ ಶುಲ್ಕವೇ ಎಂದು ಕೇಳಿ.'),
    'RF12': ('The interest-rate period is unclear; ask whether the rate is monthly or annual.', 'ಬಡ್ಡಿ ದರದ ಅವಧಿ ಸ್ಪಷ್ಟವಾಗಿಲ್ಲ. ಅದು ಮಾಸಿಕವೇ ಅಥವಾ ವಾರ್ಷಿಕವೇ ಎಂದು ಕೇಳಿ.'),
}


def positive_clause(text: str, pattern: str) -> str | None:
    for clause in re.split(r'[\n;!?]|(?<!\d)\.(?!\d)', text):
        if re.search(pattern, clause, re.I) and not re.search(r'(?i)\b(?:no|not|nil|none|zero|without|waived|optional)\b|ಇಲ್ಲ|ಐಚ್ಛಿಕ|[:=]\s*0(?:\.0+)?\s*(?:%|$)', clause):
            return clause.strip()
    return None


def detect_flags(text: str, fields: FinancialFields, kind: DocumentType, high_rate_threshold: float = 36) -> list[RedFlag]:
    if kind not in (DocumentType.LOAN, DocumentType.SCHEDULE):
        return []
    result = []

    def add(rule, evidence, refs=(), severity='review'):
        en, kn = REASONS[rule]
        result.append(RedFlag(rule_id=rule, severity=severity, reason=Bilingual(en=en, kn=kn), evidence=evidence, reference_ids=list(refs)))

    if fields.interest_rate is not None and fields.rate_period == 'annual' and fields.interest_rate > high_rate_threshold:
        add('RF01', fields.evidence.get('interest_rate', 'Extracted annual interest rate'), ['RBI-PRICING'], 'medium')
    if fields.interest_basis == 'flat' and not re.search(r'(?i)\bAPR\s*[:=]?\s*\d', text):
        add('RF02', fields.evidence.get('interest_rate', 'Flat rate stated'), ['RBI-KFS'])
    patterns = {
        'RF03': (r'(?:fee|charge|ಶುಲ್ಕ).{0,50}(?:deduct|upfront|ಕಡಿತ)|(?:deduct|upfront).{0,50}(?:fee|charge)', ['RBI-KFS']),
        'RF04': (r'(?:mandatory|compulsory|required).{0,30}insurance|insurance.{0,30}(?:mandatory|compulsory|required)|ಕಡ್ಡಾಯ ವಿಮೆ|ವಿಮೆ ಕಡ್ಡಾಯ', ['RBI-CONSENT']),
        'RF05': (r'penal interest|ದಂಡದ ಬಡ್ಡಿ', ['RBI-PENAL']),
        'RF06': (r'pre[ -]?payment (?:penalty|charge|fee)|ಮುಂಗಡ ಮರುಪಾವತಿ ಶುಲ್ಕ', ['RBI-MICRO-PREPAY'] if fields.microfinance_stated else []),
        'RF11': (r'(?:late|penal|penalty).{0,60}(?:entire|whole|full) (?:loan|principal)', ['RBI-MICRO-PREPAY', 'RBI-PENAL']),
    }
    for rule, (pattern, refs) in patterns.items():
        evidence = positive_clause(text, pattern)
        if evidence:
            add(rule, evidence, refs, 'high' if rule in ('RF04', 'RF05', 'RF11') else 'medium')
    if kind == DocumentType.LOAN and not fields.lender_present:
        add('RF07', 'No usable lender label in supplied text')
    if fields.blank_fields:
        add('RF08', ', '.join(fields.blank_fields), severity='high')
    if fields.missing_fields:
        add('RF09', ', '.join(fields.missing_fields), ['RBI-KFS'])
    if kind == DocumentType.LOAN and not re.search(r'(?i)\bkfs\b|key facts? statement|ಮುಖ್ಯ ಅಂಶಗಳ', text):
        add('RF10', 'KFS not identified in supplied text', ['RBI-KFS'])
    if fields.interest_rate is not None and fields.rate_period == 'unknown':
        add('RF12', fields.evidence.get('interest_rate', 'Rate without a period'), ['RBI-KFS'])
    return sorted(result, key=lambda flag: flag.rule_id)

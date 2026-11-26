"""Conservative bilingual label extraction; conflicting values abstain.

Amounts are INR only; no EMI/APR inference from incomplete cash flows. Evidence
is taken from already redacted text. Table cells without labels need review.
"""
import re
from backend.pii_redactor import normalize
from backend.schemas import FinancialFields, DocumentType

LABELS = {
    'principal': r'principal|loan amount|ಅಸಲು|ಸಾಲದ ಮೊತ್ತ',
    'interest_rate': r'interest rate|ಬಡ್ಡಿ ದರ|APR',
    'tenure': r'tenure|ಅವಧಿ',
    'instalment_amount': r'EMI|instalment amount|installment amount|ಕಂತು',
    'fees': r'processing fee|upfront fee|ಸಂಸ್ಕರಣಾ ಶುಲ್ಕ',
    'penalties': r'late fee|penalty amount|ವಿಳಂಬ ಶುಲ್ಕ',
    'insurance_charges': r'insurance charge|insurance premium|ವಿಮಾ ಶುಲ್ಕ',
}
NUMBER = r'(\d[\d,]*(?:\.\d+)?)'


def extract_fields(text: str, document_type: DocumentType) -> FinancialFields:
    text = normalize(text)
    values, evidence, warnings, blanks = {}, {}, [], []
    for field, aliases in LABELS.items():
        matches = list(re.finditer(rf'(?im)^[ \t]*(?:{aliases})[ \t]*[:=][ \t]*([^\n]*)', text))
        found = []
        for match in matches:
            value_text = match.group(1).strip()
            if re.fullmatch(r'[_ .-]*|blank|ಖಾಲಿ', value_text, re.I):
                blanks.append(field)
                continue
            number = re.match(rf'(?i)(?:INR|Rs\.?|ರೂ\.?|₹)?\s*{NUMBER}', value_text)
            if not number:
                continue
            tail = value_text[number.end():].strip()
            value = float(number.group(1).replace(',', ''))
            if field == 'interest_rate' and not tail.startswith('%'):
                continue
            if field == 'tenure':
                if re.match(r'(?i)(?:years?|ವರ್ಷ)', tail):
                    value *= 12
                elif not re.match(r'(?i)(?:months?|ತಿಂಗಳು)', tail):
                    warnings.append('Tenure unit is unclear; verify it with the lender.')
                    continue
            if field not in ('interest_rate', 'tenure') and tail.startswith('%'):
                warnings.append(f'{field} is a percentage; no currency amount inferred.')
                continue
            if value > 1e10:
                warnings.append(f'{field} is outside supported numeric range; verify the scan.')
                continue
            found.append((value, match.group(0).strip()))
        if len(set(v for v, _ in found)) == 1:
            values[field], evidence[field] = found[0]
        elif found:
            warnings.append(f'Conflicting {field} values; extraction abstained.')
    rate_line = evidence.get('interest_rate', '').lower()
    basis = 'effective' if re.search(r'\bapr\b|effective', rate_line) else 'flat' if 'flat' in rate_line else 'reducing' if 'reducing' in rate_line else 'unknown'
    period = 'annual' if re.search(r'per annum|annual|p\.a\.|ವಾರ್ಷಿಕ|\bapr\b', rate_line) else 'monthly' if re.search(r'per month|monthly|ಮಾಸಿಕ', rate_line) else 'unknown'
    lender = re.search(r'(?im)^[ \t]*(?:lender|bank|ಸಾಲದಾತ|ಬ್ಯಾಂಕ್)[ \t]*:[ \t]*([^\n]+)', text)
    lender_present = bool(lender and re.search(r'[A-Za-z\u0c80-\u0cff]', lender.group(1)) and lender.group(1).strip().lower() not in ('blank', 'unknown'))
    for match in re.finditer(r'(?im)^\s*(signature|ಸಹಿ|amount)\s*:\s*([_ .-]*)$', text):
        blanks.append(match.group(1).lower())
    required = ['principal', 'interest_rate', 'tenure', 'instalment_amount'] if document_type in (DocumentType.LOAN, DocumentType.SCHEDULE) else []
    return FinancialFields(**values, interest_basis=basis, rate_period=period,
        lender_present=lender_present, microfinance_stated=bool(re.search(r'(?i)\bmicrofinance\b|ಕಿರುಸಾಲ', text)),
        missing_fields=[f for f in required if f not in values], blank_fields=sorted(set(blanks)), evidence=evidence, warnings=warnings)

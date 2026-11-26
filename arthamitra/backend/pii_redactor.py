"""Conservative identifier masking. Never retain raw matches in diagnostics.

Checksums classify identifiers, but invalid checksums NEVER exempt a candidate
from masking: OCR errors and synthetic identifiers are still sensitive.
"""
import re
import unicodedata
from dataclasses import dataclass

_D = ((0,1,2,3,4,5,6,7,8,9),(1,2,3,4,0,6,7,8,9,5),(2,3,4,0,1,7,8,9,5,6),(3,4,0,1,2,8,9,5,6,7),(4,0,1,2,3,9,5,6,7,8),(5,9,8,7,6,0,4,3,2,1),(6,5,9,8,7,1,0,4,3,2),(7,6,5,9,8,2,1,0,4,3),(8,7,6,5,9,3,2,1,0,4),(9,8,7,6,5,4,3,2,1,0))
_P = ((0,1,2,3,4,5,6,7,8,9),(1,5,7,6,2,8,3,0,9,4),(5,8,0,3,7,9,6,1,4,2),(8,9,1,6,0,4,3,5,2,7),(9,4,5,3,1,2,6,8,7,0),(4,2,8,6,5,7,3,9,0,1),(2,7,9,3,8,0,6,4,1,5),(7,0,4,6,9,1,3,2,5,8))


def normalize(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)
    return ''.join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in text if c not in '\u200b\u200c\u200d\ufeff')


def valid_aadhaar(value: str) -> bool:
    digits = re.sub(r'\D', '', normalize(value))
    if not re.fullmatch(r'[2-9]\d{11}', digits):
        return False
    checksum = 0
    for i, char in enumerate(reversed(digits)):
        checksum = _D[checksum][_P[i % 8][int(char)]]
    return checksum == 0


def valid_card(value: str) -> bool:
    digits = re.sub(r'\D', '', normalize(value))
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, char in enumerate(reversed(digits)):
        n = int(char) * (2 if i % 2 else 1)
        total += n - 9 if n > 9 else n
    return total % 10 == 0


def valid_ifsc(value: str) -> bool:
    return bool(re.fullmatch(r'[A-Z]{4}0[A-Z0-9]{6}', value.upper()))


@dataclass(frozen=True)
class RedactionResult:
    text: str
    counts: dict[str, int]


class PIIRedactor:
    # Label-scoped masking also catches OCR-corrupted / short identifiers and names.
    labels = r'(?i)(?:aadhaar|aadhar|uid|account(?:\s*(?:number|no\.?))?|a/c(?:\s*no\.?)?|mobile|phone|telephone|ifsc|pan|card(?:\s*number)?|borrower(?:\s*name)?|customer(?:\s*name)?|beneficiary(?:\s*name)?|address|ಹೆಸರು|ವಿಳಾಸ|ಖಾತೆ\s*ಸಂಖ್ಯೆ|ಆಧಾರ್|ಮೊಬೈಲ್)\s*[:=]\s*[^\n;|]+'
    patterns = (
        ('LABELLED_PII', labels),
        ('EMAIL', r'(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b'),
        ('IFSC', r'(?i)\b[A-Z]{4}0[A-Z0-9]{6}\b'),
        ('PAN', r'(?i)\b[A-Z]{5}\d{4}[A-Z]\b'),
        ('AADHAAR', r'(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)'),
        ('PHONE', r'(?<!\d)(?:\+?91[ -]?)?[6-9](?:[ -]?\d){9}(?!\d)'),
        ('LONG_IDENTIFIER', r'(?<!\d)\d(?:[ ,\-]?\d){8,18}(?!\d)'),
    )

    def redact(self, text: str) -> RedactionResult:
        text = normalize(text)
        counts = {}
        for name, pattern in self.patterns:
            text, count = re.subn(pattern, f'[{name}_REDACTED]', text)
            if count:
                counts[name] = count
        return RedactionResult(text, counts)

    def assert_sanitized(self, text: str) -> None:
        if self.redact(text).counts:
            raise ValueError('Payload failed privacy gate')

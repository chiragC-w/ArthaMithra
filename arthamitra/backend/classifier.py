from backend.pii_redactor import normalize
from backend.schemas import Classification, DocumentType

SIGNALS = {
    DocumentType.LOAN: ('loan agreement', 'ಸಾಲ ಒಪ್ಪಂದ', 'loan contract'),
    DocumentType.PASSBOOK: ('passbook', 'ಪಾಸ್ಬುಕ್', 'ಪಾಸ್‌ಬುಕ್', 'debit', 'credit', 'ಶಿಲ್ಕು'),
    DocumentType.SCHEME: ('government scheme', 'sanction letter', 'ಸರ್ಕಾರಿ ಯೋಜನೆ', 'ಮಂಜೂರಾತಿ ಪತ್ರ'),
    DocumentType.SCHEDULE: ('repayment schedule', 'ಮರುಪಾವತಿ ವೇಳಾಪಟ್ಟಿ', 'due date', 'outstanding balance'),
}


def classify(text: str) -> Classification:
    text = normalize(text).casefold()
    hits = {kind: [s for s in signals if normalize(s).casefold() in text] for kind, signals in SIGNALS.items()}
    ranked = sorted(hits, key=lambda kind: len(hits[kind]), reverse=True)
    best = ranked[0]
    if not hits[best] or len(hits[best]) == len(hits[ranked[1]]):
        return Classification(document_type=DocumentType.UNKNOWN, confidence=0.0, evidence=[])
    # Heuristic score, not a calibrated probability.
    return Classification(document_type=best, confidence=min(0.95, 0.65 + 0.1 * len(hits[best])), evidence=hits[best])

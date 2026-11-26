import pytest
from backend.pii_redactor import PIIRedactor, valid_aadhaar, valid_card, valid_ifsc
from backend.rbi_retriever import RBIRetriever


@pytest.mark.parametrize('value', ['2345 6789 0123', '000011112222', '+91 98765 43210', 'SBIN0001234', '4111-1111-1111-1111', 'ABCDE1234F', 'test@example.org', '೨೩೪೫ ೬೭೮೯ ೦೧೨೩'])
def test_mask_candidates_even_invalid(value):
    result = PIIRedactor().redact(value)
    assert value not in result.text
    assert result.counts
    PIIRedactor().assert_sanitized(result.text)


def test_structural_checks():
    assert valid_card('4111111111111111')
    assert not valid_card('4111111111111112')
    assert valid_ifsc('SBIN0001234')
    assert not valid_ifsc('SBIN1001234')
    assert not valid_aadhaar('000000000000')


def test_label_mask_and_financial_preservation():
    result = PIIRedactor().redact('Account no: 123O56\nBorrower: Example Person\nPrincipal: INR 50,000\nInterest: 24%')
    assert '123O56' not in result.text and 'Example Person' not in result.text
    assert '50,000' in result.text and '24%' in result.text


def test_retrieval():
    refs = RBIRetriever().retrieve('insurance consent', ['RF04'])
    assert refs[0].id == 'RBI-CONSENT'
    assert RBIRetriever().retrieve('', []) == []

import pytest
from backend.field_extractor import extract_fields
from backend.red_flag_engine import detect_flags
from backend.schemas import DocumentType

BASE = 'Loan agreement\nLender: Example Bank\nPrincipal: 50000\nInterest rate: 20% per annum reducing\nTenure: 12 months\nEMI: 4600\nKFS attached\n'


def flags(text):
    return {f.rule_id for f in detect_flags(text, extract_fields(text, DocumentType.LOAN), DocumentType.LOAN)}


@pytest.mark.parametrize('rule,text', [
    ('RF01', BASE.replace('20%', '40%')),
    ('RF02', BASE.replace('reducing', 'flat')),
    ('RF03', BASE + 'Processing fee deducted upfront'),
    ('RF04', BASE + 'Mandatory insurance'),
    ('RF05', BASE + 'Penal interest: 2%'),
    ('RF06', BASE + 'Prepayment penalty: 2%'),
    ('RF07', BASE.replace('Lender: Example Bank\n', '')),
    ('RF08', BASE + 'Signature: ____'),
    ('RF09', BASE.replace('Principal: 50000\n', '')),
    ('RF10', BASE.replace('KFS attached\n', '')),
    ('RF11', BASE + 'Late penalty on entire loan'),
    ('RF12', BASE.replace('per annum', '')),
])
def test_each_rule(rule, text):
    assert rule in flags(text)


@pytest.mark.parametrize('clause', ['No prepayment penalty', 'Prepayment penalty: 0%', 'Insurance is not compulsory', 'No penal interest', 'No upfront fee deduction', 'Insurance is optional'])
def test_negation(clause):
    assert flags(BASE + clause) == set()


def test_boundaries_and_document_scope():
    assert 'RF01' not in flags(BASE.replace('20%', '36%'))
    assert 'RF01' not in flags(BASE.replace('per annum', 'per month').replace('20%', '40%'))
    for kind in (DocumentType.PASSBOOK, DocumentType.SCHEME, DocumentType.UNKNOWN):
        assert detect_flags('Prepayment penalty: 2%', extract_fields('', kind), kind) == []


def test_fractional_charge_not_treated_as_zero():
    assert 'RF06' in flags(BASE + 'Prepayment penalty: 0.5%')
    assert 'RF06' not in flags(BASE + 'Prepayment penalty: 0.00%')

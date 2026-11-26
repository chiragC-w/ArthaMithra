import io
from pathlib import Path
import pytest
from PIL import Image
from backend.classifier import classify
from backend.field_extractor import extract_fields
from backend.ocr_pipeline import OCRPipeline, DocumentError, preprocess_image
from backend.schemas import DocumentType

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.mark.parametrize('prefix,kind', [('loan', DocumentType.LOAN), ('passbook', DocumentType.PASSBOOK), ('scheme', DocumentType.SCHEME), ('schedule', DocumentType.SCHEDULE)])
@pytest.mark.parametrize('language', ['en', 'kn'])
def test_bilingual_classification(prefix, kind, language):
    text = (FIXTURES / f'{prefix}_{language}.txt').read_text(encoding='utf-8')
    assert classify(text).document_type == kind


def test_ambiguity_abstains():
    assert classify('loan agreement\ngovernment scheme').document_type == DocumentType.UNKNOWN
    assert classify('random text').document_type == DocumentType.UNKNOWN


@pytest.mark.parametrize('language,principal', [('en', 50000), ('kn', 40000)])
def test_fields(language, principal):
    text = (FIXTURES / f'loan_{language}.txt').read_text(encoding='utf-8')
    fields = extract_fields(text, DocumentType.LOAN)
    assert fields.principal == principal
    assert fields.rate_period == 'annual'
    assert not fields.missing_fields
    assert fields.lender_present


def test_conflicts_percentages_and_blanks():
    fields = extract_fields('Principal: 100\nPrincipal: 200\nProcessing fee: 2%\nTenure: 2 years\nSignature: ___\nEMI: ___', DocumentType.LOAN)
    assert fields.principal is None and fields.fees is None
    assert fields.tenure == 24
    assert set(fields.blank_fields) == {'signature', 'instalment_amount'}
    assert len(fields.warnings) == 2


def test_ocr_text_image_and_errors():
    class MockOCR:
        def recognize(self, image):
            assert image.mode == 'L'
            return 'Loan agreement: synthetic example'
    stream = io.BytesIO()
    Image.new('RGB', (80, 80), 'white').save(stream, format='PNG')
    assert OCRPipeline(MockOCR()).process(stream.getvalue(), '.png').text.startswith('Loan')
    assert preprocess_image(Image.new('RGB', (30, 30))).mode == 'L'
    assert OCRPipeline().process(b'Loan agreement example', '.txt').text
    for data, suffix in [(b'bad', '.png'), (b'bad', '.exe'), (b'\xff', '.txt'), (b'', '.txt')]:
        with pytest.raises(DocumentError):
            OCRPipeline().process(data, suffix)


def test_empty_line_does_not_consume_next_field():
    fields = extract_fields('Principal:\nEMI: 500\nLender:\nTenure: 2 months', DocumentType.LOAN)
    assert fields.principal is None and fields.instalment_amount == 500
    assert 'principal' in fields.blank_fields
    assert not fields.lender_present

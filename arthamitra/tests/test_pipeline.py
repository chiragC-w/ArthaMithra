import asyncio
from pathlib import Path
from backend.pipeline import AnalysisPipeline
from backend.tts_service import TTSService
from backend.schemas import DISCLAIMER


def test_pipeline_end_to_end_offline():
    content = (Path(__file__).parent / 'fixtures/loan_en.txt').read_bytes()
    content += b'\nAccount number: 123456789012\nMobile: 9876543210'
    result = asyncio.run(AnalysisPipeline().analyze(content, '.txt'))
    serialized = result.model_dump_json()
    assert '123456789012' not in serialized and '9876543210' not in serialized
    assert result.fields.principal == 50000
    assert result.red_flags == []
    assert result.disclaimer == DISCLAIMER
    assert result.stage_timings_ms['total'] >= 0
    assert result.audio.status == 'unavailable'


def test_tts_success_and_failure():
    class Success:
        async def synthesize(self, text):
            return b'ID3mock'
    class Failure:
        async def synthesize(self, text):
            raise RuntimeError('provider secret')
    assert asyncio.run(TTSService(Success()).generate('ನಮಸ್ಕಾರ')).status == 'available'
    failed = asyncio.run(TTSService(Failure()).generate('ನಮಸ್ಕಾರ'))
    assert failed.status == 'unavailable'
    assert 'secret' not in failed.model_dump_json()
    assert asyncio.run(TTSService(Success()).generate('9876543210')).status == 'unavailable'

import asyncio
import json
from types import SimpleNamespace
import pytest
httpx = pytest.importorskip('httpx')
from backend.llm_explainer import OpenAICompatibleProvider, LLMExplainer
from backend.schemas import FinancialFields, DocumentType
from backend.tts_service import AzureKannadaTTS

SETTINGS = SimpleNamespace(llm_model='test-model', llm_base_url='https://example.invalid/v1', llm_api_key='test-key', llm_timeout_seconds=1, azure_speech_region='centralindia', azure_speech_key='test-key', tts_voice='kn-IN-SapnaNeural')


def test_external_json_and_retry():
    calls = []
    def handle(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503)
        body = json.loads(request.content)
        assert body['response_format']['json_schema']['strict']
        plan = {'fact_ids': ['overview'], 'step_ids': ['carry', 'ask', 'verify'], 'reference_ids': []}
        return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(plan)}}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await LLMExplainer(OpenAICompatibleProvider(SETTINGS, client)).explain(FinancialFields(), [], DocumentType.LOAN, [])
    assert asyncio.run(run()).mode == 'external_grounded'
    assert len(calls) == 2


def test_malformed_provider_response_falls_back():
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={'choices': []}))) as client:
            return await LLMExplainer(OpenAICompatibleProvider(SETTINGS, client)).explain(FinancialFields(), [], DocumentType.LOAN, [])
    assert asyncio.run(run()).mode == 'fallback_template'


def test_azure_request():
    def handle(request):
        assert request.headers['X-Microsoft-OutputFormat'].endswith('mp3')
        assert b'&amp;' in request.content
        return httpx.Response(200, content=b'ID3mock')
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await AzureKannadaTTS(SETTINGS, client).synthesize('ನಮಸ್ಕಾರ & test')
    assert asyncio.run(run()) == b'ID3mock'


def test_gemini_quota_error_has_no_retry_or_paid_fallback():
    from backend.llm_explainer import GeminiFlashProvider
    calls = []
    def handle(request):
        calls.append(request)
        assert request.url.host == 'generativelanguage.googleapis.com'
        assert json.loads(request.content)['model'] == 'gemini-3.8-flash'
        return httpx.Response(429, json={'error': {'message': 'Quota exceeded'}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            settings = SimpleNamespace(gemini_api_key='test-google-key', llm_timeout_seconds=1)
            return await LLMExplainer(GeminiFlashProvider(settings, client)).explain(FinancialFields(), [], DocumentType.LOAN, [])
    assert asyncio.run(run()).mode == 'fallback_template'
    assert len(calls) == 1

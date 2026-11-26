import asyncio
import json
from backend.llm_explainer import LLMExplainer, ExplanationPlan
from backend.schemas import FinancialFields, DocumentType


def test_offline_grounding_and_limits():
    fields = FinancialFields(principal=50000.0)
    result = asyncio.run(LLMExplainer().explain(fields, [], DocumentType.LOAN, []))
    assert result.mode == 'offline_template'
    assert '50,000' in result.summary.en
    assert len(result.steps) == 4
    assert len(result.summary.en.split()) <= 150
    assert any('\u0c80' <= c <= '\u0cff' for c in result.summary.kn)


def test_provider_receives_only_closed_facts():
    class CapturingProvider:
        async def plan(self, payload):
            assert 'Secret Person' not in json.dumps(payload)
            return ExplanationPlan(fact_ids=['principal'], step_ids=['carry', 'ask', 'verify'], reference_ids=[])
    fields = FinancialFields(principal=1000.0, evidence={'principal': 'Secret Person'})
    result = asyncio.run(LLMExplainer(CapturingProvider()).explain(fields, [], DocumentType.LOAN, []))
    assert result.mode == 'external_grounded'
    assert result.fact_ids == ['principal']


def test_invalid_id_falls_back():
    class InventingProvider:
        async def plan(self, payload):
            return ExplanationPlan(fact_ids=['fake'], step_ids=['carry', 'ask', 'verify'], reference_ids=['invented law'])
    result = asyncio.run(LLMExplainer(InventingProvider()).explain(FinancialFields(), [], DocumentType.UNKNOWN, []))
    assert result.mode == 'fallback_template'
    assert 'fake' not in result.summary.en


def test_failure_falls_back():
    class FailedProvider:
        async def plan(self, payload):
            raise TimeoutError()
    result = asyncio.run(LLMExplainer(FailedProvider()).explain(FinancialFields(), [], DocumentType.PASSBOOK, []))
    assert result.mode == 'fallback_template'


def test_unvalidated_plan_falls_back():
    class BadProvider:
        async def plan(self, payload):
            return {'bad': 'output'}
    result = asyncio.run(LLMExplainer(BadProvider()).explain(FinancialFields(), [], DocumentType.SCHEME, []))
    assert len(result.steps) >= 3


def test_gemini_ignores_openai_model_endpoint_and_key():
    from types import SimpleNamespace
    from backend.llm_explainer import GeminiFlashProvider
    provider = GeminiFlashProvider(SimpleNamespace(
        gemini_api_key='google-test-key', llm_timeout_seconds=1,
        llm_model='expensive-model', llm_base_url='https://api.openai.com/v1',
        llm_api_key='unused-openai-key'))
    assert provider.settings.llm_model == 'gemini-3.8-flash'
    assert provider.settings.llm_api_key == 'google-test-key'
    assert provider.settings.llm_base_url == 'https://generativelanguage.googleapis.com/v1beta/openai'
    assert provider.generation_options()['reasoning_effort'] == 'low'

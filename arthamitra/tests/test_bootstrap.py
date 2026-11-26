import pytest
pytest.importorskip('pydantic_settings')
from backend.config import Settings, ROOT
from backend.schemas import FinancialFields


def test_bootstrap():
    assert len(list((ROOT / 'tests/fixtures').glob('*.txt'))) == 8
    assert FinancialFields().principal is None
    assert Settings(_env_file=None).llm_provider == 'offline'


def test_gate_cannot_be_disabled():
    with pytest.raises(ValueError):
        Settings(pii_redaction_enabled=False, _env_file=None)

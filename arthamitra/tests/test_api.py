import pytest
pytest.importorskip('fastapi')
pytest.importorskip('httpx')
pytest.importorskip('pydantic_settings')
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app


def test_api_upload_and_safe_errors():
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert client.get('/').status_code == 200
        assert client.get('/api/v1/health').json()['llm_mode'] == 'offline'
        response = client.post('/api/v1/analyze-document', files={'file': ('sample.txt', b'Bank passbook\nAccount: 123456789012', 'text/plain')})
        assert response.status_code == 200
        assert '123456789012' not in response.text
        assert response.headers['cache-control'] == 'no-store'
        assert client.post('/api/v1/analyze-document', files={'file': ('sample.exe', b'bad')}).status_code == 422
        assert client.post('/api/v1/analyze-document').status_code == 422


def test_upload_size():
    with TestClient(create_app(Settings(max_upload_bytes=20, _env_file=None))) as client:
        assert client.post('/api/v1/analyze-document', files={'file': ('sample.txt', b'x' * 30)}).status_code == 413

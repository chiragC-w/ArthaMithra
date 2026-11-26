from pathlib import Path
from typing import Literal
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    llm_provider: Literal['offline', 'openai_compatible', 'gemini'] = 'offline'
    gemini_api_key: str = ''
    llm_base_url: str = 'https://api.openai.com/v1'
    llm_api_key: str = ''
    llm_model: str = 'gpt-4.1-mini'
    llm_timeout_seconds: float = Field(default=8, gt=0, le=10)
    ocr_provider: Literal['tesseract'] = 'tesseract'
    ocr_languages: str = 'kan+eng'
    tts_provider: Literal['offline', 'azure'] = 'offline'
    azure_speech_key: str = ''
    azure_speech_region: str = 'centralindia'
    tts_voice: str = 'kn-IN-SapnaNeural'
    pii_redaction_enabled: bool = True
    max_upload_bytes: int = Field(default=5_000_000, gt=0, le=10_000_000)
    pipeline_timeout_seconds: float = Field(default=28, gt=0, le=29)
    high_rate_threshold: float = Field(default=36, gt=0)

    @model_validator(mode='after')
    def privacy_gate(self):
        if not self.pii_redaction_enabled:
            raise ValueError('PII redaction cannot be disabled')
        if self.llm_provider == 'gemini' and not self.gemini_api_key:
            raise ValueError('Gemini requires GEMINI_API_KEY from an unbilled free-tier project')
        if self.llm_provider == 'openai_compatible' and (not self.llm_api_key or not self.llm_base_url.startswith('https://')):
            raise ValueError('External LLM requires an API key and HTTPS endpoint')
        if self.tts_provider == 'azure' and not self.azure_speech_key:
            raise ValueError('Azure TTS requires a key')
        return self

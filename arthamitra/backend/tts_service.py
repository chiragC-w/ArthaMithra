import asyncio
import base64
import re
from typing import Protocol
from xml.sax.saxutils import escape, quoteattr
from backend.pii_redactor import PIIRedactor
from backend.schemas import AudioResult


class TTSProvider(Protocol):
    async def synthesize(self, text: str) -> bytes: ...


class AzureKannadaTTS:
    def __init__(self, settings, client=None):
        self.settings, self.client = settings, client
        if not re.fullmatch(r'[a-z0-9]+', settings.azure_speech_region):
            raise ValueError('Invalid Azure region')
        if not re.fullmatch(r'kn-IN-[A-Za-z]+Neural', settings.tts_voice):
            raise ValueError('Use a Kannada neural voice')

    async def synthesize(self, text: str) -> bytes:
        import httpx
        PIIRedactor().assert_sanitized(text)
        ssml = f'<speak version="1.0" xml:lang="kn-IN"><voice name={quoteattr(self.settings.tts_voice)}>{escape(text)}</voice></speak>'
        async def send(client):
            response = await client.post(f'https://{self.settings.azure_speech_region}.tts.speech.microsoft.com/cognitiveservices/v1',
                headers={'Ocp-Apim-Subscription-Key': self.settings.azure_speech_key, 'Content-Type': 'application/ssml+xml', 'X-Microsoft-OutputFormat': 'audio-16khz-32kbitrate-mono-mp3', 'User-Agent': 'ArthaMitra'},
                content=ssml.encode('utf-8'), timeout=5)
            response.raise_for_status()
            content = response.content
            if not content or len(content) > 3_000_000 or not (content.startswith(b'ID3') or content[:1] == b'\xff'):
                raise ValueError('Unexpected audio response')
            return content
        if self.client is not None:
            return await send(self.client)
        async with httpx.AsyncClient(follow_redirects=False) as client:
            return await send(client)


class TTSService:
    def __init__(self, provider: TTSProvider | None = None):
        self.provider = provider

    async def generate(self, text: str) -> AudioResult:
        if self.provider is None:
            return AudioResult(status='unavailable', message='Audio is off in local mode. Read the Kannada text aloud.')
        try:
            PIIRedactor().assert_sanitized(text)
            audio = await asyncio.wait_for(self.provider.synthesize(text), timeout=6)
            if not audio:
                raise ValueError('Empty audio')
            return AudioResult(status='available', mime_type='audio/mpeg', base64=base64.b64encode(audio).decode('ascii'))
        except Exception:
            return AudioResult(status='unavailable', message='Kannada audio is unavailable. The text explanation is still available.')

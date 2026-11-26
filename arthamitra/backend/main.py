import asyncio
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from backend.config import ROOT, Settings
from backend.llm_explainer import LLMExplainer, OpenAICompatibleProvider, GeminiFlashProvider
from backend.ocr_pipeline import OCRPipeline, TesseractOCR, DocumentError
from backend.pipeline import AnalysisPipeline
from backend.schemas import AnalysisResult
from backend.tts_service import AzureKannadaTTS, TTSService


class BodyLimitMiddleware:
    """Bound actual bytes before multipart parsing, including chunked requests."""
    def __init__(self, app, max_bytes):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') != 'POST':
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body = message.get('body', b'')
            size += len(body)
            if size > self.max_bytes:
                response = JSONResponse(status_code=413, content={'detail': 'Document exceeds the upload limit.'}, headers={'Cache-Control': 'no-store'})
                return await response(scope, receive, send)
            chunks.append(body)
            if not message.get('more_body', False):
                break
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': b''.join(chunks), 'more_body': False}
            return await receive()
        await self.app(scope, replay, send)


def create_app(settings=None, pipeline=None):
    settings = settings or Settings()
    app = FastAPI(title='ArthaMitra', version='0.1.0')
    provider = None
    if settings.llm_provider == 'gemini':
        provider = GeminiFlashProvider(settings)
    elif settings.llm_provider == 'openai_compatible':
        provider = OpenAICompatibleProvider(settings)
    app.state.pipeline = pipeline or AnalysisPipeline(
        ocr=OCRPipeline(TesseractOCR(settings.ocr_languages)),
        explainer=LLMExplainer(provider),
        tts=TTSService(AzureKannadaTTS(settings) if settings.tts_provider == 'azure' else None),
        high_rate_threshold=settings.high_rate_threshold)
    app.state.slots = asyncio.Semaphore(2)

    @app.middleware('http')
    async def headers(request: Request, call_next):
        # Reject declared oversize requests before multipart parsing. The upload
        # read is also bounded for requests without a Content-Length header.
        length = request.headers.get('content-length')
        if length and (not length.isdigit() or int(length) > settings.max_upload_bytes + 100_000):
            return JSONResponse(status_code=413, content={'detail': 'Document exceeds the upload limit.'})
        try:
            response = await call_next(request)
        except Exception:
            # Swallow private provider/parser exceptions before server logging.
            response = JSONResponse(status_code=500, content={'detail': 'Analysis failed safely. Please retry with a clearer document.'})
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; media-src 'self' data: blob:; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.exception_handler(Exception)
    async def safe_error(request: Request, exc: Exception):
        # No exception string, request body, filename or provider response is logged.
        return JSONResponse(status_code=500, content={'detail': 'Analysis failed safely. Please retry with a clearer document.'})

    @app.get('/api/v1/health')
    async def health():
        return {'status': 'ok', 'llm_mode': settings.llm_provider, 'tts_mode': settings.tts_provider, 'max_upload_bytes': settings.max_upload_bytes}

    @app.post('/api/v1/analyze-document', response_model=AnalysisResult)
    async def analyze_document(file: UploadFile = File(...)):
        suffix = Path(file.filename or '').suffix.lower()
        try:
            content = await file.read(settings.max_upload_bytes + 1)
        finally:
            await file.close()
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(413, 'Document exceeds the upload limit.')
        async def run():
            async with app.state.slots:
                return await app.state.pipeline.analyze(content, suffix)
        try:
            return await asyncio.wait_for(run(), timeout=settings.pipeline_timeout_seconds)
        except DocumentError as error:
            raise HTTPException(422, str(error)) from None
        except TimeoutError:
            raise HTTPException(504, 'Analysis timed out. Try a smaller or clearer document.') from None

    app.mount('/', StaticFiles(directory=ROOT / 'frontend', html=True), name='frontend')
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_upload_bytes + 100_000)
    return app


app = create_app()

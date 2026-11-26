# ArthaMitra

A local-first, mobile-friendly financial document explainer for trusted community intermediaries in Karnataka. Kannada and English explanations, deterministic review flags, and optional external LLM planning and Kannada speech. No local LLM weights or training pipeline.

## Run

The local `.env` now selects **Gemini Flash** (`LLM_PROVIDER=gemini`). Set `GEMINI_API_KEY` from a Google AI Studio project with **no Cloud Billing account linked** before starting. Gemini mode pins `gemini-3.8-flash` and Google's endpoint; it ignores OpenAI credentials and generic model/endpoint settings. This pin prevents accidental OpenAI fallback, but cannot enforce or verify Google's billing tier. Preserve `.env` when following the commands below. Example/code defaults remain offline; live integration verification is pending credentials and dependency installation.

Google currently lists free-tier input/output for this model. Keep the key's project on Free Tier: do not enable billing or upgrade. A 429 quota error gets no immediate retry and falls back to local templates, never to another model. A later upload can try Gemini again; daily limits reset according to Google's schedule. The app does not buy credits or upgrade billing. Keep `TTS_PROVIDER=offline` to avoid Azure speech charges. Free-tier content can be used to improve Google's products; test with synthetic data. Only the app's closed fact cards are transmitted, not raw OCR prose.

Sources checked 2026-11-24: [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [free-tier billing requirement](https://firebase.google.com/docs/ai-logic/pricing?api=dev), [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits), [OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai).

From this directory, using Python 3.12 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
if (!(Test-Path .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Open **http://127.0.0.1:8000**. API documentation is at `/docs`. Upload a synthetic fixture from `tests/fixtures/` to try it. Default mode needs no keys and makes no external LLM or TTS calls. The upload travels to your running backend; “local” means local to that backend, not browser-only processing.

For image OCR, separately install Tesseract from a trusted distribution and ensure it is on PATH with `kan` and `eng` traineddata. TXT and text PDFs do not require Tesseract. Scanned/mixed PDFs currently return a clear instruction to upload page photographs. The app does not silently omit unreadable pages. Upload limits: 5 MB by default, 10 PDF pages, 20 megapixels, 60,000 extracted characters. Unsupported documents receive a 422 response.

For an external LLM, set `LLM_PROVIDER=openai_compatible`, `LLM_API_KEY`, `LLM_MODEL`, and an HTTPS `LLM_BASE_URL` supporting Chat Completions strict JSON schema. For actual Kannada speech, set `TTS_PROVIDER=azure`, `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION`. Model and voice availability depends on your provider account. Keys stay on the backend. TTS receives only the generated Kannada explanation, advisory and action steps.

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m eval.evaluate_pipeline
node --check frontend/app.js
```

The evaluation writes `eval/results.json`. Supply a separately annotated corpus with `--labels path/to/labels.json --fixtures path/to/documents`. Gold labels list document type, the seven numeric fields that are present, and expected rule IDs. Missing expected values are treated as absent; incorrect predicted values count as both FP and FN. The confusion matrix evaluates every document/rule pair. Undefined metrics are `null`, not a fabricated perfect score. Default evaluation uses offline providers; inject a configured `AnalysisPipeline` into `evaluate()` for provider-inclusive measurements.

## Layout and contracts

```text
backend/
  schemas.py            Strict Pydantic v2 contracts and mandatory advisory
  config.py             Environment configuration; mandatory privacy gate
  pii_redactor.py        Unicode normalization and identifier masking
  ocr_pipeline.py        OCRProvider, Tesseract, text/PDF decoding, preprocessing
  classifier.py         Bilingual heuristics with unknown/ambiguous abstention
  field_extractor.py    Label-based extraction with evidence and ambiguity checks
  red_flag_engine.py    RF01–RF12, deterministic and bilingual
  rbi_retriever.py       Local keyword/rule-ID retrieval
  llm_explainer.py       LLMProvider, strict ID plans, verified bilingual rendering
  tts_service.py         TTSProvider, Azure Kannada adapter, unavailable fallback
  pipeline.py           Ordered stages and timings
  main.py               FastAPI and same-origin frontend
frontend/               Buildless HTML, CSS and JavaScript
data/rbi_rules/         Scoped regulatory references with official source URLs
tests/fixtures/         Eight synthetic English/Kannada financial documents
eval/                   Gold labels and metrics
docs/CHECKPOINTS.md     Implementation and verification record
```

`POST /api/v1/analyze-document` accepts multipart `file`. The response contains classification, masked text, redaction counts, extracted fields and evidence, deterministic red flags, RBI citations, bilingual explanation and 3–5 steps, MP3 base64 or an explicit unavailable result, mandatory advisory and stage timings. See `/docs` for the complete schema. A whole-request pipeline deadline returns 504; it is a budget, not proof of a <30-second user-perceived response over 4G. Python worker cancellation does not forcibly terminate all local parsing work; Tesseract has its own timeout. `GET /api/v1/health` reports modes and upload limit.

## Grounding and privacy decisions

1. Uploaded bytes and raw OCR stay in the backend. No remote vision receives original images. `OCRProvider` is the extension point for another local OCR engine; no TrOCR weights are bundled.
2. The mandatory redactor masks labelled identifiers, Aadhaar-shaped values (including invalid checksums), account-like long numbers, mobiles, IFSC, PAN, cards, email and labelled names/addresses. Verhoeff/Luhn/IFSC validators are included; invalid checksums never exempt a candidate. Conservative masking can remove unusually long financial numbers. Free-form names, addresses and unusual OCR corruption are not comprehensively detected; the masked-text UI warns against sharing without review.
3. Extraction and deterministic review run on the masked text. Raw payloads, filenames, matches and exception details are not application diagnostics. No document database, analytics or persistent browser history is created. Multipart temporary files are closed after reading. Disable reverse-proxy body logging and provider debug logging when deploying.
4. **Free-form OCR and evidence never reach the LLM.** Only closed bilingual fact cards built from whitelisted numeric fields and fixed rule reasons, fixed action cards and curated RBI references are sent. The redactor checks this outgoing payload again. This deliberately limits the external model to selecting and ordering known IDs. It cannot write new numbers, accusations or rules into the explanation.
5. The server rejects unknown IDs, duplicate selections, missing carry/question steps, invalid schemas and invalid citations. It assembles the final text and enforces the 150-word-per-language ceiling. Provider failure produces a labelled template fallback. Full red flags remain visible even if the short summary omits one. The model may select RBI reference IDs for traceability; all retrieved references are separately displayed with their scope.
6. The advisory is attached by the backend, displayed in the UI, and included in spoken output. Kannada text is human-readable but still needs review by Kannada-speaking field workers before operational rollout.

## Rule catalogue

| ID | Trigger | Interpretation |
|---|---|---|
| RF01 | Stated annual rate above configured threshold (default 36%) | Heuristic review threshold, **not an RBI interest cap** |
| RF02 | Flat basis without numeric APR | Ask for total annual cost |
| RF03 | Explicit upfront fee deduction | Clarify net disbursement |
| RF04 | Explicit mandatory insurance wording | Clarify consent and product type |
| RF05 | Positive penal-interest clause | Check applicable penal-charge rules |
| RF06 | Positive prepayment charge | Check applicability; microfinance reference only when stated |
| RF07 | No usable lender label in supplied agreement | Check complete original |
| RF08 | Explicit blank amount/signature field | Complete and verify |
| RF09 | Core loan field extraction missing | Could be OCR/layout failure |
| RF10 | KFS not identified in supplied agreement | Ask for KFS where applicable |
| RF11 | Late penalty on whole loan | Check overdue-only basis |
| RF12 | Rate has no annual/monthly period | Clarify rate period |

Rules run on loan agreements and repayment schedules; lender/KFS absence rules apply only to agreements. Negation handling is conservative and sentence-based, not a general language understanding system. No flags is **not** a safe-document certification. No APR is calculated from incomplete cash flows, and monthly/flat rates are not guessed into annual effective rates. Table layout and unlabelled financial values need future extraction adapters and representative validation.

## Sources and maintenance

References were checked on 2026-11-24 against official RBI pages. The data captures lender/category/date limitations; it must not be applied to every lender automatically. The historical 2022 microfinance direction is useful background, while current lender-specific consolidated directions should govern applicability.

- [RBI Commercial Banks – Responsible Business Conduct Directions, 2025, updated October 1, 2026](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13140)
- [RBI NBFC FAQ, updated November 11, 2026](https://www.rbi.org.in/scripts/FAQView.aspx?Id=92)
- [Historical microfinance framework, updated July 17, 2025](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12256)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Azure Speech REST API](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech) and [Kannada voice support](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=text-to-speech)

Review and version the reference dataset when regulations change. This project is a local development implementation, not a production authorization or financial-advice system. Before exposing it to real users, supply deployment authentication, TLS, request/rate limits, operational retention settings and independently annotated evaluation data. Public hosting was not configured.

## Verification in this workspace

The environment blocked package-registry access, so the created `.venv` does **not** yet contain the required dependencies. Using installed Python packages, 54 tests passed and three modules skipped (configuration, API and HTTP provider tests). The implemented skipped tests use mocked HTTP responses and require no live quota once dependencies are installed. Python compilation and JavaScript syntax checks passed. Browser inspection was attempted but the browser access host was unavailable; visual and Android interaction QA remain unverified.

The eight synthetic text fixtures yielded classification accuracy 1.0, field F1 1.0, flag recall 1.0 on **only one positive rule case**, FPR 0.0, and at most 33 explanation words. These are development smoke results, **not evidence for the ≥90% / ≥85% / ≤10% targets**. Real scan OCR, real field performance, Kannada speech quality, external-provider compatibility and end-to-end 4G latency remain unmeasured.

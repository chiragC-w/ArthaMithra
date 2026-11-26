# Checkpoint record

## 1. Repository and environment bootstrap

Created `pyproject.toml`, `.env.example`, `.gitignore`, `.venv`, `backend/config.py`, `backend/schemas.py`, package entry points and eight synthetic Kannada/English fixtures. Chose a local FastAPI monorepo with a buildless frontend. The two supplied PDFs remain unchanged outside the project; implementation follows the user-provided synopsis.

Checks: Python 3.12.6 confirmed. Dependency installation attempted and failed with the sandbox's WinError 10013 network restriction. Configuration tests written; execution requires `pydantic-settings`. No permissions were changed.

Assumptions: offline providers by default, user-supplied keys for cloud calls, mandatory privacy gate even when configuration requests disabling it.

## 2. Redaction and regulatory references

Created `pii_redactor.py`, `rbi_retriever.py`, `data/rbi_rules/references.json`, and `tests/test_privacy.py`. Verified official RBI sources, recorded section and scope, and avoided universal claims about lender applicability.

Checks: 11 tests passed. Candidate identifiers are masked even with invalid checksums. Unicode digits and structurally labelled OCR-corrupted values are covered. Later privacy review added comma-separated long identifiers.

Assumptions: regex is not comprehensive free-form PII detection, so OCR prose is excluded from external LLM payloads entirely.

## 3. OCR, classifier and extraction

Created `ocr_pipeline.py`, `classifier.py`, `field_extractor.py`, and bilingual extraction tests. Added local Tesseract adapter, grayscale/contrast/small-angle deskew, bounded text/image/PDF ingestion and explicit scan-PDF rejection.

Checks: 24 cumulative tests passed, including mocked image OCR, classification ambiguity, percentage versus currency charges, missing/blank fields and conflicting values. Real Tesseract execution was not available. Later regression test ensures empty labels do not consume following lines.

Assumptions: conservative label-based extraction; no effective-rate calculation or inferred table layout. Unknown document type is a supported abstention, alongside the four requested classes.

## 4. Deterministic flags

Created `red_flag_engine.py` and `tests/test_rules.py`. RF01–RF12 emit bilingual reasons, source references and evidence. Review thresholds and missing-page indicators are not presented as legal conclusions.

Checks: 43 cumulative tests passed. Each rule has a positive case; tests also cover no-charge/optional clauses, threshold boundaries and non-loan scoping. Later regression tests distinguish 0.5% from zero charges.

Assumptions: sentence-based negation and explicit cues; regulator scope needs an official's verification.

## 5. External-LLM explainer

Created `llm_explainer.py` and explainer tests. Added interchangeable providers, strict JSON-schema requests, two-attempt transient retry, overall timeout, closed bilingual fact/step planning, ID validation and safe template fallbacks.

Checks: 48 cumulative tests passed after fixing false rejection caused by Unicode normalization. Tests cover invalid IDs, failures, free-form evidence exclusion, word limits, bilingual text and required actions. HTTP transport tests were subsequently added but cannot run without httpx.

Assumptions: grounded generation means selecting/ordering verified bilingual cards, not unrestricted prose generation. No self-trained or local LLM.

## 6. API, speech, UI and evaluation

Created `tts_service.py`, `pipeline.py`, `main.py`, `frontend/{index.html,styles.css,app.js}`, `eval/{labels.json,evaluate_pipeline.py}`, integration/evaluation/transport tests, and README. Azure Kannada MP3 adapter includes SSML escaping, privacy checking and graceful unavailable fallback. API includes same-origin frontend, upload-byte limits (including chunked body accumulation), a bounded pipeline deadline, safe errors and no-store headers.

Checks: **54 tests passed; three test modules skipped** because FastAPI, httpx and pydantic-settings are unavailable. Python compilation and `node --check frontend/app.js` passed. Offline evaluation ran on eight fixtures. The local static preview server started, but browser inspection failed because the browser access host was unavailable. Preview server is stopped at handoff. Full API tests, real OCR/TTS, mobile rendering and cloud-provider integration remain unverified.

Assumptions: local repository delivery; no publication, no persistent uploaded-document store, no actual synthesized audio in offline mode. The latency deadline is not an empirical 4G result.

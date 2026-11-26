import asyncio
from time import perf_counter
from backend.classifier import classify
from backend.field_extractor import extract_fields
from backend.llm_explainer import LLMExplainer
from backend.ocr_pipeline import OCRPipeline
from backend.pii_redactor import PIIRedactor
from backend.rbi_retriever import RBIRetriever
from backend.red_flag_engine import detect_flags
from backend.schemas import AnalysisResult, DISCLAIMER, DocumentType
from backend.tts_service import TTSService


class AnalysisPipeline:
    def __init__(self, ocr=None, explainer=None, tts=None, high_rate_threshold=36):
        self.ocr = ocr or OCRPipeline()
        self.explainer = explainer or LLMExplainer()
        self.tts = tts or TTSService()
        self.redactor = PIIRedactor()
        self.retriever = RBIRetriever()
        self.high_rate_threshold = high_rate_threshold

    async def analyze(self, content: bytes, suffix: str) -> AnalysisResult:
        start = perf_counter()
        marks = {}
        last = start
        def mark(name):
            nonlocal last
            now = perf_counter()
            marks[name] = round((now - last) * 1000, 2)
            last = now
        ocr = await asyncio.to_thread(self.ocr.process, content, suffix)
        mark('ocr')
        redacted = self.redactor.redact(ocr.text)
        self.redactor.assert_sanitized(redacted.text)
        # Drop the raw string reference; never send it to providers or diagnostics.
        ocr.text = ''
        mark('redaction')
        classification = classify(redacted.text)
        fields = extract_fields(redacted.text, classification.document_type)
        mark('classification_extraction')
        flags = detect_flags(redacted.text, fields, classification.document_type, self.high_rate_threshold)
        references = self.retriever.retrieve(redacted.text, [f.rule_id for f in flags])
        mark('rules_retrieval')
        explanation = await self.explainer.explain(fields, flags, classification.document_type, references)
        mark('explanation')
        spoken = ' '.join([DISCLAIMER.kn, explanation.summary.kn] + [s.kn for s in explanation.steps])
        audio = await self.tts.generate(spoken)
        mark('tts')
        marks['total'] = round((perf_counter() - start) * 1000, 2)
        warnings = ocr.warnings + fields.warnings
        if classification.document_type == DocumentType.UNKNOWN:
            warnings.append('Document type uncertain; loan-specific rules were not applied.')
        warnings.append('Automated screening cannot establish legal compliance. Check the original with an official.')
        return AnalysisResult(classification=classification, redacted_text=redacted.text, redaction_counts=redacted.counts,
            fields=fields, red_flags=flags, rbi_citations=references, explanation=explanation, audio=audio, stage_timings_ms=marks, warnings=warnings)

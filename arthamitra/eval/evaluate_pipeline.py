"""Run from repository root: python -m eval.evaluate_pipeline.

These hand-authored synthetic fixtures are smoke tests, NOT a held-out benchmark.
Use --labels and --fixtures to supply a separately annotated evaluation corpus.
FPR is calculated over document x rule decisions, not only emitted flags.
"""
import argparse
import asyncio
import json
import math
from pathlib import Path
from backend.pipeline import AnalysisPipeline
from backend.red_flag_engine import REASONS

FIELDS = ('principal','interest_rate','tenure','instalment_amount','fees','penalties','insurance_charges')


def safe_ratio(numerator, denominator):
    return numerator / denominator if denominator else None


async def evaluate(labels, fixtures, pipeline=None):
    pipeline = pipeline or AnalysisPipeline()
    correct = field_tp = field_fp = field_fn = flag_tp = flag_fp = flag_fn = flag_tn = 0
    latencies, counts, rows = [], [], []
    for row in labels:
        path = (fixtures / row['file']).resolve()
        if not path.is_relative_to(fixtures.resolve()):
            raise ValueError('Fixture path escapes fixture directory')
        result = await pipeline.analyze(path.read_bytes(), path.suffix)
        correct += result.classification.document_type.value == row['type']
        for key in FIELDS:
            predicted = getattr(result.fields, key)
            expected = row['fields'].get(key)
            match = predicted is not None and expected is not None and math.isclose(predicted, expected, abs_tol=.01)
            field_tp += match
            field_fp += predicted is not None and not match
            field_fn += expected is not None and not match
        actual_flags = {flag.rule_id for flag in result.red_flags}
        expected_flags = set(row['flags'])
        if not expected_flags <= REASONS.keys():
            raise ValueError('Unknown gold rule ID')
        for rule in REASONS:
            actual, expected = rule in actual_flags, rule in expected_flags
            flag_tp += actual and expected
            flag_fp += actual and not expected
            flag_fn += not actual and expected
            flag_tn += not actual and not expected
        words = {lang: len(getattr(result.explanation.summary, lang).split()) for lang in ('en', 'kn')}
        counts.extend(words.values())
        latencies.append(result.stage_timings_ms['total'])
        rows.append({'file': row['file'], 'predicted_type': result.classification.document_type.value, 'flags': sorted(actual_flags), 'explanation_words': words, 'steps': len(result.explanation.steps)})
    ordered = sorted(latencies)
    return {'corpus': 'Supplied labels; default corpus is synthetic smoke tests only', 'documents':len(labels),
        'classification_accuracy':safe_ratio(correct,len(labels)), 'field_f1':safe_ratio(2*field_tp,2*field_tp+field_fp+field_fn),
        'red_flag_recall':safe_ratio(flag_tp,flag_tp+flag_fn), 'red_flag_fpr':safe_ratio(flag_fp,flag_fp+flag_tn),
        'flag_confusion':{'tp':flag_tp,'fp':flag_fp,'fn':flag_fn,'tn':flag_tn},
        'max_explanation_words':max(counts,default=0), 'latency_p95_ms':ordered[max(0,math.ceil(.95*len(ordered))-1)] if ordered else None,
        'latency_scope':'Local pipeline; excludes upload/network transit; defaults use offline LLM and TTS', 'rows':rows}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--labels',type=Path,default=Path('eval/labels.json'))
    parser.add_argument('--fixtures',type=Path,default=Path('tests/fixtures'))
    parser.add_argument('--output',type=Path,default=Path('eval/results.json'))
    args=parser.parse_args()
    results=asyncio.run(evaluate(json.loads(args.labels.read_text(encoding='utf-8')),args.fixtures))
    args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in results.items() if k!='rows'},indent=2))


if __name__ == '__main__':
    main()

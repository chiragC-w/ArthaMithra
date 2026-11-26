import asyncio
import json
from pathlib import Path
from eval.evaluate_pipeline import evaluate, safe_ratio


def test_smoke_evaluation():
    root = Path(__file__).resolve().parents[1]
    result = asyncio.run(evaluate(json.loads((root/'eval/labels.json').read_text()), root/'tests/fixtures'))
    assert result['documents'] == 8
    assert result['classification_accuracy'] == 1
    assert result['field_f1'] == 1
    assert result['flag_confusion']['tp'] == 1
    assert result['max_explanation_words'] <= 150
    assert all(3 <= row['steps'] <= 5 for row in result['rows'])


def test_undefined_metric_not_faked_as_perfect():
    assert safe_ratio(0, 0) is None
    assert safe_ratio(1, 2) == .5

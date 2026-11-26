import json
import re
from pathlib import Path
from backend.schemas import RBIReference


class RBIRetriever:
    def __init__(self, path: Path | None = None):
        path = path or Path(__file__).resolve().parents[1] / 'data/rbi_rules/references.json'
        self.references = [RBIReference.model_validate(row) for row in json.loads(path.read_text(encoding='utf-8'))]

    def retrieve(self, text: str, rule_ids: list[str], limit: int = 5) -> list[RBIReference]:
        terms = set(re.findall(r'\w+', text.lower())) | {r.lower() for r in rule_ids}
        scored = [(sum(3 if k.startswith('RF') else 1 for k in r.keywords if k.lower() in terms), r) for r in self.references]
        return [r for score, r in sorted(scored, key=lambda pair: (-pair[0], pair[1].id)) if score > 0][:limit]

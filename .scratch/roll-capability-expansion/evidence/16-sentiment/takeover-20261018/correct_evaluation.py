"""Derive corrected metrics from archived confusion, without new inference/tuning."""
import hashlib
import json
from pathlib import Path
from roll.market.sentiment_evaluation import evaluate_confusion

out = Path(__file__).resolve().parent
source = out.parent / 'eval-reject-results.json'
original = json.loads(source.read_bytes())
corrected = {name: evaluate_confusion(original[name]['confusion']) for name in ('design', 'holdout', 'combined')}
result = {
    'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'method': 'All truth-labeled rows remain in recall denominators; false positives include neutral/irrelevant truth. Binary macro-F1 is named separately from four-class support.',
    'gate_thresholds': original['gates'], 'passed': False,
    'latency_p95': original['latency_p95'], 'splits': corrected,
    'limitations': ['NON_INDEPENDENT_AGENT_LABELS', 'DESIGN_HOLDOUT_TIME_OVERLAP', 'SEMANTIC_EVENT_ISOLATION_NOT_ESTABLISHED', 'NO_NEUTRAL_HOLDOUT_SUPPORT', 'OLD_HOLDOUT_ALREADY_EXAMINED'],
}
c = corrected['combined']
g = original['gates']
result['passed'] = bool(
    c['macro_f1'] >= g['macro_f1'] and c['positive_recall'] >= g['positive_recall']
    and c['negative_recall'] >= g['negative_recall']
    and original['combined']['non_directional_rejection_rate'] >= g['non_directional_rejection']
    and original['combined']['abstain_coverage'] <= g['abstain_coverage']
    and original['latency_p95'] <= g['p95_seconds']
)
(out / 'corrected-evaluation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))

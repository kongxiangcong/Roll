"""Economic-model/review/snapshot bindings for backup and recovery."""
import json
from .service import fail, verified, fingerprint


def validate_economics(db, archives):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'company_research_operating_models' not in names:
        return

    def require(value):
        if not value:
            fail('RESEARCH_REFERENCE_INVALID', 'Economic model, review or snapshot binding differs', 409)

    def records(table, key):
        require('company_research_' + table in names)
        return {r[0]: verified(json.loads(r[1])) for r in db.execute(f'SELECT {key},value FROM company_research_{table}')}

    models = records('operating_models', 'operating_model_id')
    reviews = records('economic_reviews', 'review_id')
    snapshots = records('snapshots', 'snapshot_id')
    valuations = records('valuations', 'valuation_id')
    facts = records('facts', 'version_id')
    for item in [*models.values(), *reviews.values()]:
        require(archives.get(item['archive']['sha256']) == item['archive'])
        require(fingerprint({k: v for k, v in item.items() if k not in {'content_sha256', 'archive'}}) == item['archive']['sha256'])
    for model in models.values():
        snapshot = snapshots.get(model['snapshot_id'])
        require(snapshot and snapshot['company_id'] == model['company_id'] and snapshot['content_sha256'] == model['snapshot_sha256'])
        require(model['request']['snapshot_id'] == model['snapshot_id'])
        for fact in model.get('classification_context', []):
            require(facts.get(fact['version_id']) == fact and fact['company_id'] == model['company_id'])
        require(archives.get(model['algorithm_archive']['sha256']) == model['algorithm_archive'])
        for item in model['derived_records']:
            verified(item)
            require(item['company_id'] == model['company_id'] and item['kind'] == 'DERIVED')
    for review in reviews.values():
        model = models.get(review['operating_model_id'])
        valuation = valuations.get(review['valuation_id'])
        require(model and model['company_id'] == review['company_id'] and model['content_sha256'] == review['operating_model_sha256'])
        policy = review.get('policy_archive', model['algorithm_archive'] if review['policy_version'] == 'economic-review-1' else None)
        require(policy == model['algorithm_archive'] and archives.get(policy['sha256']) == policy)
        if review['valuation_id'] is None:
            require(review['applicability'] == 'NOT_APPLICABLE' and review['status'] == 'blocked' and model['cashflows'] == [] and review['valuation_sha256'] is None)
        else:
            require(valuation and model['company_id'] == valuation['company_id'] and valuation['content_sha256'] == review['valuation_sha256'])
            require(model['snapshot_id'] == valuation['snapshot_id'] == review['source_snapshot_id'])
        require(review['status'] in {'unreviewed', 'conditional', 'blocked', 'reviewed'})
        require(review['usable_range'] == (review['status'] in {'conditional', 'reviewed'}))
        expected = 'blocked' if any(c['status'] == 'BLOCKED' for c in review['checks']) else 'conditional' if review['limitations'] or any(c['status'] == 'CONDITIONAL' for c in review['checks']) else 'reviewed'
        require(review['status'] == expected)
    for snapshot in snapshots.values():
        if snapshot.get('enrichment_kind') != 'ECONOMIC_REVIEW':
            continue
        require(len(snapshot['economic_review_ids']) == 1)
        review = reviews.get(snapshot['economic_review_ids'][0])
        require(review and review['company_id'] == snapshot['company_id'] and review['source_snapshot_id'] == snapshot['parent_snapshot_id'])
        require(snapshot['valuation_ids'] == ([review['valuation_id']] if review['valuation_id'] else []))
        require(snapshot['core']['valuation'] == dict(review_id=review['review_id'], valuation_id=review['valuation_id'],
            operating_model_id=review['operating_model_id'], status=review['status'], usable_range=review['usable_range']))

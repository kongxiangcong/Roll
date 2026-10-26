"""Company valuation relationship checks at the public backup/recovery boundary."""
import json
from .service import verified, fingerprint, fail


def validate_valuations(db, archives, companies):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'company_research_valuation_inputs' not in names:
        return

    def require(condition):
        if not condition:
            fail('RESEARCH_REFERENCE_INVALID', 'Valuation relationships or canonical archive hashes differ', 409)

    def records(table, key):
        require('company_research_' + table in names)
        return {r[0]: verified(json.loads(r[1])) for r in db.execute(f'SELECT {key},value FROM company_research_{table}')}

    def archive(item):
        require(isinstance(item, dict) and archives.get(item.get('sha256')) == item)

    inputs = records('valuation_inputs', 'version_id')
    results = records('valuations', 'valuation_id')
    snapshots = records('snapshots', 'snapshot_id')
    analysis_inputs = records('inputs', 'input_id')
    identities = {c['version_id']: c for c in companies}
    for value in inputs.values():
        snapshot = snapshots.get(value['snapshot_id'])
        require(snapshot and snapshot['company_id'] == value['company_id'] and snapshot['content_sha256'] == value['snapshot_sha256'])
        require(value['company_identity'] == identities.get(value['company_identity']['version_id']))
        require(value['company_identity'] == analysis_inputs[snapshot['input_id']]['payload']['company'])
        require(value['fact_version_ids'] == snapshot['fact_version_ids'] and value['hypothesis_version_ids'] == snapshot['hypothesis_version_ids'])
        require(value['economic_status'] == 'unreviewed' and value['usable_range'] is False)
        archive(value['input_archive'])
        require(fingerprint({k: v for k, v in value.items() if k not in {'input_archive', 'content_sha256'}}) == value['input_archive']['sha256'])
        for item in value['algorithm']['files']:
            archive(item['archive'])
        parent = inputs.get(value['parent_version_id'])
        require(value['parent_version_id'] is None and value['revision'] == 1 or parent and parent['company_id'] == value['company_id'] and parent['entity_id'] == value['entity_id'] and parent['revision'] + 1 == value['revision'])
    for value in results.values():
        frozen = inputs.get(value['input_version_id'])
        require(frozen and frozen['company_id'] == value['company_id'] and frozen['snapshot_id'] == value['snapshot_id'])
        require(value['input_sha256'] == frozen['content_sha256'] and value['algorithm'] == frozen['algorithm'])
        require(value['result']['usable_range'] is False and value['result']['review']['status'] == 'unreviewed')
        archive(value['result_archive'])
        require(fingerprint({k: v for k, v in value.items() if k not in {'result_archive', 'content_sha256'}}) == value['result_archive']['sha256'])

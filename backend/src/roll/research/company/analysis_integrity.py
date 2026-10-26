"""Research analysis relationship validation used by the existing backup boundary."""
import json
from .service import verified, fingerprint, fail


def validate_analysis(db, archives, materials, facts, companies):
    names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'company_research_inputs' not in names:
        return

    def require(condition):
        if not condition:
            fail('RESEARCH_REFERENCE_INVALID', 'Frozen analysis references are missing or inconsistent', 409)

    def records(table, key):
        require('company_research_' + table in names)
        return {r[0]: verified(json.loads(r[1])) for r in db.execute(f'SELECT {key},value FROM company_research_{table}')}

    inputs = records('inputs', 'input_id')
    snapshots = records('snapshots', 'snapshot_id')
    hypotheses = records('hypotheses', 'version_id')
    runs = records('analysis_runs', 'run_id')
    candidates = records('candidates', 'candidate_id')
    company_versions = {c['version_id']: c for c in companies}
    company_ids = {c['company_id'] for c in companies}

    def archive(value):
        require(isinstance(value, dict) and archives.get(value.get('sha256')) == value)

    for packet in inputs.values():
        require(packet['company_id'] in company_ids)
        payload = packet['payload']
        require(company_versions.get(payload['company']['version_id']) == payload['company'])
        require(payload['company']['company_id'] == packet['company_id'])
        require(fingerprint(payload) == packet['packet_sha256'] == packet['input_archive']['sha256'])
        archive(packet['input_archive'])
        require(packet['fact_version_ids'] == [f['version_id'] for f in payload['facts']])
        require(packet['material_ids'] == [m['material_id'] for m in payload['materials']])
        for f in payload['facts']:
            require(facts.get(f['version_id']) == f and f['company_id'] == packet['company_id'])
            require(f['material_id'] in packet['material_ids'])
        for material in payload['materials']:
            require(materials.get(material['material_id']) == material and material['company_id'] == packet['company_id'])
        for h in payload['prior_hypotheses']:
            require(hypotheses.get(h['version_id']) == h and h['company_id'] == packet['company_id'])
        for conflict in payload['conflicts']:
            require(all(i in packet['fact_version_ids'] and facts[i]['fact_id'] == conflict['fact_id'] for i in conflict['version_ids']))
            if conflict['resolution']:
                resolution = conflict['resolution']
                row = db.execute('SELECT value FROM company_research_conflict_resolutions WHERE resolution_id=?', (resolution['resolution_id'],)).fetchone()
                require(row and verified(json.loads(row[0])) == resolution and resolution['company_id'] == packet['company_id'])
        parent = snapshots.get(packet['parent_snapshot_id'])
        require(packet['parent_snapshot_id'] is None or parent and parent['company_id'] == packet['company_id'])

    for h in hypotheses.values():
        require(h['company_id'] in company_ids)
        for identifier in h['support_fact_version_ids'] + h['counter_fact_version_ids'] + h['next_validation_event']['date_fact_version_ids']:
            require(identifier in facts and facts[identifier]['company_id'] == h['company_id'])
        parent = hypotheses.get(h['parent_version_id'])
        require(h['parent_version_id'] is None and h['revision'] == 1 or parent and
                parent['company_id'] == h['company_id'] and parent['hypothesis_id'] == h['hypothesis_id'] and parent['revision'] + 1 == h['revision'])

    for snapshot in snapshots.values():
        packet = inputs.get(snapshot['input_id'])
        require(packet and packet['company_id'] == snapshot['company_id'])
        require(snapshot['input_sha256'] == packet['packet_sha256'] and snapshot['input_archive'] == packet['input_archive'])
        require(snapshot['parent_snapshot_id'] == packet['parent_snapshot_id'] and snapshot['parent_snapshot_id'] != snapshot['snapshot_id'])
        require(snapshot['fact_version_ids'] == packet['fact_version_ids'] and snapshot['material_ids'] == packet['material_ids'])
        require(fingerprint(snapshot['core']) == snapshot['core_sha256'])
        archive(snapshot['candidate_archive'])
        require(snapshot['candidate_sha256'] == snapshot['candidate_archive']['sha256'])
        if snapshot.get('raw_output_archive'):
            archive(snapshot['raw_output_archive'])
        require(snapshot['hypothesis_version_ids'] == [h['version_id'] for h in snapshot['core']['hypotheses']])
        for h in snapshot['core']['hypotheses']:
            require(hypotheses.get(h['version_id']) == h and h['company_id'] == snapshot['company_id'])
            require(set(h['support_fact_version_ids'] + h['counter_fact_version_ids']) <= set(packet['fact_version_ids']))
        for field in ['business_structure', 'attention_reasons', 'counterevidence']:
            for claim in snapshot['core'][field]:
                require(set(claim['fact_version_ids']) <= set(packet['fact_version_ids']))

    for candidate in candidates.values():
        packet = inputs.get(candidate['input_id'])
        require(packet and packet['company_id'] == candidate['company_id'])
        archive(candidate['candidate_archive'])
        require(candidate['candidate_sha256'] == candidate['candidate_archive']['sha256'])

    for run in runs.values():
        packet = inputs.get(run['input_id'])
        require(packet and packet['company_id'] == run['company_id'])
        if run.get('candidate_output_archive'):
            archive(run['candidate_output_archive'])
        if run.get('snapshot_id'):
            snapshot = snapshots.get(run['snapshot_id'])
            require(snapshot and snapshot['input_id'] == run['input_id'] and snapshot['company_id'] == run['company_id'])

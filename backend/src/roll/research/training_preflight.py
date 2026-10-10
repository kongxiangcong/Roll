"""Read registered metadata without consuming inputs or a model-fit attempt."""
import hashlib
from typing import Literal
from fastapi import HTTPException

from roll.accounts.ledger import encode


TrainingPurpose = Literal['RESEARCH', 'METHOD_VALIDATION']


def admit_model_training(registry, protocol_id, purpose: TrainingPurpose):
    """HTTP command admission; keep existing numerical code/artifact fingerprints intact."""
    protocol = registry.get(protocol_id)
    if purpose == 'RESEARCH':
        # Metadata only: never decode source, partitions, or labels to rediscover known gaps.
        preflight = training_preflight(registry, protocol_id, purpose)
        if not preflight['ready_to_fit']:
            raise HTTPException(409, {'code': 'TRAINING_ADMISSION_BLOCKED',
                'blockers': preflight['blockers'], 'checks': preflight['checks'],
                'budget': preflight['budget'], 'attempt_started': False,
                'assessment': preflight['assessment']})
    else:
        dataset = registry.dataset(protocol['dataset_id']) if protocol['dataset_id'] else None
        if dataset is None or dataset['source_evidence_kind'] != 'METHOD_CASE':
            raise HTTPException(409, {'code': 'METHOD_VALIDATION_REQUIRES_METHOD_CASE',
                'attempt_started': False})
        preflight = training_preflight(registry, protocol_id, purpose)
        if preflight['budget']['calibration']['exhausted']:
            raise HTTPException(409, {'code': 'CALIBRATION_BUDGET_EXHAUSTED',
                'budget': preflight['budget'], 'attempt_started': False})


def training_preflight(registry, protocol_id, purpose: TrainingPurpose = 'RESEARCH'):
    protocol = registry.get(protocol_id)
    dataset = registry.dataset(protocol['dataset_id']) if protocol['dataset_id'] else None
    manifest = registry.attempt_manifest(protocol_id)
    attempts = [{
        **{key: value[key] for key in ['attempt_id', 'protocol_id', 'category',
                                      'partition', 'status', 'started_at']},
        'host_owner': value.get('host_owner'),
        'configuration_sha256': hashlib.sha256(encode(value['configuration']).encode()).hexdigest(),
        'completion_recorded_at': value.get('completion', {}).get('recorded_at'),
    } for value in manifest['attempts']]
    budget = {}
    for name, categories, limit in [('primary_and_neighbors', ['PRIMARY_FIT', 'G5_NEIGHBOR'], 5),
                                    ('calibration', ['CALIBRATION'], 1)]:
        used = sum(value['category'] in categories for value in attempts)
        budget[name] = {'categories': categories, 'limit': limit, 'used': used,
                        'remaining': max(0, limit - used), 'exhausted': used >= limit}
    source = None
    windows = {}
    blockers = []
    checks = {'source_artifact_integrity': 'NOT_CHECKED',
              'training_inputs_labels_and_support': 'NOT_CHECKED',
              'historical_point_in_time': 'NO_REGISTERED_EVIDENCE',
              'real_training_path': 'NOT_IMPLEMENTED'}
    if dataset:
        readiness = dataset.get('training_readiness', {})
        source = {'origin': dataset.get('source_origin', 'HOST_ENGINEERING_ARCHIVE'),
                  'evidence_kind': dataset['source_evidence_kind'],
                  'run_id': dataset['source_run_id'], 'snapshot_id': dataset['source_snapshot_id'],
                  'data_fingerprint': dataset['data_fingerprint'],
                  'registered_training_readiness': readiness.get('state', 'NOT_ESTABLISHED')}
        # Seal independence is a later confirmatory-validation condition, not a ticket19 fit prerequisite.
        blockers.extend(gap for gap in readiness.get('blockers', [])
                        if gap not in {'HISTORICAL_SEAL_INDEPENDENCE_UNPROVEN', 'SEALED_INDEPENDENCE_UNPROVEN'})
        if dataset['scope'].get('historical_point_in_time_proven'):
            checks['historical_point_in_time'] = 'REGISTERED_PROOF_NOT_REVALIDATED'
        else:
            checks['historical_point_in_time'] = 'NOT_PROVEN_IN_REGISTRATION'
            blockers.append('HISTORICAL_POINT_IN_TIME_NOT_PROVEN')
        for name in ['DEVELOPMENT', 'CALIBRATION']:
            metadata = dataset['partitions'].get(name, {})
            windows[name] = {key: metadata[key] for key in ['state', 'rows', 'context_rows',
                             'first_date', 'last_date', 'context_first_date'] if key in metadata}
            if metadata.get('state') != 'HOST_FILTERED':
                blockers.append('RESEARCH_WINDOWS_NOT_PREREGISTERED' if metadata.get('state') == 'NOT_PREREGISTERED'
                                else 'RESEARCH_WINDOW_COVERAGE_INSUFFICIENT')
        if dataset['source_evidence_kind'] == 'METHOD_CASE':
            blockers.append('METHOD_CASE_NOT_REAL_RESEARCH_DATA')
        elif purpose == 'METHOD_VALIDATION':
            blockers.append('METHOD_VALIDATION_REQUIRES_METHOD_CASE')
    else:
        blockers.append('DATASET_NOT_REGISTERED')
    blockers.extend(['REAL_TRAINING_PATH_NOT_IMPLEMENTED', 'TRAINING_INPUTS_LABELS_AND_SUPPORT_NOT_CHECKED'])
    if budget['primary_and_neighbors']['exhausted']:
        blockers.append('PRIMARY_FIT_BUDGET_EXHAUSTED')
    if budget['calibration']['exhausted']:
        blockers.append('CALIBRATION_BUDGET_EXHAUSTED')
    return {
        'protocol_id': protocol_id, 'purpose': purpose, 'assessment': 'METADATA_ONLY',
        'ready_to_fit': False, 'dataset_id': protocol['dataset_id'],
        'readiness_scope': 'ACTUAL_RESEARCH_TRAINING; METHOD_VALIDATION never upgrades real readiness',
        'source': source, 'registered_windows': windows,
        'blockers': list(dict.fromkeys(blockers)), 'checks': checks,
        'budget': budget,
        'budget_basis': 'All registered family attempts count, regardless of terminal status. '
                        'This read is not a reservation; attempt start rechecks the budget transactionally.',
        'attempt_manifest': {**{key: manifest[key] for key in ['lineage', 'family_protocol_ids',
                                                             'attempt_ids', 'basis']},
                             'attempts': attempts},
    }

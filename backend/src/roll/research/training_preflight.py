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
    if dataset and dataset.get('data_use')=='RECONSTRUCTED_RESEARCH':
        return reconstructed_preflight(registry,protocol,dataset,budget,manifest,attempts,purpose)
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


def reconstructed_preflight(registry,protocol,dataset,budget,manifest,attempts,purpose):
    """Actual source/feature/mature-support preflight, not a statistical fit attempt."""
    from roll.research.reconstruction import fingerprint
    blockers=[];checks={'historical_point_in_time':'NOT_PROVEN; RECONSTRUCTED_PURPOSE_ONLY','real_training_path':'IMPLEMENTED_RECONSTRUCTED_SCOPE',
        'source_artifact_integrity':'NOT_CHECKED','training_inputs_labels_and_support':'NOT_CHECKED'}
    counts={};exclusions={};windows={n:{k:v for k,v in dataset['partitions'][n].items() if k!='artifact'} for n in ['DEVELOPMENT','CALIBRATION']}
    if purpose!='RESEARCH':blockers.append('METHOD_VALIDATION_REQUIRES_METHOD_CASE')
    if dataset['source_evidence_kind']!='REAL_ACQUISITION':blockers.append('METHOD_CASE_NOT_REAL_RESEARCH_DATA')
    try:
        if dataset['reconstruction_code_fingerprint']!=fingerprint():raise ValueError('RECONSTRUCTION_ALGORITHM_VERSION_CHANGED_REGISTER_NEW_VERSION')
        for archive in [*dataset['original_archives'],dataset['clean_archive'],dataset['assumptions_archive'],dataset['quality_report_archive']]:registry.evidence.raw(archive['sha256'])
        parts={n:registry.partition(dataset['dataset_id'],n) for n in windows}
        if parts['DEVELOPMENT']['metadata']['last_date']>=parts['CALIBRATION']['metadata']['first_date']:raise ValueError('DEV_CAL_TIME_OVERLAP')
        support={n:registry.executions.support(protocol['protocol_id'],n) for n in windows}
        examples,excluded=registry.models.prepare_examples(protocol,support,parts,False)
        for name,items in examples.items():
            classes={str(y):sum(r['label']==y for r in items) for y in [0,1]}
            counts[name]={'feature_and_mature_label_count':len(items),'per_class':classes,'independent_sample_count':None,
                'daily_count_divided_by_horizon':len(items)//20,'latest_label_end':max((r['maturity_date'] for r in items),default=None)}
            exclusions[name]=excluded[name]
        if any(not counts['DEVELOPMENT']['per_class'][str(y)] for y in [0,1]):blockers.append('DEVELOPMENT_BOTH_CLASSES_REQUIRED')
        if any(counts['CALIBRATION']['per_class'][str(y)]<protocol['design']['statistics']['minimum_calibration_examples_per_class'] for y in [0,1]):blockers.append('CALIBRATION_PER_CLASS_SUPPORT_BELOW_20')
        checks.update(source_artifact_integrity='VERIFIED',training_inputs_labels_and_support='CHECKED')
    except (HTTPException,ValueError,KeyError,ArithmeticError) as error:
        blockers.append(str(error.detail if isinstance(error,HTTPException) else error))
    for name,code in [('primary_and_neighbors','PRIMARY_FIT_BUDGET_EXHAUSTED'),('calibration','CALIBRATION_BUDGET_EXHAUSTED')]:
        if budget[name]['exhausted']:blockers.append(code)
    return {'protocol_id':protocol['protocol_id'],'dataset_id':dataset['dataset_id'],'purpose':purpose,'assessment':'HOST_RECONSTRUCTED_INPUTS_AND_MATURE_SUPPORT',
        'ready_to_fit':not blockers,'source':{'evidence_kind':dataset['source_evidence_kind'],'data_use':dataset['data_use'],'data_fingerprint':dataset['data_fingerprint']},
        'registered_windows':windows,'support':counts,'excluded':exclusions,'checks':checks,'blockers':list(dict.fromkeys(blockers)),'budget':budget,
        'budget_basis':'All prior family failures retained; this support check is not a fit or reservation',
        'attempt_manifest':{**{k:manifest[k] for k in ['lineage','family_protocol_ids','attempt_ids','basis']},'attempts':attempts},
        'strict_historical_as_of_allowed':False,'capability':'NOT_GRANTED','calibration_validity':'NOT_INDEPENDENTLY_VALIDATED'}

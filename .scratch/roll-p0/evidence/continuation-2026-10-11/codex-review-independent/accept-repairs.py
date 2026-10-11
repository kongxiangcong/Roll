"""Independent literal/public METHOD acceptance; reuse stopped model, never fit or call SDK."""
import copy
from datetime import date, timedelta
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[5]
SCOPE = Path(__file__).resolve().parent
SOURCE = ROOT / '.scratch/worktrees/codex-review-fixes'
EVIDENCE = SOURCE / '.scratch/roll-p0/evidence/codex-review-repairs-2026-10-11'
PROFILE = ROOT / '.roll-data/implementation-evidence/codex-review-fixes/independent-method-successor-02'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (SCOPE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def literal_checks():
    from roll.research.shadow import simulate
    from roll.research.statistics import paired_block_interval
    from roll.research.validation import probability_checks, continuous_checks
    days = [(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(120)]
    rule = {'state': 'CONFIRMED_NORMAL', 'company_actions': 'CONFIRMED_NONE',
        'price_tick_yuan': '.01', 'normal_price_limit_percent': '10'}
    frozen = {'baseline': {'cash_yuan': '80000.00', 'positions': []}, 'scope': {'instruments': ['METHOD:A']},
        'rules': {'METHOD:A': rule}, 'fingerprints': {'model': 'LITERAL_ONLY'},
        'policy': {'quantity': '200', 'probability_threshold': '.60', 'maximum_gross_exposure': '.50', 'exit': 'HORIZON_SESSION20_CLOSE'},
        'design': {'event': 'LITERAL', 'costs': {k: '0' for k in ['minimum_commission_yuan', 'commission_scenario_rate',
            'transfer_each_side_rate', 'stamp_sell_rate', 'extra_regulatory_charge', 'slippage_each_side_rate']},
            'primary_objective': {'risk_constraints': {'maximum_drawdown': '.10', 'maximum_simulated_gross_exposure': '.50',
                'minimum_decision_coverage': '.20', 'candidate_drawdown_excess_over_risk_matched_baseline': '.02'},
                'minimum_improvement_nav_return': '.0025'}, 'statistics': {'minimum_effective_time_blocks': 30}}}
    def inputs(prices):
        return {'sessions': days[20:], 'facts': [{'trade_date': d, 'instrument': 'METHOD:A', 'open': str(p), 'close': str(p),
            'high': str(p + 1), 'low': str(p - 1), 'volume_shares': '10000', 'errors': [],
            'completion_state': 'COMPLETE_REPORTED_HISTORICAL', 'execution_evidence': rule} for d,p in zip(days,prices)],
            'statutory': {}, 'cash_events': []}
    rising = inputs([Decimal('70') + Decimal('.2') * i for i in range(120)])
    no_cross = simulate(frozen, rising, [], days[-1], 'MA5_MA20')
    assert no_cross['events'] == no_cross['opportunities'] == [] and no_cross['nav_yuan'] == '80000.00'
    crossing = inputs([Decimal('70')] * 20 + [Decimal('70') + Decimal('.2') * (i+1) for i in range(100)])
    one_cross = simulate(frozen, crossing, [], days[-1], 'MA5_MA20')
    fills = [(e['kind'],e['date'],e['quantity'],e['price_yuan']) for e in one_cross['events']]
    assert fills == [('BUY_FILL', days[21], '200', '70.40'), ('SELL_FILL', days[40], '200', '74.20')]
    assert one_cross['cash_yuan'] == one_cross['nav_yuan'] == '80760.00' and len(one_cross['opportunities']) == 1
    bad = copy.deepcopy(crossing)
    bad['facts'][20]['execution_evidence'] = {**bad['facts'][20]['execution_evidence'], 'state':'UNKNOWN'}
    assert simulate(frozen,bad,[],days[-1],'MA5_MA20')['events'] == []
    constant = inputs([Decimal('70')] * 120)
    cash = simulate(frozen,constant,[],days[-1])
    hold = simulate(frozen,constant,[],days[-1],'START_HOLD')
    comparison = continuous_checks(frozen,cash,{'START_HOLD':hold})['comparisons']['START_HOLD']
    assert comparison['baseline_exposure']['maximum_gross_exposure'] == .175
    assert comparison['position_difference']['maximum_gross_exposure'] == -.175
    assert comparison['baseline_exposure']['occupied_session_fraction'] == .99
    assert comparison['risk_matching'] == 'COMMON_CONSTRAINTS_DO_NOT_ESTABLISH_REALIZED_RISK_MATCHING'
    # Unequal same-day counts: ratio is .55, whereas averaging member-date means is .30.
    calendar = [{'date': f'{i:04}', 'scores': {'A': -.2} if i%4 == 0 else
        {'A': .8, 'B': .8, 'C': .8} if i%4 == 1 else {}} for i in range(240)]
    intervals = [paired_block_interval(calendar, block_sessions=b, conditional=True) for b in [20,40]]
    for v in intervals:
        assert v['mean'] == .55 and v['member_count'] == 240 and v['member_calendar_sessions'] == 120
        assert v['lower_95'] <= .55 <= v['upper_95'] and v['statistical_pass'] is False
        assert v == paired_block_interval(calendar,block_sessions=v['block_sessions'],conditional=True)
    empty = paired_block_interval([{'date':f'{i:04}','scores':{}} for i in range(80)], conditional=True)
    assert empty['status'] == 'INSUFFICIENT_MEMBER_SUPPORT' and empty['lower_95'] is None
    missing = copy.deepcopy(calendar); missing[5]['scores'] = {'UNKNOWN': None}
    assert paired_block_interval(missing,conditional=True)['status'] == 'INCOMPLETE_ALIGNED_CALENDAR_SCORES'
    dates = days
    forecasts = [{'forecast_id':str(i),'instrument':'METHOD:A','observation_cutoff':d,'probability':.75 if i%2 else .25} for i,d in enumerate(dates)]
    outcomes = {str(i):{'label':i%2,'scoreable':True,'maturity_date':days[-1]} for i in range(120)}
    original = {'model':{'model_run_id':'LITERAL_NOT_FITTED'},'model_artifact':{'base_rate':.5},'replay':{'inputs':{'sessions':dates,'counterfactuals':outcomes},
        'forecasts':forecasts,'through_date':days[-1]}}
    probability = probability_checks(frozen,original)
    assert probability['selected_mature'] == 60 and probability['unobserved_checkpoint_sessions'] == 0
    assert all(i['mean'] == i['lower_95'] == i['upper_95'] == .1875 for i in probability['selected_dependent_loss_intervals'])
    duplicated = copy.deepcopy(original); duplicated['replay']['forecasts'].append(dict(forecasts[1]))
    repeated = probability_checks(frozen,duplicated)
    assert repeated['duplicate_event_count'] == 1 and repeated['selected_dependent_loss_intervals'] == probability['selected_dependent_loss_intervals']
    unknown = copy.deepcopy(original); unknown['replay']['inputs']['counterfactuals']['4']['label'] = None
    unavailable = probability_checks(frozen,unknown)
    assert unavailable['unobserved_checkpoint_sessions'] == 1
    assert all(i['status'] == 'INCOMPLETE_ALIGNED_CALENDAR_SCORES' for i in unavailable['selected_dependent_loss_intervals'])
    return {'already_above_no_cross_events':0,'single_cross_fills':fills,'final_NAV':'80760.00',
        'risk_difference':comparison,'weighted_conditional_intervals':intervals,'empty_subset':empty,
        'true_missing_preserved':True,'duplicate_support_not_increased':True,'qualifies_real_model':False}


def main():
    os.environ['ROLL_ENV'] = 'test'
    os.environ.pop('ROLL_ENV_FILE',None)
    for key in ['ROLL_CODEX_AUTH_FILE','DEEPSEEK_API_KEY','ROLL_DEEPSEEK_API_KEY_FILE','ROLL_TEST_CRASH_POINT','ROLL_TEST_BOOTSTRAP_FAULT']:
        os.environ.pop(key,None)
    sys.path.insert(0,str(SOURCE / 'backend/src'))
    expected_sources = json.loads((EVIDENCE / 'source-final.json').read_text(encoding='utf-8'))
    before_sources = {i['path']:sha(SOURCE / i['path']) for i in expected_sources}
    assert all(before_sources[i['path']] == i['sha256'] for i in expected_sources)
    original_record = ROOT / '.scratch/roll-p0/evidence/continuation-2026-10-11/review-fixes/actual-codex-continuation-results.json'
    record_sha = sha(original_record)
    preservation = []
    for label in ['old','new','final']:
        manifest = json.loads((EVIDENCE / ('runtime-'+label+'-method-manifest.json')).read_text(encoding='utf-8'))
        source, target = Path(manifest['source']), Path(manifest['destination'])
        assert len(manifest['files']) == manifest['file_count']
        for item in manifest['files']:
            for base in [source,target]:
                path = base / item['path']
                assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256']
        preservation.append({'profile':label,'files':manifest['file_count'],'sha_length_mismatches':0})
    assert not PROFILE.exists()
    source = ROOT / '.roll-data/implementation-evidence/codex-review-fixes/old-method'
    copied = []
    for path in source.rglob('*'):
        if not path.is_file(): continue
        relative = path.relative_to(source)
        assert not path.is_symlink() and not path.name.lower() in {'.env','auth.json'}
        if relative.parts[0] == 'backups' or relative.name == '.startup.lock': continue
        destination = PROFILE / relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,destination)
        assert sha(path) == sha(destination)
        copied.append({'path':str(relative),'bytes':path.stat().st_size,'sha256':sha(path)})
    save('copied-method-profile.json',{'source':str(source),'target':str(PROFILE),'files':copied,'no_auth_or_environment':True})
    literal = literal_checks()
    from fastapi.testclient import TestClient
    import httpx
    from roll.app import create_app
    meta = json.loads((EVIDENCE / 'old-method-identities.json').read_text(encoding='utf-8'))
    def snapshot():
        with sqlite3.connect((PROFILE / 'roll.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
            names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('research_models','research_forecasts','research_attempts','research_validation_attempts')")]
            return {name:sorted(hashlib.sha256(repr(tuple(row)).encode()).hexdigest() for row in db.execute('SELECT * FROM '+name)) for name in names}
    retained = snapshot()
    network = []
    def deny(request):
        network.append(str(request.url).split('?')[0]); raise RuntimeError('METHOD no network')
    def app(): return create_app(PROFILE,market_transport=httpx.MockTransport(deny))
    with TestClient(app()) as client:
        def get(path):
            response = client.get(path); response.raise_for_status(); return response.json()
        def post(path,body):
            response = client.post(path,json=body); response.raise_for_status(); return response.json()
        old_freeze = get('/api/research/complete-freezes/'+meta['freeze_id'])
        old_validation = get('/api/research/validations/'+meta['validation_id'])
        old_shadow = get('/api/research/shadow/'+meta['freeze_id'])
        # Only the cloned synthetic METHOD shadow-input archive is inspected.
        old_input_path = (PROFILE / old_shadow['input_archive']['path']).resolve()
        assert old_input_path.is_relative_to(PROFILE.resolve())
        assert sha(old_input_path) == old_shadow['input_archive']['sha256']
        old_input = json.loads(old_input_path.read_text(encoding='utf-8'))
        assert client.post('/api/research/shadow/'+meta['freeze_id']+'/replay').status_code == 409
        assert client.post('/api/research/validations/'+meta['validation_id']+'/replay').status_code == 409
        old_protocol = get('/api/research/protocols/'+old_freeze['protocol_id'])
        model = get('/api/research/models/'+old_freeze['model_run_id'])
        protocol = post('/api/research/protocols',{'dataset_id':old_protocol['dataset_id'],'predecessor_id':old_protocol['protocol_id'],
            'basis':'Independent METHOD comparator/subset algorithm successor; reused existing model and attempts; no fit'})
        attempts = get('/api/research/protocols/'+protocol['protocol_id']+'/attempt-manifest')
        frozen = post('/api/research/protocols/'+protocol['protocol_id']+'/complete-freezes',{'model_run_id':model['model_run_id'],
            'attempt_ids':attempts['attempt_ids'],'artifact_fingerprints':model['artifact_fingerprints'],
            'baseline':old_freeze['baseline'],'basis':'Independent METHOD source-version successor; original old freeze preserved'})
        assert frozen['method_validation']['version'] == '20-method-v2'
        assert frozen['method_validation']['comparator_contract']['MA5_MA20']['exit'] == 'HORIZON_SESSION20_CLOSE'
        assert frozen['statistical_methods']['version'] == '20-statistical-method-v2'
        assert frozen['predecessor_protocol_id'] == old_protocol['protocol_id']
        path = '/api/research/shadow/'+frozen['freeze_id']
        shadow = post(path+'/advance',{'through_date':old_shadow['through_date'],
            'forecast_ids':[f['forecast_id'] for f in old_input['forecasts']],'expected_revision':0})
        assert client.post(path+'/replay').json()['matches_original'] is True
        validation = post('/api/research/complete-freezes/'+frozen['freeze_id']+'/validations',{'purpose':'DIAGNOSTIC',
            'expected_complete_protocol_fingerprint':frozen['complete_protocol_fingerprint'],'basis':'Independent METHOD exposure/schema and immutable replay'})
        for c in validation['gates']['G4']['details']['comparisons'].values():
            assert 'position_difference' in c and c['baseline_exposure']['unknown_sessions'] == 0
        assert validation['capability_status'] == 'NOT_GRANTED' and validation['system_usable'] is False
        assert validation['sealed_read'] is validation['confirmation_pass_look'] is False
        assert get('/api/account')['version'] == 0 and get('/api/research/protocols/'+protocol['protocol_id'])['forward_started_at'] is None
        assert client.post('/api/research/validations/'+validation['validation_id']+'/replay').json()['matches_original'] is True
        assert get('/api/research/complete-freezes/'+meta['freeze_id']) == old_freeze
        assert get('/api/research/validations/'+meta['validation_id']) == old_validation
    with TestClient(app()) as client:
        assert client.get('/api/research/complete-freezes/'+frozen['freeze_id']).json() == frozen
        assert client.get('/api/research/validations/'+validation['validation_id']).json() == validation
        assert client.post(path+'/replay').json()['matches_original'] is True
        assert client.post('/api/research/validations/'+validation['validation_id']+'/replay').json()['matches_original'] is True
        assert client.post('/api/research/shadow/'+meta['freeze_id']+'/replay').status_code == 409
    final = snapshot()
    for name in ['research_models','research_forecasts']:
        assert final.get(name) == retained.get(name)
    assert final['research_attempts'] == retained['research_attempts']
    assert len(final['research_validation_attempts']) == len(retained['research_validation_attempts']) + 1
    assert not network and sha(original_record) == record_sha
    assert before_sources == {i['path']:sha(SOURCE / i['path']) for i in expected_sources}
    # Source root preservation copies remain byte-identical; none were opened as a Host.
    for label in ['old','new','final']:
        manifest = json.loads((EVIDENCE / ('runtime-'+label+'-method-manifest.json')).read_text(encoding='utf-8'))
        assert all(sha(Path(manifest['destination'])/i['path']) == i['sha256'] for i in manifest['files'])
    save('independent-results.json',{'status':'PASS','evidence_kind':'METHOD_CASE','literal':literal,
        'preserved_runtime_profiles':preservation,'profile_copy_no_fit':True,'old_shadow_and_validation_409':True,
        'old_freeze_and_manifest_unchanged':True,'new_freeze_id':frozen['freeze_id'],'new_validation_id':validation['validation_id'],
        'restart_replay_match':True,'network_calls':0,'provider_calls':0,'new_model_or_forecast_count':0,
        'added_attempts':'1 DIAGNOSTIC only','SEALED_read':False,'account_version':0,'forward_started_at':None,
        'NOT_GRANTED':True,'source18_stable':True,'original_sanitized_ReviewRecord_unchanged':True})
    print('independent repair literal/public METHOD successor/restart/version-guard acceptance PASS; no fit/provider/SEALED')


if __name__ == '__main__': main()

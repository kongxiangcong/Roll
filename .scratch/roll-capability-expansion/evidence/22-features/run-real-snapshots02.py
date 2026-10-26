"""Actual saved sources only: current deterministic features and honest old gaps."""
import hashlib,json,shutil
from pathlib import Path
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from roll.app import create_app
from roll.research.models import code_fingerprint
repo=Path(__file__).resolve().parents[4];p=Path(__file__).resolve().parent
freeze=json.loads((p/'runtime02-freeze.json').read_bytes())
for name,sha in freeze['files'].items():assert hashlib.sha256((repo/name).read_bytes()).hexdigest()==sha,name
source=repo/'.scratch/r18-runtime04';target=repo/'.scratch/r22-real02';assert not target.exists()
original_sha=hashlib.sha256((source/'roll.sqlite3').read_bytes()).hexdigest();shutil.copytree(source,target)
model_code=code_fingerprint();cutoff=datetime.now(timezone.utc).isoformat()
with TestClient(create_app(target,runtime_role='API')) as client:
 before_account=client.get('/api/account').json()['version']
 protocols=client.get('/api/research/protocols').json()
 series=client.get('/api/market/sentiment-series/SSE:600362/snapshots').json()
 selected=next(row for row in series if 'FinBERT' in row['model'])
 command={'idempotency_key':'actual-current-features','basis':'Actual saved-source feature observation; no retrospective prediction claim or training','instrument':'SSE:600362','known_by':cutoff,'series_id':selected['series_id']}
 response=client.post('/api/research/feature-snapshots',json=command);assert response.status_code==201,response.text
 current=response.json()
 assert current['evidence_kind']=='REAL_SAVED_FEATURE_OBSERVATION'
 assert current['financial']['debt_ratio']['value']=='65.475577'
 assert current['financial']['cash_profit_ratio']['value']=='0.611974'
 assert all(value['value'] is None for value in current['sentiment'].values())
 assert current['sentiment_quality_gate_passed'] and current['sentiment_labels_supported']==['POSITIVE','NEGATIVE','NEUTRAL']
 assert current['sentiment']['positive_share']['reason']=='VERSION_NOT_AVAILABLE'
 assert client.post('/api/research/feature-snapshots',json=command).json()==current
 old=client.post('/api/research/feature-snapshots',json={**command,'idempotency_key':'actual-old-gap','known_by':'2026-10-01T15:06:00+08:00','series_id':None}).json()
 assert all(value['value'] is None for value in old['financial'].values())
 assert not old['historical_pit_eligible']
 assert client.get('/api/account').json()['version']==before_account==0
 assert not protocols and client.get('/api/research/feature-plans').json()==[]
 missing=client.get('/api/research/feature-budget/no-such-existing-family')
 assert missing.status_code==404
 (p/'real02-current-snapshot.json').write_text(json.dumps(current,ensure_ascii=False,indent=2),encoding='utf-8')
 (p/'real02-historical-gap.json').write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
with TestClient(create_app(target,runtime_role='API')) as client:
 assert client.get('/api/research/feature-snapshots/'+current['snapshot_id']).json()==current
 assert client.get('/api/research/feature-snapshots/'+old['snapshot_id']).json()==old
 assert client.get('/api/account').json()['version']==0
 assert client.get('/api/research/protocols').json()==[]
 assert code_fingerprint()==model_code
 assert hashlib.sha256((source/'roll.sqlite3').read_bytes()).hexdigest()==original_sha
 summary={'status':'COMPLETE','evidence_kind':'REAL_SAVED_FEATURE_OBSERVATION','data_directory':str(target),'source_db_sha256':original_sha,'source_unchanged':True,'snapshot_id':current['snapshot_id'],'old_gap_snapshot_id':old['snapshot_id'],'financial':{key:value['value'] for key,value in current['financial'].items()},'sentiment':'all missing: new-model classification available after current checkpoint; tomorrow pending','real_family_registration':'No existing same-scope family in saved-source copy or current .roll-data/pit metadata; did not manufacture new root or fit budget','model_fingerprint_unchanged':True,'public_replay_after_restart':True,'network_calls':0,'model_calls':0,'fits':0,'sealed_reads':0,'account_before':0,'account_after':0,'at':datetime.now(timezone.utc).isoformat()}
 (p/'real02-runtime-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))

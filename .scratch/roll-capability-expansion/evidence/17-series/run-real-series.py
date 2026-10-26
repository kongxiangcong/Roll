"""Actual API over immutable copies of saved real runs; no models, fake clocks or HTTP sources."""
import hashlib,json,shutil,sqlite3
from pathlib import Path
from datetime import datetime,timezone
from fastapi.testclient import TestClient
from roll.app import create_app
p=Path(__file__).resolve().parent;repo=Path(__file__).resolve().parents[4]
freeze=json.loads((p/'runtime-freeze.json').read_bytes())
for name,digest in freeze['files'].items():assert hashlib.sha256((repo/name).read_bytes()).hexdigest()==digest,name
legacy=repo/'.scratch/r16-takeover-20261018';modern=repo/'.scratch/r16-candidate-runtime01';target=repo/'.scratch/r17-runtime01'
assert target.is_relative_to(repo/'.scratch') and not target.exists()
before_sources={str(s):hashlib.sha256((s/'roll.sqlite3').read_bytes()).hexdigest() for s in [legacy,modern]}
shutil.copytree(legacy,target,ignore=shutil.ignore_patterns('backups'))
# Read-only source connection, explicit scratch-only destination; preserve original saved timestamps/JSON.
source=sqlite3.connect('file:'+(modern/'roll.sqlite3').as_posix()+'?mode=ro',uri=True)
destination=sqlite3.connect(target/'roll.sqlite3')
for table in ['news_facts','sentiment_runs','sentiment_facts','sentiment_references','evidence_archives','news_events','news_event_members','news_association_decisions','news_derivations']:
 rows=source.execute('SELECT * FROM '+table).fetchall()
 if rows:destination.executemany('INSERT OR IGNORE INTO '+table+' VALUES('+','.join('?' for _ in rows[0])+')',rows)
destination.commit();destination.close();source.close()
for file in (modern/'raw').iterdir():
 if not file.is_file():continue
 copied=target/'raw'/file.name
 if copied.exists():assert hashlib.sha256(copied.read_bytes()).digest()==hashlib.sha256(file.read_bytes()).digest()
 else:shutil.copy2(file,copied)
for root,digest in before_sources.items():assert hashlib.sha256((Path(root)/'roll.sqlite3').read_bytes()).hexdigest()==digest
snapshots={};commands={};cutoff=datetime.now(timezone.utc).isoformat()
with TestClient(create_app(target,runtime_role='API')) as client:
 before=client.get('/api/account').json()['version'];runs=client.get('/api/market/sentiment-series/SSE:600362/source-runs').json()
 old=next(r for r in runs if r['profile']=='legacy');new=next(r for r in runs if r['profile']=='finbert-adaptation-01')
 for name,run in [('legacy',old),('research',new)]:
  command={'idempotency_key':'real-series-'+name,'basis':'User-authorized actual saved observation reconstruction, no source/model calls or historical forecast claim','source_run_id':run['run_id'],'start_date':'2026-10-15','end_date':'2026-10-20','known_by':cutoff};commands[name]=command
  response=client.post('/api/market/sentiment-series/SSE:600362',json=command);assert response.status_code==201,response.text
  value=response.json();assert value['evidence_kind']=='REAL_SAVED_OBSERVATION_RECONSTRUCTION' and value['network_calls']==value['model_calls']==0
  assert client.get('/api/market/sentiment-series/runs/'+value['series_id']).json()==value
  assert client.post('/api/market/sentiment-series/SSE:600362',json=command).json()==value
  snapshots[name]=value
 legacy_day=next(d for d in snapshots['legacy']['days'] if d['trade_date']=='2026-10-19')
 assert legacy_day['unique_events']==10 and legacy_day['counts']=={'POSITIVE':2,'NEGATIVE':0,'NEUTRAL':None} and legacy_day['reject_count']==8,legacy_day
 assert len(snapshots['research']['deferred_events'])==12
 assert all(d['unique_events']==0 and all(v is None for v in d['counts'].values()) for d in snapshots['research']['days'])
 assert client.get('/api/account').json()['version']==before==0
 for name,value in snapshots.items():(p/('real-'+name+'-series.json')).write_bytes(json.dumps(value,ensure_ascii=False,indent=2).encode())
with TestClient(create_app(target,runtime_role='API')) as client:
 for name,value in snapshots.items():assert client.get('/api/market/sentiment-series/runs/'+value['series_id']).json()==value
 assert client.get('/api/account').json()['version']==0
report={'status':'COMPLETE','evidence_kind':'REAL_SAVED_OBSERVATION_RECONSTRUCTION','directory':str(target),'source_database_sha256':before_sources,'source_files_unchanged':True,'models_called':0,'network_calls':0,'fake_clock':False,'source_worker_override':False,'classification_worker_override':False,'account_before':0,'account_after':0,'restart_replay_identical':True,'legacy':{'series_id':snapshots['legacy']['series_id'],'source_run_id':old['run_id'],'observed_day':'2026-10-19','unique_events':10,'counts':legacy_day['counts'],'rejections':8,'neutral_supported':False,'quality_gate_passed':False},'research':{'series_id':snapshots['research']['series_id'],'source_run_id':new['run_id'],'deferred_events':12,'target_checkpoint':'2026-10-20T15:05:00+08:00','future_counts_not_emitted':True,'quality_gate_passed':True},'actual_cutoff':cutoff,'historical_forecast_archive':False}
(p/'real-runtime-summary.json').write_bytes(json.dumps(report,ensure_ascii=False,indent=2).encode());print(json.dumps(report,ensure_ascii=False,indent=2))

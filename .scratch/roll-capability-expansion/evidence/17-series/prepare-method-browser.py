"""METHOD-only browser data. Fake source clocks and inference; never real results."""
import json,sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
repo=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(repo/'backend/tests/application'))
from roll.app import create_app
from test_sentiment_series import setup,collect,classify,build,P,COPY,N
target=repo/'.scratch/r17-browser-method01'
assert not target.exists()
monkeypatch=pytest.MonkeyPatch()
with TestClient(create_app(target,runtime_role='API')) as client:
 setup(client)
 multi=('20261014123700','江西铜业涨3%，紫金矿业跌2%','江西铜业涨3%，紫金矿业跌2%。')
 collect(client,monkeypatch,[P,COPY,N,multi],'2026-10-15T14:00:00+08:00','method-browser-initial')
 first=classify(client,monkeypatch,'2026-10-15T14:01:00+08:00','method-browser-first','finbert-adaptation-01')
 assert next(row for row in first['facts'] if row['title']==multi[1])['label']=='POSITIVE'
 old,_=build(client,first,'method-browser-old')
 collect(client,monkeypatch,[('20261014123701','江西铜业涨4%','江西铜业涨4%。')],'2026-10-16T15:01:00+08:00','method-browser-late')
 second=classify(client,monkeypatch,'2026-10-16T15:02:00+08:00','method-browser-second','finbert-adaptation-01')
 value,_=build(client,second,'method-browser-new')
 day=value['days'][0]
 assert day['unique_events']==3 and day['source_fact_count']==4
 assert day['counts']=={'POSITIVE':2,'NEGATIVE':1,'NEUTRAL':0}
 assert value['evidence_kind']=='METHOD_CASE'
 assert client.get('/api/account').json()['version']==0
 (Path(__file__).resolve().parent/'method-browser-data.json').write_text(json.dumps({'evidence_kind':'METHOD_CASE','fake_clock':True,'worker_override':True,'network_calls':0,'model_calls':0,'old_series':old['series_id'],'new_series':value['series_id'],'run':second['run_id'],'first_day':day},ensure_ascii=False,indent=2),encoding='utf-8')
monkeypatch.undo()

"""Small live supplier check in a new isolated directory; never touches user accounts."""
import json
import sys
import hashlib
from pathlib import Path

from roll.accounts.ledger import Ledger
from roll.config import load_runtime_environment
from roll.market.directory import MarketDirectory, WatchCommand, IdentityCommand
from roll.market.evidence import EvidenceStore, DataRequest
from roll.market.source_policy import describe


def main():
    load_runtime_environment()
    root=Path(__file__).resolve().parents[1]/'.scratch/roll-source-routing/live-20261029'
    root.mkdir(parents=True,exist_ok=True)
    ledger=Ledger(root)
    market=MarketDirectory(ledger)
    if 'SSE:600362' not in {m['instrument'] for m in market.listing()['members']}:
        market.watch(WatchCommand(operation='ADD',instrument='SSE:600362',expected_list_version=market.listing()['version']))
        market.identify(IdentityCommand(instrument='SSE:600362',exchange='SSE',board='MAIN',instrument_type='STOCK',
            name='江西铜业',basis='Existing Roll SSE:600362 company registry; bounded supplier check only',
            effective_at='2026-10-01T00:00:00+08:00'))
    evidence=EvidenceStore(ledger,market)
    results=[]
    commands=[dict(groups=['DAILY','QUOTE'],start_date='2026-10-19',end_date='2026-10-28',
                   daily_source='AUTO',quote_source='AUTO',compare_sources=True,research_source='ORIGINAL'),
              dict(groups=['PERFORMANCE'],start_date='2025-01-01',end_date='2026-10-28',research_source='AUTO')]
    if '--market-only' in sys.argv:commands=commands[:1]
    for command in commands:
        request=evidence.request(DataRequest(instruments=['SSE:600362'],purpose='OBSERVATION',max_calls=12,
            timeout_seconds=45,max_decoded_bytes=2*1024*1024,max_total_decoded_bytes=2*1024*1024,**command))
        run=evidence.retrieve(request['request_id'],acquisition_limits={'max_response_bytes':2*1024*1024,'max_total_bytes':2*1024*1024})
        snapshot=evidence.get('market_evidence_snapshots',run['snapshot_id'])
        replay=evidence.replay(run['run_id'])
        result=dict(groups=command['groups'],run_id=run['run_id'],status=run['status'],evidence_kind=run['evidence_kind'],
            sources=sorted({f['source_id'] for f in snapshot['facts']}),facts=len(snapshot['facts']),
            latest_daily=max((f['trade_date'] for f in snapshot['facts'] if f['group']=='DAILY'),default=None),
            calls=sum(t.get('network_calls',1) for t in run['tools']),gaps=run['gaps'],
            attempts=run.get('source_attempts',[]),comparisons=run.get('source_comparisons',[]),
            references=[{k:v for k,v in item.items() if k!='content'} for item in snapshot.get('research_context',[])],
            replay_network_calls=replay['network_calls'])
        results.append(result)
        print(json.dumps(result,ensure_ascii=False),flush=True)
    receipt=dict(policy=describe(),account_version=ledger.account()['version'],results=results,
                 scope='REAL_SINGLE_STOCK_BOUNDED_CHECK; NOT_FULL_MARKET_PIT_OR_FINANCIAL_QUALIFICATION')
    files=['evidence.py','source_policy.py','research_context.py','miaoxiang.py']
    receipt['code_hashes']={name:hashlib.sha256((Path(__file__).resolve().parents[1]/'backend/src/roll/market'/name).read_bytes()).hexdigest() for name in files}
    filename='receipt-market.json' if '--market-only' in sys.argv else 'receipt.json'
    (root/filename).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    main()

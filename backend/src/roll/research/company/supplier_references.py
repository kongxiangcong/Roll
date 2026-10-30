"""Bounded supplier research material, separate from disclosed financial facts."""
import asyncio
import json
import threading
from datetime import datetime, timedelta

from roll.accounts.ledger import encode, now
from roll.market.evidence import DataRequest
from roll.market.rules import SHANGHAI
from .models import MaterialCommand


class SupplierReferences:
    run_table='supplier_reference_runs'
    def __init__(self,research):
        self.research=research
        with research.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS supplier_reference_runs(key TEXT PRIMARY KEY,instrument TEXT NOT NULL,value TEXT NOT NULL)')

    async def collect(self,instrument,command):
        cancel=threading.Event()
        try:
            return await asyncio.to_thread(self.acquire,instrument,command,cancel)
        finally:
            cancel.set()

    def acquire(self,instrument,command,cancel):
        key=instrument+':'+command.idempotency_key
        with self.research.ledger.connection() as db:
            saved=db.execute('SELECT value FROM supplier_reference_runs WHERE key=?',(key,)).fetchone()
        if saved:return json.loads(saved[0])
        identity=self.research.resolve(instrument)
        if identity['status']!='RESOLVED':raise ValueError('COMPANY_IDENTITY_REQUIRED')
        company=identity['company']
        end=datetime.now(SHANGHAI).date()
        request=self.research.evidence.request(DataRequest(instruments=[instrument],groups=['PERFORMANCE'],
            purpose='RESEARCH',start_date=end-timedelta(days=730),end_date=end,research_source='AUTO',
            max_calls=8,timeout_seconds=18,max_decoded_bytes=2*1024*1024,max_total_decoded_bytes=2*1024*1024))
        run=self.research.evidence.retrieve(request['request_id'],cancel_event=cancel,
            acquisition_limits={'max_response_bytes':2*1024*1024,'max_total_bytes':2*1024*1024})
        snapshot=self.research.evidence.get('market_evidence_snapshots',run['snapshot_id'])
        materials=[]
        for item in snapshot.get('research_context',[]):
            if item['status']!='ACQUIRED_REFERENCE' or not item['raw_hashes']:continue
            sha=item['raw_hashes'][-1]
            with self.research.ledger.connection() as db:
                archive=json.loads(db.execute('SELECT value FROM evidence_archives WHERE sha256=?',(sha,)).fetchone()[0])
            metadata=MaterialCommand(company_id=company['company_id'],subject_name=company['legal_name'],
                source_id=item['provider'].lower()+'-research',origin_root_id=item['provider']+':'+sha,
                source_url=archive['source_url'],media_type='application/octet-stream',scope='SUPPLIER_RESEARCH_REFERENCE',
                limitations=['SUPPLIER_REFERENCE_NOT_ISSUER_DISCLOSURE','NO_AUTOMATIC_FINANCIAL_FACT_ADMISSION',
                             'CURRENT_RECEIPT_NOT_HISTORICAL_PIT','PRIMARY_DOCUMENT_VERIFICATION_REQUIRED'])
            saved=self.research._material(metadata,self.research.evidence.raw(sha).read_bytes(),
                'METHOD_CASE' if run['evidence_kind'].startswith('METHOD_CASE') else 'PUBLIC_ACQUISITION',
                dict(source_type='SUPPLIER_RESEARCH_REFERENCE',record_id=run['run_id'],raw_sha256=sha,
                     original_received_at=archive['received_at'],evidence_kind=run['evidence_kind']))
            materials.append(saved['material_id'])
        result=dict(run_id=run['run_id'],snapshot_id=run['snapshot_id'],material_ids=materials,
            status='COMPLETE' if materials else 'FAILED',evidence_kind=run['evidence_kind'],
            network_calls=sum(t.get('network_calls',1) for t in run['tools']),finished_at=now())
        with self.research.ledger.connection() as db:
            db.execute('INSERT OR IGNORE INTO supplier_reference_runs VALUES(?,?,?)',(key,instrument,encode(result)))
        return result

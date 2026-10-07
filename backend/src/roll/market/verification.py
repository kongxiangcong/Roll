"""Decisive field verification; archived values never grant financial authority."""
import json
import hashlib
from decimal import Decimal, InvalidOperation
from itertools import combinations
from datetime import datetime
from pathlib import Path
import platform
import sqlite3
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from roll.market.verification_input import VerificationCommand

from roll.accounts.ledger import encode, now


FIELDS={'open','close','last','high','low','previous_close','reported_limit_up','reported_limit_down',
    'volume_shares','volume_reported','amount_yuan','trade_date','report_period','disclosure_date','record_date','ex_date',
    'dividend_yuan_per_share','total_operating_income_yuan','net_profit_yuan','eps_yuan_per_share','published_at','upstream_at'}


def verification_invalidations(db,changed_hashes,revision):
    """Called inside the existing 08 revision publication transaction."""
    records=[]
    for row in db.execute('SELECT value FROM evidence_verifications'):
        value=json.loads(row[0])
        if changed_hashes&set(value['basis_raw_hashes']):
            records.append({**revision,'invalidation_id':str(uuid4()),'target_type':'VERIFY_REVIEW_EVIDENCE',
                'target_id':value['verification_id'],'basis_raw_hashes':value['basis_raw_hashes']})
    return records


class IndependentVerifications:
    def __init__(self,evidence):
        self.evidence,self.ledger=evidence,evidence.ledger
        self.adapter_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS evidence_verifications(id TEXT PRIMARY KEY,value TEXT NOT NULL)')

    def provenance(self,fact,evidence_kind):
        unknown={'status':'INDEPENDENCE_UNPROVEN','basis_id':None,'producer':None,
            'reason':'Provider/domain/tool identity does not prove independent original production'}
        if evidence_kind.startswith('METHOD_CASE'):
            try:
                sample=json.loads(self.evidence.raw(fact['raw_hash']).read_bytes())
                proof=sample.get('_roll14_original_provenance',{})
                if proof.get('origin_kind')=='DIRECT_ORIGINAL' and all(isinstance(proof.get(k),str) and proof[k].strip()
                    for k in ['original_record','producer','generation_basis']):
                    return {'status':'METHOD_CASE_ORIGINAL_LINEAGE','basis_id':proof['original_record'],
                        'producer':proof['producer'],'generation_basis':proof['generation_basis'],
                        'reason':'Injected external fixture only; never a production independence assertion',
                        'proof_raw_hash':fact['raw_hash']}
            except (ValueError,UnicodeError):pass
        if fact.get('document_hash') and fact.get('art_code'):
            return {'status':'ISSUER_ORIGINAL_SINGLE_BASIS','basis_id':fact['instrument']+':'+fact['art_code'],
                'producer':'ISSUER:'+fact['instrument'],'proof_raw_hash':fact['document_hash'],
                'reason':'Same issuer announcement and its host/metadata representations count once; no independent production proven'}
        return unknown

    def compare(self,before,after,field):
        reasons=[]
        if before['source_errors'] or after['source_errors']:reasons.append('SOURCE_BASIC_CHECK_FAILED')
        if before['field_unit']=='UNKNOWN' or after['field_unit']=='UNKNOWN':reasons.append('UNIT_NOT_ESTABLISHED')
        elif before['field_unit']!=after['field_unit']:reasons.append('FIELD_UNIT_NOT_COMPARABLE')
        names=['instrument','group','trade_date','report_period','ex_date','upstream_at','time_precision','currency',
            'volume_unit','adjustment','adjustment_version']
        for name in names:
            if name==field or name=='volume_unit' and not field.startswith('volume'):continue
            a,b=before['context'].get(name),after['context'].get(name)
            if name=='upstream_at' and a and b:a,b=datetime.fromisoformat(a),datetime.fromisoformat(b)
            if a!=b:reasons.append(name.upper()+'_NOT_COMPARABLE')
        a,b=before['value'],after['value']
        if a is None or b is None:reasons.append('MISSING_VALUE')
        equal_kind='EQUAL_LITERAL'
        if field in {'published_at','upstream_at'} and a and b:
            equal=datetime.fromisoformat(a)==datetime.fromisoformat(b);equal_kind='EQUAL_INSTANT'
        else:
            try:
                av,bv=Decimal(str(a)),Decimal(str(b))
                if av.is_finite() and bv.is_finite():equal=av==bv;equal_kind='EQUAL_DECIMAL'
                else:equal=False;reasons.append('NONFINITE_VALUE')
            except InvalidOperation:equal=a==b
        return {'primary_reference':before['reference'],'alternate_reference':after['reference'],
            'primary_value':a,'alternate_value':b,'comparable':not reasons,'reasons':reasons,
            'values':equal_kind if equal else 'DIFFERENT'}

    def consume_review(self,request_id):
        request=self.evidence.get('review_verification_requests',request_id)
        if request['verification_id']:return self.get(request['verification_id'])
        origin={k:request[k] for k in ['request_id','task_id','snapshot_id','audit_id']}
        try:command=VerificationCommand.model_validate(request['request'])
        except ValidationError:
            raise HTTPException(409,{'code':'SAVED_VERIFICATION_INPUT_INCOMPATIBLE',
                'reason':'已保存关键复盘输入不兼容当前字段长度或类型；保留原记录，请按当前限制重新提交疑点请求'})
        return self.create(command,review_origin=origin)

    def review_request(self,request_id):
        request=self.evidence.get('review_verification_requests',request_id)
        if request['verification_id']:request['verification']=self.get(request['verification_id'])
        return request

    def create(self,command,*,review_origin=None):
        if not command.reason.strip() or len({f.fact_id for f in command.facts})!=len(command.facts):
            raise HTTPException(422,'疑点理由需非空且决定性事实键唯一')
        cutoff=command.knowledge_cutoff or datetime.fromisoformat(now())
        if cutoff.tzinfo is None or cutoff>datetime.fromisoformat(now()):
            raise HTTPException(422,'复盘知识截止须带时区且不晚于现在')
        facts=[]
        for item in command.facts:
            if item.field not in FIELDS:raise HTTPException(422,'仅核验实际市场事实字段，不核验权限或元数据')
            evidence=[]
            for reference in item.references:
                snapshot=self.evidence.get('market_evidence_snapshots',reference.snapshot_id)
                if reference.fact_index>=len(snapshot['facts']):raise HTTPException(422,'事实下标不在原快照')
                fact=snapshot['facts'][reference.fact_index]
                if item.field not in fact or isinstance(fact[item.field],(dict,list,bool)):
                    raise HTTPException(422,'仅核验已归档的具体标量事实字段')
                self.evidence.raw(fact['raw_hash'])
                if fact.get('document_hash'):self.evidence.raw(fact['document_hash'])
                run=self.evidence.get('retrieval_runs',snapshot['run_id'])
                request=self.evidence.get('data_requests',run['request_id'])
                field_unit=('SHARE' if fact.get('volume_unit')=='SHARE' else 'UNKNOWN') if item.field=='volume_shares' else (
                    fact.get('source_volume_unit',fact.get('volume_unit','UNKNOWN')) if item.field=='volume_reported' else (
                    'CNY_PER_SHARE' if item.field in {'dividend_yuan_per_share','eps_yuan_per_share'} else (
                    'CNY' if item.field in {'amount_yuan','total_operating_income_yuan','net_profit_yuan'} else (
                    'INDEX_POINT' if request['purpose']=='BACKGROUND' else 'CNY') if item.field in
                    {'open','close','last','high','low','previous_close','reported_limit_up','reported_limit_down'} else (
                    'TIMESTAMP_WITH_ZONE' if item.field in {'published_at','upstream_at'} else 'DATE'))))
                evidence.append({'reference':reference.model_dump(),'value':fact[item.field],
                    'evidence_kind':snapshot['evidence_kind'],'source_errors':fact.get('errors',[]),
                    'field_unit':field_unit,'field_definition_basis':'Registered normalized field contract; reported volume requires evidenced native unit',
                    'source_id':fact['source_id'],'source_url':fact['source_url'],'raw_hash':fact['raw_hash'],
                    'document_hash':fact.get('document_hash'),'revision_id':fact['revision_id'],
                    'available_at':fact['available_at'],'context':{name:fact.get(name) for name in
                        ['instrument','group','trade_date','report_period','ex_date','upstream_at','time_precision',
                         'currency','volume_unit','adjustment','adjustment_version']},
                    'known_at_review_cutoff':datetime.fromisoformat(fact['available_at'])<=cutoff,
                    'provenance':self.provenance(fact,snapshot['evidence_kind'])})
            proofs=[v['provenance'] for v in evidence]
            bases={p['basis_id'] for p in proofs if p['basis_id']}
            producers={p['producer'] for p in proofs if p['producer']}
            independent=min(len(bases),len(producers))
            comparisons=[self.compare(a,b,item.field) for a,b in combinations(evidence,2)]
            gaps=[]
            limitations=[]
            if any(p['basis_id'] is None for p in proofs):gaps.append('INDEPENDENCE_UNPROVEN')
            if len(bases)<len(evidence) and len(bases)>0:
                limitations.append('SAME_ORIGINAL_BASIS')
                if independent<2:gaps.append('SAME_ORIGINAL_BASIS')
            if independent<2:gaps.append('TWO_INDEPENDENT_ORIGINAL_BASES_NOT_ESTABLISHED')
            if any(v['source_errors'] for v in evidence):gaps.append('SOURCE_BASIC_CHECK_FAILED')
            if any(v['value'] is None for v in evidence):gaps.append('MISSING_VALUE')
            if any(v['field_unit']=='UNKNOWN' for v in evidence):gaps.append('UNIT_NOT_ESTABLISHED')
            if any(not v['known_at_review_cutoff'] for v in evidence):gaps.append('ACQUIRED_AFTER_REVIEW_KNOWLEDGE_CUTOFF')
            gaps.extend(sorted({r for c in comparisons for r in c['reasons']}))
            conflict=any(c['comparable'] and c['values']=='DIFFERENT' for c in comparisons)
            result='CONFLICT' if conflict else 'INSUFFICIENT' if gaps else 'VERIFIED'
            facts.append({'fact_id':item.fact_id,'field':item.field,'evidence':evidence,'result':result,
                'independent_basis_count':independent,'gaps':gaps,'comparisons':comparisons,
                'limitations':limitations,
                'attribution_status':'READY' if result=='VERIFIED' else 'DEFERRED'})
        outcome='CONFLICT' if any(f['result']=='CONFLICT' for f in facts) else 'INSUFFICIENT' if any(f['result']=='INSUFFICIENT' for f in facts) else 'VERIFIED'
        frozen=[{'fact_id':f['fact_id'],'field':f['field'],'versions':sorted([
            {k:v for k,v in entry.items() if k not in {'reference','available_at'}} for entry in f['evidence']],key=encode)} for f in facts]
        fingerprint=hashlib.sha256(encode({'adapter_hash':self.adapter_hash,'facts':frozen,'knowledge_constraint':
            command.knowledge_cutoff.isoformat() if command.knowledge_cutoff else 'CURRENT_ACQUIRED_INPUTS'}).encode()).hexdigest()
        reused=next((v for v in self.history() if v['input_fingerprint']==fingerprint and v['dependency_status']=='CURRENT'),None)
        if reused:facts=reused['facts'];outcome=reused['result']
        value={'verification_id':str(uuid4()),'command':command.model_dump(mode='json'),'created_at':now(),
            'status':'COMPLETED','result':outcome,'facts':facts,'dependency_status':'CURRENT',
            'current_result':outcome,'invalidations':[],'input_fingerprint':fingerprint,
            'knowledge_cutoff':cutoff.isoformat(),'knowledge_basis':'ACTUAL_CONSUMER_BOUND; NO_RETROACTIVE_SOURCE_KNOWLEDGE',
            'reuse_of':reused['verification_id'] if reused else None,'review_origin':review_origin,
            'basis_raw_hashes':sorted({v[k] for f in facts for v in f['evidence'] for k in ['raw_hash','document_hash'] if v.get(k)}),
            'formal_judgment':'DISABLED','account_confirmation':'NOT_GRANTED','network_calls':0,
            'adapter_version':'14-verify-v1','adapter_hash':self.adapter_hash,
            'runtime_versions':{'python':platform.python_version(),'sqlite':sqlite3.sqlite_version},
            'source_evidence_kinds':sorted({e['evidence_kind'] for f in facts for e in f['evidence']}),
            'evidence_kind':'METHOD_CASE' if any(e['evidence_kind'].startswith('METHOD_CASE') for f in facts for e in f['evidence']) else 'REAL_ARCHIVED_EVIDENCE'}
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                if review_origin:
                    request=json.loads(db.execute('SELECT value FROM review_verification_requests WHERE id=?',
                        (review_origin['request_id'],)).fetchone()[0])
                    if request['verification_id']:
                        db.rollback()
                        return self.get(request['verification_id'])
                db.execute('INSERT INTO evidence_verifications VALUES(?,?)',(value['verification_id'],encode(value)))
                if review_origin:
                    request.update(status='CONSUMED',verification_id=value['verification_id'],consumed_at=now())
                    db.execute('UPDATE review_verification_requests SET value=? WHERE id=?',
                        (encode(request),review_origin['request_id']))
                    audit=json.loads(db.execute('SELECT value FROM review_audits WHERE id=?',(review_origin['audit_id'],)).fetchone()[0])
                    audit.setdefault('verification_links',[]).append({'request_id':review_origin['request_id'],
                        'verification_id':value['verification_id'],'linked_at':request['consumed_at']})
                    if audit['critical_review'].get('request_id')==review_origin['request_id']:
                        audit['critical_review'].update(status='CONSUMED',verification_id=value['verification_id'])
                    db.execute('UPDATE review_audits SET value=? WHERE id=?',(encode(audit),review_origin['audit_id']))
                self.ledger.crash_point('verification_before_commit')
                db.commit()
                self.ledger.crash_point('verification_after_commit')
            except BaseException:db.rollback();raise
        return self.get(value['verification_id'])

    def get(self,verification_id):
        value=self.evidence.get('evidence_verifications',verification_id)
        for sha in value['basis_raw_hashes']:self.evidence.raw(sha)
        with self.ledger.connection() as db:
            invalidations=[json.loads(row[0]) for row in db.execute(
                'SELECT value FROM evidence_dependency_invalidations WHERE target_id=?',(verification_id,))]
            revisions=[json.loads(row[0]) for row in db.execute('SELECT value FROM source_revisions')]
        # A fresh verification UUID must not make a known superseded source current.
        for revision in revisions:
            hashes=revision.get('verification_changed_raw_hashes')
            if hashes is None:
                from roll.market.resolution import key
                prior=self.evidence.get('source_resolutions',revision['prior_resolution_id'])
                current=self.evidence.get('source_resolutions',revision['new_resolution_id'])
                after={key(f):f for f in current.get('acquired_facts',current['facts'])}
                hashes=[f['raw_hash'] for f in prior.get('acquired_facts',prior['facts'])
                    if list(key(f)) in revision['changed_fact_keys'] or key(f) in after and f['raw_hash']!=after[key(f)]['raw_hash']]
            if set(hashes)&set(value['basis_raw_hashes']) and not any(i['revision_id']==revision['revision_id'] for i in invalidations):
                invalidations.append({**revision,'target_type':'VERIFY_REVIEW_EVIDENCE','target_id':verification_id,
                    'basis_raw_hashes':value['basis_raw_hashes'],'reason':'SOURCE_VERSION_SUPERSEDED'})
        return {**value,'dependency_status':'INVALIDATED' if invalidations else 'CURRENT',
            'current_result':'INSUFFICIENT' if invalidations else value['result'],'invalidations':invalidations}

    def history(self):
        with self.ledger.connection() as db:
            ids=[row[0] for row in db.execute('SELECT id FROM evidence_verifications ORDER BY rowid DESC LIMIT 100')]
        values=[]
        for key in ids:
            try:values.append(self.get(key))
            except HTTPException as error:
                if error.status_code!=409:raise
                original=self.evidence.get('evidence_verifications',key)
                values.append({**original,'dependency_status':'UNREADABLE','current_result':'INSUFFICIENT',
                    'integrity_error':error.detail})
        return values

    def replay(self,verification_id):
        value=self.get(verification_id)
        for item in value['command']['facts']:
            for ref in item['references']:
                snapshot=self.evidence.get('market_evidence_snapshots',ref['snapshot_id'])
                self.evidence.replay(snapshot['run_id'])
        return {'verification_id':verification_id,'recorded_at':now(),'original_result':value['result'],
            'facts':value['facts'],'network_calls':0,'current_dependency_status':value['dependency_status'],
            'formal_judgment':'DISABLED'}

"""Finite host GETs of explicitly bound primary documents, never model URLs."""
import hashlib
import ipaddress
import socket
import time
from uuid import uuid4
from urllib.parse import urlsplit
from datetime import datetime
from roll.market.rules import SHANGHAI
import httpx
from fastapi import HTTPException
from pydantic import Field
from typing import Literal
from roll.accounts.ledger import encode, now
from .models import Command, MaterialCommand
from .service import fail, record, fingerprint
from .report_archive import archive

HOSTS={'static.cninfo.com.cn','epaper.cs.com.cn','yield.chinabond.com.cn','pages.stern.nyu.edu','pdf.dfcfw.com',
       'www.sse.com.cn','www.hkexnews.hk','www.sec.gov','www.stats.gov.cn','data.stats.gov.cn'}


class ReportSource(Command):
    material: MaterialCommand
    category: Literal['本体披露','行业时序','产业链','同业对照','估值序列','研报','官方监管']
    identity_basis: str = Field(min_length=10,max_length=2000)
    expected_sha256: str | None = Field(default=None,pattern='^[a-f0-9]{64}$')
    source_subject: str = Field(default='ISSUER_DOCUMENT',min_length=1,max_length=300)
    source_role: Literal['ISSUER_DISCLOSURE','ISSUER_INDUSTRY_DISCUSSION','EXTERNAL_CONTEXT'] = 'ISSUER_DISCLOSURE'


def validate_source(source,company_id,cutoff):
    parsed=urlsplit(source.material.source_url)
    if parsed.scheme!='https' or parsed.hostname not in HOSTS or parsed.username or parsed.password or parsed.port not in (None,443):
        fail('SOURCE_SCOPE_UNSUPPORTED','Only explicitly bound HTTPS public disclosure/statistical hosts are supported')
    if source.material.company_id!=company_id:
        fail('CROSS_COMPANY_REFERENCE','Source plan must belong to the requested company')
    cutoff_day=datetime.fromisoformat(cutoff).astimezone(SHANGHAI).date().isoformat()
    if source.material.period_end and source.material.period_end>cutoff_day:
        fail('SOURCE_AFTER_REPORT_CUTOFF','Source report period exceeds requested report cutoff')


def validate_periods(facts,materials,cutoff):
    stamp=datetime.fromisoformat(cutoff)
    day=stamp.astimezone(SHANGHAI).date().isoformat()
    later=[i.get('version_id',i.get('material_id')) for i in [*facts,*materials] if i.get('period_end') and i['period_end']>day]
    disclosed=[m['material_id'] for m in materials if m.get('disclosed_at') and datetime.fromisoformat(m['disclosed_at'])>stamp]
    if later or disclosed:
        fail('REPORT_PERIOD_AFTER_CUTOFF','Pinned material/fact reporting period or known disclosure exceeds the requested report cutoff; choose an aligned snapshot without changing the old core',409,
             later_period_ids=later,later_disclosure_ids=disclosed,report_cutoff_day=day)


def acquire(research,job,source,index):
    """One GET, eight seconds/8 MiB; receipt survives all failures."""
    validate_source(source,job['company_id'],job['request_cutoff'])
    key='report:'+job['job_id']+':'+str(index)
    source_id='report-primary:'+fingerprint(source.material.source_url)[:24]
    with research.ledger.connection() as db:
        prior=db.execute('SELECT value FROM company_research_checks WHERE company_id=? AND source_id=? AND key=?',(job['company_id'],source_id,key)).fetchone()
    if prior:
        from .service import verified
        check=verified(__import__('json').loads(prior[0]))
        return dict(**check['source_receipts'][0],check_id=check['check_id'])
    material=source.material
    with research.ledger.connection() as db:
        before={r[0] for r in db.execute('SELECT material_id FROM company_research_materials WHERE company_id=?',(job['company_id'],))}
    started=now(); deadline=time.monotonic()+8
    receipt=dict(index=index,source_url=material.source_url,category=source.category,identity_basis=source.identity_basis,
        started_at=started,network_check_performed=False,actual_obtained_at=None,material_id=None,status='FAILED',
        historical_pit_eligible=False,evidence_kind='METHOD_CASE' if research.evidence.transport else 'REAL_PUBLIC_ACQUISITION')
    try:
        if research.evidence.transport is None:
            hostname=urlsplit(material.source_url).hostname
            if any(not ipaddress.ip_address(ip[4][0]).is_global for ip in socket.getaddrinfo(hostname,443)):
                raise ValueError('PUBLIC_ADDRESS_REQUIRED')
        chunks=[]; size=0
        with httpx.Client(transport=research.evidence.transport,follow_redirects=False,timeout=8) as client:
            receipt['network_check_performed']=True
            with client.stream('GET',material.source_url) as response:
                receipt['http_status']=response.status_code
                response.raise_for_status()
                for chunk in response.iter_bytes():
                    size+=len(chunk)
                    if size>8*1024*1024 or time.monotonic()>deadline:
                        raise TimeoutError('ACQUISITION_BOUND_EXCEEDED')
                    chunks.append(chunk)
        raw=b''.join(chunks)
        digest=hashlib.sha256(raw).hexdigest()
        raw_archive=archive(research.evidence,raw,'REPORT_SOURCE_RESPONSE_BYTES')
        receipt.update(actual_obtained_at=now(),bytes=len(raw),raw_sha256=digest,raw_archive=raw_archive)
        if source.expected_sha256 and digest!=source.expected_sha256:
            raise ValueError('SOURCE_BYTES_CHANGED')
        saved=research._material(material,raw,'METHOD_CASE' if research.evidence.transport else 'PUBLIC_ACQUISITION',
            dict(report_job_id=job['job_id'],category=source.category,identity_basis=source.identity_basis,
                source_subject=source.source_subject,source_role=source.source_role,
                source_limit='材料关联主研究公司，不把外部行业/同业论述转换成主公司披露事实；事实入口仍执行02主体隔离',acquisition=receipt))
        receipt.update(material_id=saved['material_id'],status='SUCCESS',meaning='原件已存共享材料；未凭PDF猜测财务事实，待有据字段/经营分析')
        receipt['new_material_count']=int(saved['material_id'] not in before)
        if not receipt['new_material_count']:
            receipt['meaning']='本次实际复取所列原件，未新增共享材料；不代表经营未变或原文已独立审计'
    except Exception as error:
        code=error.detail.get('code') if isinstance(error,HTTPException) and isinstance(error.detail,dict) else 'ACQUISITION_TIMEOUT' if isinstance(error,(TimeoutError,httpx.TimeoutException)) else str(error) if isinstance(error,ValueError) and str(error) in {'SOURCE_BYTES_CHANGED','PUBLIC_ADDRESS_REQUIRED'} else 'SOURCE_UNAVAILABLE'
        receipt['error']=dict(code=code,type=type(error).__name__)
    receipt['finished_at']=now()
    scope=source.category
    with research.ledger.connection() as db:
        previous=db.execute("SELECT value FROM company_research_checks WHERE company_id=? AND source_id=? AND json_extract(value,'$.requested_scopes[0]')=? AND json_extract(value,'$.status')='SUCCESS' ORDER BY rowid DESC LIMIT 1",(job['company_id'],source_id,scope)).fetchone()
    from .service import verified
    prior_success=verified(__import__('json').loads(previous[0])) if previous else None
    check_identifier=str(uuid4())
    check=record(dict(company_id=job['company_id'],source_id=source_id,requested_scopes=[scope],idempotency_key=key,
        check_id=check_identifier,attempt_id=str(uuid4()),status=receipt['status'],started_at=started,finished_at=receipt['finished_at'],
        completed_scopes=[scope] if receipt['status']=='SUCCESS' else [],failed_scopes=[] if receipt['status']=='SUCCESS' else [scope],
        material_ids=[receipt['material_id']] if receipt['material_id'] else [],new_material_count=int(bool(receipt['material_id'] and receipt['material_id'] not in before)),
        source_receipts=[receipt],errors=[] if receipt['status']=='SUCCESS' else [dict(scope=scope,**receipt['error'])],
        last_success_check_id=check_identifier if receipt['status']=='SUCCESS' else prior_success['check_id'] if prior_success else None,last_success_at=receipt['finished_at'] if receipt['status']=='SUCCESS' else prior_success['finished_at'] if prior_success else None,
        meaning=receipt.get('meaning','本次来源核查未完成，旧资料/缺口保留'),retry_state='EXPLICIT_NEW_ATTEMPT_REQUIRED'))
    with research.transaction() as db:
        db.execute('INSERT INTO company_research_checks VALUES(?,?,?,?,?,?)',(check['check_id'],job['company_id'],check['source_id'],key,fingerprint(source.model_dump()),encode(check)))
    return dict(**receipt,check_id=check['check_id'])

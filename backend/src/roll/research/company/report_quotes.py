"""Literal operating quotations with physical PDF pages, never inferred numbers."""
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Literal
from pydantic import Field,model_validator
from roll.accounts.ledger import encode,now
from .models import Command,FactCommand
from .service import fail,record
from .report_archive import archive


class ReportQuote(Command):
    source_index: int | None = Field(default=None,ge=0,le=3)
    material_id: str | None = None
    page: int = Field(ge=1,le=2000)
    quote: str = Field(min_length=20,max_length=2000)
    business: str = Field(min_length=1,max_length=160)
    metric: Literal['business_structure','product_structure','operating_scope','operating_counterevidence'] = 'business_structure'

    @model_validator(mode='after')
    def one_source(self):
        if (self.source_index is None)==(self.material_id is None):
            raise ValueError('Specify one source index or registered material ID')
        return self


def read_pdf_page(research,material,page):
    key=(material['raw_sha256'],page)
    cache=getattr(research,'report_page_cache',{})
    if key in cache:return cache[key]
    environment={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','TEMP','TMP'}}
    result=subprocess.run([sys.executable,'-u',str(Path(__file__).with_name('report_quote_worker.py'))],
        input=encode(dict(path=str(research.evidence.raw(material['raw_sha256'])),page=page)),
        capture_output=True,text=True,encoding='utf-8',timeout=8,env=environment,
        cwd=research.evidence.directory,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode or len(result.stdout.encode())>131072:
        fail('SOURCE_QUOTE_EXTRACTION_FAILED','Fixed PDF text reader failed; source retained without a fabricated fact')
    text=json.loads(result.stdout)['text']
    cache[key]=text;research.report_page_cache=cache
    return text


def verify_quote(research,job,quote,index):
    material_id=quote.material_id
    if material_id is None:
        receipts=job.get('acquisition',{}).get('receipts',[])
        if quote.source_index>=len(receipts) or not receipts[quote.source_index].get('material_id'):
            fail('SOURCE_QUOTE_ORIGINAL_MISSING','Quote source was not acquired; original failure remains explicit')
        material_id=receipts[quote.source_index]['material_id']
    material=research.material(material_id,job['company_id'])
    if not material['period_start'] or not material['period_end']:
        fail('SOURCE_QUOTE_PERIOD_REQUIRED','Declare the document reporting period; retrieval day cannot fill it')
    original=research.material_bytes(material_id)
    if len(original)>8*1024*1024:
        fail('SOURCE_QUOTE_SIZE_BOUND','Selected original exceeds the bounded text reader limit')
    page,table=None,'RAW_TEXT_EXACT_QUOTE'
    if material['media_type']=='application/pdf':
        text=read_pdf_page(research,material,quote.page);page=str(quote.page);table='PDF_EXACT_PAGE_QUOTE'
    elif material['media_type']=='text/plain' and quote.page==1:
        text=original.decode('utf-8-sig')
    else:
        fail('SOURCE_QUOTE_TYPE_UNSUPPORTED','Only a physical PDF page or exact raw text is supported')
    if quote.quote not in text:
        fail('SOURCE_QUOTE_NOT_IN_ORIGINAL','The literal quotation does not occur on the declared original page')
    extraction=archive(research.evidence,text.encode(),'REPORT_QUOTE_DERIVED_PAGE_TEXT')
    fact=research.add_fact(FactCommand(company_id=job['company_id'],material_id=material_id,metric=quote.metric,
        business=quote.business,value=quote.quote,value_type='TEXT',unit=material['unit'],currency=material['currency'],scope=material['scope'],
        period_start=material['period_start'],period_end=material['period_end'],page=page,table=table,kind='DISCLOSED',
        change_reason='Host verified a literal operating quotation against the original physical page; no numeric inference or independent endorsement',
        idempotency_key='report-quote:'+job['job_id']+':'+str(index)))
    return record(dict(index=index,status='SUCCESS',fact_version_id=fact['version_id'],material_id=material_id,
        original_sha256=material['raw_sha256'],page=page,table=table,derived_text_archive=extraction,
        quote=quote.quote,verified_at=now(),meaning='逐字引文核对；经营含义仍由共同分析处理，未知数值口径保持未知'))

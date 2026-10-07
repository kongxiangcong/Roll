"""Host-owned bounded acquisition; raw authority precedes normalized SQLite facts."""
import hashlib
import json
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from importlib.metadata import version
from pathlib import Path
from typing import Literal
from uuid import uuid4

import httpx
import pyarrow as pa
import pyarrow.parquet as pq
from pypdf.errors import PyPdfError
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from roll.accounts.ledger import encode, now
from roll.market.directory import ScopeCommand
from roll.market.rules import SHANGHAI
from roll.market import source_facts

ADAPTER_VERSION='08-market-v1'
GROUPS=['DAILY','QUOTE','ADJUSTMENTS','ANNOUNCEMENTS','PERFORMANCE','MAJOR_EVENTS','STATUS']


class DataRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    instruments:list[str]=Field(min_length=1)
    groups:list[Literal['DAILY','QUOTE','ADJUSTMENTS','ANNOUNCEMENTS','PERFORMANCE','MAJOR_EVENTS','STATUS']]=Field(min_length=1)
    purpose:Literal['OBSERVATION','RESEARCH','BACKGROUND']
    start_date:date
    end_date:date
    cutoff:datetime|None=None
    required_fields:list[str]=Field(default_factory=list,max_length=30)
    timeout_seconds:int=Field(default=40,ge=1,le=60)
    max_calls:int=Field(default=20,ge=1,le=30)
    daily_source:Literal['EASTMONEY','TENCENT']|None=None
    quote_source:Literal['TENCENT','SINA']='TENCENT'


def decimal_value(value,price=False):
    if value in {None,'','-','--','null'}:
        return None
    try:
        number=Decimal(str(value))
        if not number.is_finite() or number<0 or (price and number==0):
            return None
        return format(number,'f')
    except InvalidOperation:
        return None


class EvidenceStore:
    def __init__(self,ledger,market,transport=None):
        self.ledger,self.market=ledger,market
        self.directory=ledger.path.parent
        self.transport=transport
        self.evidence_kind='METHOD_CASE' if transport is not None else 'REAL_ACQUISITION'
        self.runtime_versions={name:version(name) for name in ['httpx','pyarrow','pypdf']}
        with ledger.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS data_requests(id TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS retrieval_runs(id TEXT PRIMARY KEY, request_id TEXT NOT NULL, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS market_evidence_snapshots(id TEXT PRIMARY KEY, run_id TEXT NOT NULL, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS evidence_archives(sha256 TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')
            # A process that died before snapshot commit cannot remain apparently running.
            for row in db.execute('SELECT id,value FROM retrieval_runs'):
                run=json.loads(row['value'])
                if run['status']=='RUNNING':
                    run.update(status='INTERRUPTED',finished_at=now(),recovery_reason='PROCESS_RESTART_BEFORE_SNAPSHOT_COMMIT')
                    db.execute('UPDATE retrieval_runs SET value=? WHERE id=?',(encode(run),row['id']))

    def archive(self,content,kind,extension='raw',**metadata):
        sha=hashlib.sha256(content).hexdigest()
        relative=Path('parquet' if extension=='parquet' else 'raw')/(sha+'.'+extension)
        target=self.directory/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            temporary=target.with_name(target.name+'.'+str(uuid4())+'.tmp')
            with temporary.open('xb') as stream:
                stream.write(content);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,target)
        if hashlib.sha256(target.read_bytes()).hexdigest()!=sha:
            raise RuntimeError('市场证据归档指纹损坏')
        result={'sha256':sha,'path':relative.as_posix(),'bytes':len(content),'kind':kind,**metadata}
        with self.ledger.connection() as db:
            db.execute('INSERT OR IGNORE INTO evidence_archives VALUES(?,?)',(sha,encode(result)))
        return result

    def raw(self,sha):
        with self.ledger.connection() as db:
            row=db.execute('SELECT value FROM evidence_archives WHERE sha256=?',(sha,)).fetchone()
        if row is None:
            raise HTTPException(404,'归档不存在')
        metadata=json.loads(row[0]); path=self.directory/metadata['path']
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
            raise HTTPException(409,{'code':'ARCHIVE_MISSING_OR_CORRUPT'})
        return path

    def get(self,table,key):
        with self.ledger.connection() as db:
            row=db.execute(f'SELECT value FROM {table} WHERE id=?',(key,)).fetchone()
        if row is None:
            raise HTTPException(404,'事实请求/运行/快照不存在')
        return json.loads(row[0])

    def request(self,command:DataRequest):
        if command.start_date>command.end_date:
            raise HTTPException(422,'开始日期不得晚于结束日期')
        cutoff=command.cutoff or datetime.fromisoformat(now())
        if cutoff.tzinfo is None or cutoff>datetime.fromisoformat(now()):
            raise HTTPException(422,'cutoff需要带时区且不是未来时点')
        if command.end_date>cutoff.astimezone(SHANGHAI).date():
            raise HTTPException(422,'请求数据日期不能晚于事件截止')
        if command.purpose=='BACKGROUND' and set(command.groups)-{'DAILY','QUOTE'}:
            raise HTTPException(422,'背景指数只请求量价与报价，不作公司事项/个股研究')
        if command.purpose=='BACKGROUND' and command.daily_source=='EASTMONEY':
            raise HTTPException(422,'本票背景日线仅预先适配腾讯；不能将明确选择的来源静默换源')
        source=command.daily_source or ('TENCENT' if command.purpose=='BACKGROUND' else 'EASTMONEY')
        for field in command.required_fields:
            parts=field.split('.',1)
            if not field or len(field)>80 or (len(parts)==2 and parts[0] not in command.groups):
                raise HTTPException(422,'必需字段需明确对应本次请求事实组或公共字段')
        scope=self.market.check_scope(ScopeCommand(instruments=command.instruments,purpose=command.purpose))
        listing=self.market.listing(scope['list_version'])
        identities={m['instrument']:{k:v for k,v in m['identity'].items() if k in
            {'exchange','code','board','instrument_type','name','revision','effective_at','confirmed_at'}}
            for m in listing['members'] if m['instrument'] in command.instruments}
        result={**command.model_dump(mode='json'),'daily_source':source,'request_id':str(uuid4()),'cutoff':cutoff.isoformat(),
            'cutoff_basis':'EVENT_OR_SOURCE_DISCLOSURE_BOUND_NOT_PAST_KNOWLEDGE_PROOF',
            'scope':scope,'identity_context':identities,'created_at':now(),'technical_limits':{'max_calls':command.max_calls,
                'timeout_seconds':command.timeout_seconds,'max_response_bytes':16*1024*1024,'retries':0}}
        with self.ledger.connection() as db:
            db.execute('INSERT INTO data_requests VALUES(?,?)',(result['request_id'],encode(result)))
        return result

    def daily(self,archive,request,instrument,adjustment):
        raw=source_facts.source_json(self.raw(archive['sha256']).read_bytes())
        if raw.get('rc')!=0 or not raw.get('data'):
            raise ValueError('PROVIDER_BUSINESS_ERROR_OR_EMPTY')
        data=raw['data']
        if data.get('code')!=instrument.split(':')[1]:
            raise ValueError('SOURCE_OBJECT_MISMATCH')
        if 'market' in data and data['market']!=(1 if instrument.split(':')[0]=='SSE' else 0):
            raise ValueError('SOURCE_EXCHANGE_MISMATCH')
        facts=[]
        for row in data.get('klines',[]):
            fields=row.split(',')
            if len(fields)<7:
                raise ValueError('MISSING_DAILY_FIELDS')
            day=date.fromisoformat(fields[0])
            if not request['start_date']<=day.isoformat()<=request['end_date']:
                continue
            values={name:decimal_value(value,price=name in {'open','close','high','low'})
                    for name,value in zip(['open','close','high','low','volume_hands','amount_yuan'],fields[1:7])}
            errors=['MISSING_OR_PLACEHOLDER_'+name.upper() for name,value in values.items() if value is None]
            identity=request.get('identity_context',{}).get(instrument,{})
            unit_verified=identity.get('exchange')=='SSE' and identity.get('board')=='MAIN' and identity.get('instrument_type')=='STOCK'
            shares=format(Decimal(values['volume_hands'])*100,'f') if unit_verified and values['volume_hands'] is not None else None
            limitations=[] if unit_verified else ['VOLUME_UNIT_UNVERIFIED_FOR_THIS_SCOPE']
            if not errors:
                o,c,h,l=(Decimal(values[name]) for name in ['open','close','high','low'])
                if not l<=min(o,c)<=max(o,c)<=h:
                    errors.append('INVALID_OHLC_RANGE')
                if Decimal(values['volume_hands'])>0 and Decimal(values['amount_yuan'])==0:
                    errors.append('AMOUNT_PLACEHOLDER_OR_INCONSISTENT')
                if adjustment=='RAW' and shares is not None and Decimal(shares)>0 and Decimal(values['amount_yuan'])>0:
                    vwap=Decimal(values['amount_yuan'])/Decimal(shares)
                    if not l-Decimal('.01')<=vwap<=h+Decimal('.01'):
                        errors.append('UNIT_AMOUNT_OHLC_MISMATCH')
            received=datetime.fromisoformat(archive['received_at'])
            completion='COMPLETE_REPORTED_HISTORICAL' if day<received.astimezone(SHANGHAI).date() else 'UNCONFIRMED_CURRENT_DAY'
            index=request['purpose']=='BACKGROUND'
            facts.append({'instrument':instrument,'group':'DAILY','trade_date':day.isoformat(),'time_precision':'DATE',
                **values,'volume_reported':values['volume_hands'],'source_volume_unit':'HAND' if unit_verified else 'UNKNOWN',
                'volume_shares':shares,'volume_unit':'SHARE' if unit_verified else 'UNKNOWN',
                'conversion_basis':'已确认SSE主板普通股票；成交量手数与成交额/OHLC核对；1手100股' if unit_verified else None,
                'adjustment':adjustment,'adjustment_version':archive['sha256'] if adjustment!='RAW' else None,
                'completion_state':completion,'quality':'INVALID' if errors else 'BASIC_CHECKED_SINGLE_SOURCE',
                'errors':errors,'limitations':limitations,'model_daily_input_allowed':not errors and not limitations and completion.startswith('COMPLETE'),
                'volume_state':'MISSING' if values['volume_hands'] is None else 'ZERO_REPORTED' if Decimal(values['volume_hands'])==0 else 'REPORTED',
                'source_id':'eastmoney-daily','source_url':archive['source_url'],'raw_hash':archive['sha256'],
                'revision_id':archive['sha256'],'received_at':archive['received_at'],'available_at':archive['received_at'],
                'available_basis':'FIRST_ACTUAL_RECEIPT_IN_THIS_RUNTIME','published_at':None,
                'historical_limitations':['PROVIDER_CURRENT_REVISION_NOT_PROVEN_POINT_IN_TIME',
                    'ADJUSTED_SERIES_CURRENT_PROVIDER_VERSION' if adjustment!='RAW' else 'SOURCE_REPORTED_SESSION_DATES']})
        return facts,{'instrument':instrument,'group':'DAILY','source_total_rows':data.get('dktotal'),
            'returned_rows':len(facts),'first_date':facts[0]['trade_date'] if facts else None,
            'last_date':facts[-1]['trade_date'] if facts else None,'request_start':request['start_date'],
            'request_end':request['end_date'],'status':'ACQUIRED' if facts else 'NO_ROWS_RETURNED',
            'full_history_verified':False,'truncation':'REQUEST_BOUNDED; SOURCE_TOTAL_IS_NOT_RETURNED_COVERAGE',
            'adjustment':adjustment,'raw_hash':archive['sha256']}

    def retrieve(self,request_id):
        import time
        request=self.get('data_requests',request_id)
        # Recheck current membership, so a stale request cannot acquire a removed stock.
        self.market.check_scope(ScopeCommand(instruments=request['instruments'],purpose=request['purpose']))
        run={'run_id':str(uuid4()),'request_id':request_id,'backend':'DIRECT_HTTP','model':None,
            'sdk_runtime_version':'httpx-'+self.runtime_versions['httpx']+'/'+ADAPTER_VERSION,'runtime_versions':self.runtime_versions,
            'config_fingerprint':hashlib.sha256(encode({'limits':request['technical_limits'],'daily_source':request.get('daily_source','EASTMONEY'),
                'quote_source':request.get('quote_source','TENCENT'),
                'adapter_version':ADAPTER_VERSION,'runtime_versions':self.runtime_versions,
                'adapter_code_hashes':[hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in [__file__,source_facts.__file__]]}).encode()).hexdigest(),
            'evidence_kind':self.evidence_kind,'started_at':now(),'status':'RUNNING','tools':[],'gaps':[]}
        with self.ledger.connection() as db:
            db.execute('INSERT INTO retrieval_runs VALUES(?,?,?)',(run['run_id'],request_id,encode(run)))
        started=time.monotonic();facts=[];archives=[];coverage=[];observations=[]
        with httpx.Client(transport=self.transport,follow_redirects=False) as client:
            def fetch(source_id,instrument,group,url,params=None,headers=None,**context):
                if len(run['tools'])>=request['max_calls'] or time.monotonic()-started>=request['timeout_seconds']:
                    run['gaps'].append({'instrument':instrument,'group':group,'code':'TECHNICAL_LIMIT',**context});return None
                tool={'source_id':source_id,'instrument':instrument,'group':group,'started_at':now(),
                    'method':'GET','source_url':str(httpx.Request('GET',url,params=params).url),**context}
                run['tools'].append(tool)
                try:
                    with client.stream('GET',url,params=params,headers=headers,timeout=min(10,max(.1,request['timeout_seconds']-(time.monotonic()-started)))) as response:
                        content=bytearray()
                        for chunk in response.iter_bytes():
                            if len(content)+len(chunk)>16*1024*1024 or time.monotonic()-started>request['timeout_seconds']:
                                raise ValueError('RESPONSE_SIZE_OR_TIME_LIMIT')
                            content.extend(chunk)
                        archive=self.archive(bytes(content),'RAW_RESPONSE',source_id=source_id,source_url=str(response.url),
                            received_at=now(),http_status=response.status_code,evidence_kind=self.evidence_kind)
                    archives.append(archive);tool.update(raw_hash=archive['sha256'],http_status=response.status_code)
                    response.raise_for_status();tool.update(status='ARCHIVED',finished_at=now(),received_bytes=len(content))
                    return archive,bytes(content)
                except (httpx.HTTPError,ValueError,KeyError,TypeError) as error:
                    tool.update(status='FAILED',finished_at=now());run['gaps'].append({'instrument':instrument,'group':group,'code':type(error).__name__,
                        'reason':str(error)[:300],**context});return None

            def parsed(group,instrument,callback):
                try:return callback()
                except (ValueError,KeyError,TypeError,IndexError,PyPdfError) as error:
                    run['gaps'].append({'instrument':instrument,'group':group,'code':'NORMALIZATION_ERROR','reason':str(error)[:300]});return None

            for instrument in request['instruments']:
                if instrument.split(':')[0]=='BSE':
                    run['gaps'].extend({'instrument':instrument,'group':group,'code':'SOURCE_SCOPE_NOT_ADAPTED_BSE'} for group in request['groups']);continue
                if (request['purpose']=='BACKGROUND' or request.get('daily_source')=='TENCENT') and 'DAILY' in request['groups']:
                    symbol=('sh' if instrument.split(':')[0]=='SSE' else 'sz')+instrument.split(':')[1]
                    for adjustment,mode in [('RAW','')] if request['purpose']=='BACKGROUND' else [('RAW',''),('FORWARD_CURRENT_VERSION','qfq')]:
                        response=fetch('tencent-index-daily' if request['purpose']=='BACKGROUND' else 'tencent-daily',instrument,'DAILY',
                            'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get',
                            {'param':','.join([symbol,'day',request['start_date'],request['end_date'],'800',mode])},adjustment=adjustment)
                        if response:
                            result=parsed('DAILY',instrument,lambda:source_facts.index_daily(response[1],response[0],instrument,request,symbol,decimal_value,adjustment))
                            if result:
                                rows,cov=result;facts.extend(rows);coverage.append(cov)
                for adjustment,fqt in [('RAW',0),('FORWARD_CURRENT_VERSION',1)] if 'DAILY' in request['groups'] and request['purpose']!='BACKGROUND' and request.get('daily_source','EASTMONEY')=='EASTMONEY' else []:
                    params={'secid':('1' if instrument.startswith('SSE:') else '0')+'.'+instrument.split(':')[1],
                        'klt':101,'fqt':fqt,'beg':request['start_date'].replace('-',''),'end':request['end_date'].replace('-',''),
                        'fields1':'f1,f2,f3,f4,f5,f6','fields2':'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61'}
                    url='https://push2his.eastmoney.com/api/qt/stock/kline/get'
                    response=fetch('eastmoney-daily',instrument,'DAILY',url,params,adjustment=adjustment)
                    if response:
                        result=parsed('DAILY',instrument,lambda:self.daily(response[0],request,instrument,adjustment))
                        if result:
                            rows,cov=result;facts.extend(rows);coverage.append(cov)
                if {'QUOTE','STATUS'}&set(request['groups']):
                    symbol=('sh' if instrument.split(':')[0]=='SSE' else 'sz' if instrument.split(':')[0]=='SZSE' else 'bj')+instrument.split(':')[1]
                    sina=request.get('quote_source')=='SINA'
                    response=fetch('sina-quote' if sina else 'tencent-quote',instrument,'QUOTE',
                        'https://hq.sinajs.cn/list='+symbol if sina else 'https://qt.gtimg.cn/q='+symbol,
                        headers={'Referer':'https://finance.sina.com.cn/'} if sina else None)
                    if response:
                        fact=parsed('QUOTE',instrument,lambda:source_facts.sina_quote(response[1],response[0],instrument,request,decimal_value)
                            if sina else source_facts.quote(response[1],response[0],instrument,decimal_value))
                        if fact and datetime.fromisoformat(fact['upstream_at'])<=datetime.fromisoformat(request['cutoff']):
                            if 'QUOTE' in request['groups']:facts.append(fact)
                            if 'STATUS' in request['groups']:
                                state=fact.get('method_status','UNKNOWN')
                                facts.append({**source_facts.authority(response[0],instrument,'STATUS'),'state':state,
                                    'reported_quote_as_of':fact['upstream_at'],'reported_limit_up':fact['reported_limit_up'],
                                    'reported_limit_down':fact['reported_limit_down'],'time_precision':'SECOND',
                                    'suspension':'UNKNOWN','risk_warning':'UNKNOWN','listing_stage':'UNKNOWN','current_ex_rights':'UNKNOWN',
                                    'status_basis':fact.get('status_basis'),'model_input_allowed':False,
                                    'reason':'明确固定样本；不确认实际当前状态' if fact.get('method_status') else '报价与名称不能确认当前异常状态'})
                                if state=='UNKNOWN':run['gaps'].append({'instrument':instrument,'group':'STATUS','code':'CURRENT_STATUS_UNKNOWN'})
                                if state in {'SUSPENDED','RISK_WARNING'}:
                                    observations.append({'kind':'STATUS_RISK_ALERT','classification':'FACT','instrument':instrument,
                                        'severity':'ATTENTION','basis_raw_hashes':[fact['raw_hash']],'state':state,
                                        'event_date':fact['trade_date'],'message':fact['status_basis'],'formal_judgment':'DISABLED'})
                            coverage.append({'instrument':instrument,'group':'QUOTE','returned_rows':1,'upstream_at':fact['upstream_at'],
                                'age_seconds':fact['age_seconds'],'raw_hash':fact['raw_hash'],'full_history_verified':False})
                        elif fact:run['gaps'].append({'instrument':instrument,'group':'QUOTE','code':'UPSTREAM_AFTER_CUTOFF'})
                for group,report,size in [('ADJUSTMENTS','RPT_SHAREBONUS_DET',5),('PERFORMANCE','RPT_LICO_FN_CPD',3)]:
                    if group not in request['groups']:continue
                    params={'reportName':report,'columns':'ALL','filter':'(SECURITY_CODE="'+instrument.split(':')[1]+'")',
                        'pageSize':size,'pageNumber':1,'sortColumns':'REPORT_DATE' if group=='ADJUSTMENTS' else 'REPORTDATE','sortTypes':-1}
                    response=fetch('eastmoney-actions' if group=='ADJUSTMENTS' else 'eastmoney-performance',instrument,group,
                        'https://datacenter-web.eastmoney.com/api/data/v1/get',params)
                    if response:
                        result=parsed(group,instrument,lambda:source_facts.financial(response[1],response[0],instrument,group,request,decimal_value))
                        if result:
                            rows,cov=result;facts.extend(rows);coverage.append(cov)
                event_groups={'ANNOUNCEMENTS','PERFORMANCE','MAJOR_EVENTS','ADJUSTMENTS'}&set(request['groups'])
                if event_groups:
                    response=fetch('eastmoney-announcements',instrument,'ANNOUNCEMENTS','https://np-anotice-stock.eastmoney.com/api/security/ann',
                        {'sr':-1,'page_size':30,'page_index':1,'ann_type':'A','stock_list':instrument.split(':')[1]})
                    if response:
                        result=parsed('ANNOUNCEMENTS',instrument,lambda:source_facts.announcement_candidates(response[1],instrument,request))
                        if result:
                            selected,cov=result;coverage.append({'instrument':instrument,'group':'ANNOUNCEMENTS',**cov,'raw_hash':response[0]['sha256']})
                            for group in ['ANNOUNCEMENTS','PERFORMANCE','MAJOR_EVENTS','ADJUSTMENTS']:
                                if group not in event_groups:continue
                                row=selected.get(group)
                                if not row:
                                    run['gaps'].append({'instrument':instrument,'group':group,'code':'NO_ORIGINAL_IN_BOUNDED_METADATA_PAGE'});continue
                                detail=fetch('eastmoney-original',instrument,group,'https://np-cnotice-stock.eastmoney.com/api/content/ann',
                                    {'art_code':row['art_code'],'page_index':1,'client_source':'web'},art_code=row['art_code'])
                                if not detail:continue
                                url=parsed(group,instrument,lambda:source_facts.attachment_url(detail[1]))
                                # Raw supplier HTML cannot direct the host to arbitrary local/network addresses.
                                try:
                                    target=httpx.URL(url) if url else None
                                except httpx.InvalidURL:
                                    target=None
                                if not target or target.scheme!='https' or target.host!='pdf.dfcfw.com' or target.username or target.password:
                                    run['gaps'].append({'instrument':instrument,'group':group,'code':'ORIGINAL_PDF_LINK_MISSING_OR_UNAPPROVED'});continue
                                document=fetch('eastmoney-original',instrument,group,url,art_code=row['art_code'],kind='PDF')
                                if document:
                                    fact=parsed(group,instrument,lambda:source_facts.original(detail[1],detail[0],instrument,group,row,document[0],document[1]))
                                    if fact:facts.append(fact)
        for instrument in request['instruments']:
            for group in request['groups']:
                rows=[f for f in facts if f['instrument']==instrument and f['group']==group]
                if not rows and not any(g['instrument']==instrument and g['group']==group for g in run['gaps']):
                    run['gaps'].append({'instrument':instrument,'group':group,'code':'NO_FACTS_IN_REQUEST_WINDOW'})
        for fact in facts:
            if fact['group']=='DAILY':
                calendar=self.market.rules.calendar(fact['instrument'].split(':')[0],date.fromisoformat(fact['trade_date']))
                fact['session_state']='TRADING_DAY' if calendar['is_trading_day'] is True else 'MARKET_CLOSED' if calendar['is_trading_day'] is False else 'CALENDAR_UNKNOWN'
                fact['calendar_source']={k:v for k,v in (calendar.get('source') or {}).items() if k in {'id','sha256'}} or None
                if fact['session_state']=='MARKET_CLOSED':
                    fact['errors'].append('PROVIDER_ROW_ON_CLOSED_MARKET_DATE');fact['model_daily_input_allowed']=False
                if fact['session_state']=='CALENDAR_UNKNOWN':
                    fact.setdefault('limitations',[]).append('CALENDAR_COVERAGE_UNKNOWN');fact['model_daily_input_allowed']=False
            disclosure=fact.get('disclosure_date')
            fact['event_cutoff_eligibility']='UNKNOWN_DATE_ONLY_SAME_DAY' if disclosure==datetime.fromisoformat(request['cutoff']).astimezone(SHANGHAI).date().isoformat() else 'WITHIN_REQUESTED_EVENT_WINDOW'
            fact['point_in_time_input_allowed']=datetime.fromisoformat(fact['available_at'])<=datetime.fromisoformat(request['cutoff']) and fact['event_cutoff_eligibility']!='UNKNOWN_DATE_ONLY_SAME_DAY'
            if not fact['point_in_time_input_allowed']:
                fact.setdefault('historical_limitations',[]).append('FIRST_RECEIPT_AFTER_REQUEST_CUTOFF_NOT_PAST_AVAILABLE_PROOF')
            missing=[]
            for field in request['required_fields']:
                parts=field.split('.',1)
                if len(parts)==2 and parts[0]!=fact['group']:continue
                key=parts[-1]
                if fact.get(key) is None:missing.append(key)
            if missing:
                fact['missing_required_fields']=missing
                if fact['group']=='DAILY':fact['model_daily_input_allowed']=False
                run['gaps'].append({'instrument':fact['instrument'],'group':fact['group'],'code':'REQUIRED_FIELDS_MISSING','fields':missing})
            if fact.get('errors'):
                observations.append({'kind':'DATA_QUALITY_ALERT','classification':'DETERMINISTIC_INFERENCE','instrument':fact['instrument'],
                    'severity':'ATTENTION','basis_raw_hashes':[fact['raw_hash']],'facts':fact['errors'],'formal_judgment':'DISABLED'})
            if fact['group']=='ADJUSTMENTS':
                pending=fact.get('document_hash') is not None or fact.get('action_state')=='IMPLEMENTATION_ANNOUNCED'
                observations.append({'kind':'PENDING_ACCOUNT_RECONCILIATION' if pending else 'ACTION_PLAN_REFERENCE','classification':'FACT','instrument':fact['instrument'],
                    'severity':'INFO','basis_raw_hashes':[fact['raw_hash']],'message':'外部权益分派公告已归档；到账、税费和持仓变化待券商事实确认',
                    'formal_judgment':'DISABLED'})
                if not pending:observations[-1]['message']='供应商登记分派预披露/计划；金额、除息日与实际到账未确认'
            if fact.get('document_hash'):
                observations.append({'kind':'DISCLOSED_COMPANY_EVENT','classification':'FACT','instrument':fact['instrument'],'severity':'INFO',
                    'basis_raw_hashes':[fact['raw_hash'],fact['document_hash']],'title':fact['title'],'disclosure_date':fact['disclosure_date'],
                    'formal_judgment':'DISABLED'})
        for instrument in request['instruments']:
            bars=sorted((f for f in facts if f['instrument']==instrument and f['group']=='DAILY' and f['adjustment']=='RAW' and f.get('close')),
                key=lambda f:f['trade_date'])
            actions={f['ex_date']:f for f in facts if f['instrument']==instrument and f['group']=='ADJUSTMENTS' and
                f.get('ex_date') and f.get('dividend_yuan_per_share') is not None}
            for previous,current in zip(bars,bars[1:]):
                before=Decimal(previous['close']);after=Decimal(current['close']);action=actions.get(current['trade_date'])
                if action:
                    observations.append({'kind':'EX_RIGHTS_PRICE_CONTEXT','classification':'DETERMINISTIC_INFERENCE','instrument':instrument,
                        'severity':'INFO','event_date':current['trade_date'],'basis_raw_hashes':[current['raw_hash'],action['raw_hash']],
                        'observed_raw_return':format((after-before)/before,'f'),
                        'cash_dividend_adjusted_return':format((after+Decimal(action['dividend_yuan_per_share'])-before)/before,'f'),
                        'message':'除息日原价变化与已披露现金分派并列核对；不是普通暴跌或账户到账证明',
                        'limitations':['SIMPLE_PRETAX_CASH_DIVIDEND_CONTEXT_NOT_COMPLETE_TOTAL_RETURN'], 'formal_judgment':'DISABLED'})
                elif (after-before)/before<=Decimal('-.10'):
                    observations.append({'kind':'PRICE_MOVE_OBSERVATION','classification':'DETERMINISTIC_INFERENCE','instrument':instrument,
                        'severity':'ATTENTION','event_date':current['trade_date'],'basis_raw_hashes':[previous['raw_hash'],current['raw_hash']],
                        'observed_raw_return':format((after-before)/before,'f'),'message':'原价显著变化；公司行为与当前状态仍需核对',
                        'limitations':['CORPORATE_ACTION_COVERAGE_NOT_COMPLETE'], 'formal_judgment':'DISABLED'})
        for observation in observations:
            bases=[f for f in facts if f['raw_hash'] in observation['basis_raw_hashes']]
            observation.update(observation_id=str(uuid4()),observed_at=now(),
                event_date=observation.get('event_date') or next((f.get('trade_date') or f.get('disclosure_date') for f in bases),None),
                time_precision=next((f.get('time_precision') for f in bases),None),
                unknown_items=['ACCOUNT_RECEIPT_NOT_CONFIRMED'] if observation['kind']=='PENDING_ACCOUNT_RECONCILIATION' else [],
                account_version=request['scope']['account_version'],list_version=request['scope']['list_version'],
                model_qualification='NOT_GRANTED',evidence_kind=self.evidence_kind)
        table=pa.Table.from_pylist([{'instrument':f['instrument'],'group':f['group'],'trade_date':f.get('trade_date'),
            'open':f.get('open'),'close':f.get('close'),'high':f.get('high'),'low':f.get('low'),
            'volume_shares':f.get('volume_shares'),'amount_yuan':f.get('amount_yuan'),'adjustment':f.get('adjustment'),
            'completion_state':f.get('completion_state'),'raw_hash':f['raw_hash'],'payload':encode(f)} for f in facts])
        buffer=BytesIO();pq.write_table(table,buffer)
        parquet=self.archive(buffer.getvalue(),'NORMALIZED_PARQUET','parquet',adapter_version=ADAPTER_VERSION)
        snapshot={'snapshot_id':str(uuid4()),'run_id':run['run_id'],'request_id':request_id,'facts':facts,
            'archives':archives,'parquet':parquet,'coverage':coverage,'observations':observations,'gaps':run['gaps'],
            'requested_instruments':request['instruments'],'requested_groups':request['groups'],
            'created_at':now(),'requested_cutoff':request['cutoff'],'namespace':'HISTORICAL' if request['purpose']=='RESEARCH' else 'ACTUAL',
            'evidence_kind':self.evidence_kind,'formal_judgment':'DISABLED','adapter_version':ADAPTER_VERSION}
        run.update(status='PARTIAL' if run['gaps'] and facts else 'FAILED' if not facts else 'COMPLETE',
            snapshot_id=snapshot['snapshot_id'],finished_at=now(),elapsed_seconds=round(time.monotonic()-started,3))
        with self.ledger.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                db.execute('INSERT INTO market_evidence_snapshots VALUES(?,?,?)',(snapshot['snapshot_id'],run['run_id'],encode(snapshot)))
                db.execute('UPDATE retrieval_runs SET value=? WHERE id=?',(encode(run),run['run_id']));db.commit()
            except BaseException:
                db.rollback();raise
        return run

    def replay(self,run_id):
        run=self.get('retrieval_runs',run_id)
        snapshot=self.get('market_evidence_snapshots',run['snapshot_id'])
        for archive in snapshot['archives']+[snapshot['parquet']]:
            self.raw(archive['sha256'])
        saved=pq.read_table(self.raw(snapshot['parquet']['sha256'])).to_pylist()
        facts=[json.loads(row['payload']) for row in saved]
        if facts!=snapshot['facts']:raise HTTPException(409,{'code':'PARQUET_SQLITE_FACTS_MISMATCH'})
        return {'run_id':run_id,'replay_kind':'IMMUTABLE_ARCHIVE_ONLY','adapter_version':snapshot['adapter_version'],
            'facts':facts,'observations':snapshot['observations'],'network_calls':0}

    def snapshots(self,instrument=None,group=None,available_before=None):
        if available_before and available_before.tzinfo is None:raise HTTPException(422,'可得时间筛选需要时区')
        with self.ledger.connection() as db:
            snapshots=[json.loads(row[0]) for row in db.execute('SELECT value FROM market_evidence_snapshots ORDER BY rowid DESC')]
        result=[]
        for snapshot in snapshots:
            facts=[f for f in snapshot['facts'] if (not instrument or f['instrument']==instrument) and
                (not group or f['group']==group) and (not available_before or datetime.fromisoformat(f['available_at'])<=available_before)]
            if instrument or group or available_before:
                if not facts:continue
            result.append({**snapshot,'facts':facts})
        return result

    def coverage(self,instrument=None,group=None):
        result=[]
        for snapshot in self.snapshots():
            for entry in snapshot['coverage']:
                if instrument and entry.get('instrument')!=instrument or group and entry.get('group')!=group:continue
                result.append({**entry,'snapshot_id':snapshot['snapshot_id'],'run_id':snapshot['run_id'],
                    'recorded_at':snapshot['created_at'],'evidence_kind':snapshot['evidence_kind'],
                    'available_time_basis':'ACTUAL_ACQUISITION_NOW; NO_POINT_IN_TIME_HISTORY_PROOF',
                    'historical_revision_proof':'NOT_AVAILABLE','namespace':snapshot['namespace']})
        return {'coverage':result,'complete_source_history':False,'model_qualification':'NOT_GRANTED'}

"""Versioned deterministic financial reading; facts, metrics and PDF derivations stay immutable."""
import hashlib,json
from datetime import date,datetime
from decimal import Decimal,InvalidOperation
from uuid import uuid4
from fastapi import HTTPException
from roll.accounts.ledger import encode,now
from roll.market.financial_metrics import metrics

VERSION='financial-observation-v1'
FRESH_DAYS=120
LIMITATIONS=['描述性观察，不构成收益预测、目标价或买卖建议','合并口径与报告期以保存原件为准，历史PIT资格未授予',
    '未知、零或负基期不补数、不推排名','行业专用指标仅对一般非金融企业给出；其他行业只展示通用原表']
REASON={'PRIOR_YTD_MISSING_OR_INCOMPARABLE':'前期累计缺失或口径不可比','FOUR_COMPARABLE_QUARTERS_REQUIRED':'需要四个连续可比季度',
    'NON_POSITIVE_DENOMINATOR':'分母为零或负','MISSING_OR_INCOMPARABLE_INPUT':'输入缺失或口径不可比',
    'CURRENT_FACT_UNKNOWN':'当前事实未知','NON_QUARTER_PERIOD':'非标准季度报告期','OPERATING_REVENUE_CONFLICT':'营业收入字段冲突',
    'FINANCIAL_OR_UNKNOWN_INDUSTRY_NOT_APPLICABLE':'行业专用口径不适用','NON_POSITIVE_BASE':'基期为零或负'}


def money(value):
    try:number=Decimal(str(value))/Decimal(100000000)
    except (InvalidOperation,ValueError,TypeError):return '未知'
    return f'{number.quantize(Decimal("0.01")):,.2f} 亿元'


def percent(value):
    try:number=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError):return '未知'
    return f'{number.quantize(Decimal("0.01")):+}%'


def plain(value):
    try:return str(Decimal(str(value)).quantize(Decimal('0.01')))
    except (InvalidOperation,ValueError,TypeError):return '未知'


def known(metric):
    return metric if metric and metric.get('status')=='KNOWN' and metric.get('value') is not None else None


class FinancialObservations:
    def __init__(self,evidence,income,statements):
        self.evidence,self.ledger=evidence,evidence.ledger
        self.income,self.statements=income,statements
        with self.ledger.connection() as db:
            db.execute('CREATE TABLE IF NOT EXISTS financial_observations(id TEXT PRIMARY KEY,instrument TEXT,input_sha256 TEXT,created_at TEXT,known_by TEXT,value TEXT,UNIQUE(instrument,input_sha256))')

    def facts(self,instrument,stamp):
        with self.ledger.connection() as db:
            rows=db.execute('SELECT value FROM financial_income_facts WHERE instrument=? ORDER BY rowid',(instrument,)).fetchall()
        return [json.loads(row[0]) for row in rows if datetime.fromisoformat(json.loads(row[0])['available_at'])<=stamp]

    def parses(self,shas):
        if not shas:return {}
        with self.ledger.connection() as db:
            rows=db.execute('SELECT value FROM financial_document_parses').fetchall()
        output={}
        for row in rows:
            value=json.loads(row[0])
            if value.get('source_sha256') in shas and value.get('artifact'):
                output.setdefault(value['source_sha256'],[]).append({'parse_id':value['parse_id'],'status':value['status'],
                    'first_page':value['first_page'],'last_page':value['last_page'],'artifact_sha256':value['artifact']['sha256']})
        return output

    def build(self,instrument,known_by=None):
        stamp=known_by or datetime.fromisoformat(now())
        if stamp.tzinfo is None or stamp>datetime.fromisoformat(now()):
            raise HTTPException(422,'FINANCIAL_OBSERVATION_CUTOFF_REQUIRES_PAST_AWARE_TIME')
        view=metrics(self.income,self.statements,instrument,stamp)
        periods=view['periods'];facts=self.facts(instrument,stamp)
        latest_period=periods[0] if periods else None
        latest_income=None
        if latest_period:
            same=[fact for fact in facts if fact['statement']=='INCOME' and fact['report_period']==latest_period['report_period']]
            latest_income=max(same,key=lambda fact:fact['version']) if same else None
        org_type=latest_income.get('original_fields',{}).get('ORG_TYPE') if latest_income else None
        support='GENERAL_SUPPORTED' if org_type=='通用' else ('UNKNOWN_INDUSTRY_NOT_SUPPORTED' if org_type in (None,'') else 'FINANCIAL_OR_SPECIAL_NOT_SUPPORTED')
        times={}
        if latest_income:
            times={key:latest_income.get(key) for key in ('reported_publication_date','reported_update_date','first_received_at','available_at')}
        revised=[fact for fact in facts if fact.get('version',1)>1 or str(fact.get('reported_update_date') or '')[:10]>str(fact.get('reported_publication_date') or '')[:10]]
        latest_metrics=latest_period['metrics'] if latest_period else {}
        analysis=[];gaps=[]
        if latest_period:
            revenue=known(latest_metrics.get('revenue'));yoy=known(latest_metrics.get('revenue_yoy'))
            profit=known(latest_metrics.get('parent_net_profit'));profit_yoy=known(latest_metrics.get('parent_net_profit_yoy'))
            cash=known(latest_metrics.get('operating_cash_flow'));cash_ratio=known(latest_metrics.get('cash_profit_ratio'))
            gross=known(latest_metrics.get('gross_margin'));net=known(latest_metrics.get('net_margin'));debt=known(latest_metrics.get('debt_ratio'))
            if revenue:
                line=f"{latest_period['report_period']} 营业收入 {money(revenue['value'])}"
                if yoy:line+=f"，同比 {percent(yoy['value'])}"
                analysis.append({'kind':'FACT','metrics':['revenue','revenue_yoy'],'text':line+'。','source_fact_ids':revenue['source_fact_ids']})
            if profit:
                line=f"归属于母公司股东的净利润 {money(profit['value'])}"
                if profit_yoy:line+=f"，同比 {percent(profit_yoy['value'])}"
                analysis.append({'kind':'FACT','metrics':['parent_net_profit','parent_net_profit_yoy'],'text':line+'。','source_fact_ids':profit['source_fact_ids']})
            if cash:
                line=f"经营活动现金流量净额 {money(cash['value'])}"
                if cash_ratio:line+=f"，经营现金/净利润 {plain(cash_ratio['value'])}"
                analysis.append({'kind':'FACT','metrics':['operating_cash_flow','cash_profit_ratio'],'text':line+'。','source_fact_ids':cash['source_fact_ids']})
            ratios=[]
            if gross:ratios.append(f"毛利率 {plain(gross['value'])}%")
            if net:ratios.append(f"净利率 {plain(net['value'])}%")
            if debt:ratios.append(f"资产负债率 {plain(debt['value'])}%")
            if ratios:analysis.append({'kind':'FACT','metrics':[key for key,item in (('gross_margin',gross),('net_margin',net),('debt_ratio',debt)) if item],'text':'；'.join(ratios)+'。','source_fact_ids':sorted({i for item in (gross,net,debt) if item for i in item['source_fact_ids']})})
            for name in ('revenue','parent_net_profit','operating_cash_flow','revenue_yoy','parent_net_profit_yoy','gross_margin','net_margin','cash_profit_ratio','debt_ratio'):
                metric=latest_metrics.get(name)
                if metric and metric.get('status')!='KNOWN':gaps.append({'metric':name,'reason':metric.get('reason'),'description':REASON.get(metric.get('reason'),metric.get('reason') or '未知')})
        else:
            gaps.append({'metric':'ALL','reason':'NO_SAVED_FINANCIAL_FACTS','description':'该截止时点没有已保存财务事实'})
        conclusions=[]
        if latest_period:
            direction=[]
            if known(latest_metrics.get('revenue_yoy')):
                delta=Decimal(latest_metrics['revenue_yoy']['value']);direction.append('营业收入同比'+('增长' if delta>0 else '下降' if delta<0 else '持平'))
            if known(latest_metrics.get('parent_net_profit_yoy')):
                delta=Decimal(latest_metrics['parent_net_profit_yoy']['value']);direction.append('归母净利润同比'+('增长' if delta>0 else '下降' if delta<0 else '持平'))
            if known(latest_metrics.get('debt_ratio')):direction.append('资产负债率 '+plain(latest_metrics['debt_ratio']['value'])+'%')
            if known(latest_metrics.get('cash_profit_ratio')):direction.append('经营现金/净利润 '+plain(latest_metrics['cash_profit_ratio']['value']))
            conclusions.append({'kind':'DESCRIPTIVE','text':('；'.join(direction) if direction else '当前没有足够的口径可比事实形成描述性结论')+'。不构成收益预测、行业排名或买卖建议。'})
        trend=[]
        for period in periods[:4]:
            item={'report_period':period['report_period']}
            for name in ('revenue','revenue_yoy','parent_net_profit','parent_net_profit_yoy','gross_margin','net_margin','cash_profit_ratio','debt_ratio'):
                metric=known(period['metrics'].get(name))
                if metric:item[name]=metric['value']
            trend.append(item)
        documents=[]
        for fact in facts:
            document=fact.get('semantic_document') or {}
            sha=document.get('sha256')
            if sha and all(item['sha256']!=sha for item in documents):
                documents.append({'sha256':sha,'source_url':document.get('source_url'),'report_period':fact['report_period'],'page':document.get('page'),'parses':[]})
        parsed=self.parses({item['sha256'] for item in documents})
        for item in documents:item['parses']=parsed.get(item['sha256'],[])
        if any(not item['parses'] for item in documents):gaps.append({'metric':'PDF_DERIVATION','reason':'PDF_NOT_PARSED','description':'部分已存PDF尚无表格/页码派生，仅可查看原件'})
        if support!='GENERAL_SUPPORTED':gaps.append({'metric':'INDUSTRY','reason':support,'description':'该行业未支持专用比率；通用原表仍可查看'})
        status='MISSING' if not latest_period else ('FRESH' if 0<=(stamp.date()-date.fromisoformat(latest_period['report_period'])).days<=FRESH_DAYS else 'STALE')
        digest=hashlib.sha256(json.dumps({'version':VERSION,'known_by':stamp.isoformat() if known_by is not None else 'CURRENT',
            'facts':sorted((fact['fact_id'],fact.get('version'),fact.get('raw_sha256')) for fact in facts),
            'parses':sorted((parse['parse_id'],parse['status']) for values in parsed.values() for parse in values)},sort_keys=True).encode()).hexdigest()
        content={'instrument':instrument,'known_by':stamp.isoformat(),'created_at':now(),'calculation_version':VERSION,'input_sha256':digest,
            'status':status,'freshness_days':None if not latest_period else (stamp.date()-date.fromisoformat(latest_period['report_period'])).days,
            'revision':{'revised':bool(revised),'fact_ids':[fact['fact_id'] for fact in revised],'latest_update':times.get('reported_update_date')},
            'industry':{'organization_type':org_type,'support':support},'latest_period':latest_period['report_period'] if latest_period else None,'times':times,
            'analysis':analysis,'conclusions':conclusions,'trend':trend,'gaps':gaps,'documents':documents,
            'periods':periods[:4],'source_versions':view['source_versions'],'limitations':LIMITATIONS,
            'network_calls':0,'historical_pit_eligible':False,'system_usable':False,'capability':'NOT_GRANTED'}
        return content

    def store(self,instrument,content):
        with self.ledger.connection() as db:
            existing=db.execute('SELECT id,value FROM financial_observations WHERE instrument=? AND input_sha256=?',(instrument,content['input_sha256'])).fetchone()
            if existing:return json.loads(existing[1])
            version=db.execute('SELECT COUNT(*) FROM financial_observations WHERE instrument=?',(instrument,)).fetchone()[0]+1
            identifier=str(uuid4());content=dict(content,observation_id=identifier,observation_version=version)
            db.execute('INSERT OR IGNORE INTO financial_observations VALUES(?,?,?,?,?,?)',(identifier,instrument,content['input_sha256'],content['created_at'],content['known_by'],encode(content)));db.commit()
            row=db.execute('SELECT id,value FROM financial_observations WHERE instrument=? AND input_sha256=?',(instrument,content['input_sha256'])).fetchone()
            return json.loads(row[1])

    def listing(self,instrument,known_by=None):
        current=self.store(instrument,self.build(instrument,known_by))
        with self.ledger.connection() as db:
            rows=[json.loads(row[0]) for row in db.execute('SELECT value FROM financial_observations WHERE instrument=? ORDER BY rowid DESC',(instrument,))]
        versions=[{'observation_id':row['observation_id'],'version':row['observation_version'],'known_by':row['known_by'],'status':row['status'],'created_at':row['created_at']} for row in rows]
        return {'instrument':instrument,'current':current,'versions':versions,'network_calls':0,'system_usable':False,'capability':'NOT_GRANTED'}

    def get(self,identifier):
        with self.ledger.connection() as db:
            row=db.execute('SELECT value FROM financial_observations WHERE id=?',(identifier,)).fetchone()
        if not row:raise HTTPException(404,'FINANCIAL_OBSERVATION_NOT_FOUND')
        return json.loads(row[0])

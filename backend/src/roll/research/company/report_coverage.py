"""Frozen source receipts and sourceful appendix topics; no latest lookup or model authority."""
import json
import re
from .service import record,verified
from .report_template import table,cell

CATEGORIES=('本体披露','行业时序','产业链','同业对照','估值序列','研报','官方监管')
TOPICS={'A':{'company_history':'沿革','capital_event':'资本事件'},
        'B':{'ownership_structure':'股权','governance':'治理'},
        'C':{'capacity_technology':'产能与技术','channel_structure':'渠道','staff_structure':'人员'}}
CHANNELS={'本体披露':'发行人年报、公告与招股说明书','行业时序':'统计机构、行业协会的同口径年度原表',
          '产业链':'上下游发行人披露与官方行业资料','同业对照':'可比公司原始披露与交易所上市资料',
          '估值序列':'交易所价格、股本与同期间盈利原件','研报':'明确作者、日期及引用范围的研究原件','官方监管':'监管机关及交易所原始文件'}
TOPIC_CUES={'company_history':r'成立|设立|始建|沿革|改制|founded',
 'capital_event':r'股本|增发|分红|股利|回购|资本|发行|上市',
 'ownership_structure':r'股东|股权|持股|控制人',
 'governance':r'董事|监事|治理|审计|委员会',
 'capacity_technology':r'产能|产线|生产工艺|生产技术|技术路线',
 'channel_structure':r'经销|渠道|销售网点|直销',
 'staff_structure':r'员工|职工|人数|人员结构'}
COLLECTOR_CATEGORIES={'akshare-financial-income':'本体披露','akshare-financial-supplement':'本体披露'}

ISSUER_BUSINESSES={'FINANCIAL_STATEMENT','BALANCE_NOTE','BUSINESS_STRUCTURE','COMMITMENT_NOTE','DISCLOSURE_AVAILABILITY'}


def capture(research,job,payload):
    """Only the request's explicit parent chain, at most eight jobs. Never choose latest."""
    materials={m['material_id']:m for m in payload['materials']};facts={f['version_id']:f for f in payload['facts']}
    attempts=[];unclassified_attempts=[];quotes=[];lineage=[];seen=set();seen_quotes=set();current=job
    for _ in range(8):
        if current['job_id'] in seen:break
        seen.add(current['job_id']);lineage.append(current['job_id'])
        for receipt in (current.get('acquisition') or {}).get('receipts',[]):
            category=receipt.get('category')
            if category not in CATEGORIES and receipt.get('source'):
                category=COLLECTOR_CATEGORIES.get(receipt['source'])
                entry={**receipt,'category':category,'job_id':current['job_id'],'relation':'CURRENT_JOB' if current['job_id']==job['job_id'] else 'EXPLICIT_PARENT_HISTORY','origin_kind':'REGISTERED_COLLECTOR_RUN','verified_check':None}
                if category:attempts.append(entry)
                else:unclassified_attempts.append(entry)
                continue
            if category not in CATEGORIES:continue
            check_id=receipt.get('check_id');check=None
            if check_id:
                with research.ledger.connection() as db:row=db.execute('SELECT value FROM company_research_checks WHERE check_id=?',(check_id,)).fetchone()
                if row:check=verified(json.loads(row[0]))
            valid=bool(check and check['company_id']==job['company_id'] and category in check['requested_scopes'] and
                any(all(r.get(k)==receipt.get(k) for k in ['status','material_id','raw_sha256','started_at','finished_at']) for r in check['source_receipts']))
            material=materials.get(receipt.get('material_id'))
            if receipt.get('status')=='SUCCESS':valid=bool(valid and material and material['raw_sha256']==receipt.get('raw_sha256'))
            if valid:
                attempts.append(dict(**receipt,job_id=current['job_id'],relation='CURRENT_JOB' if current['job_id']==job['job_id'] else 'EXPLICIT_PARENT_HISTORY',verified_check=check))
        for receipt in current.get('quote_receipts',[]):
            fact=facts.get(receipt.get('fact_version_id'));material=materials.get(receipt.get('material_id'))
            if (receipt.get('status')=='SUCCESS' and fact and material and fact['material_id']==material['material_id'] and
                receipt['quote']==fact['value'] and receipt['original_sha256']==material['raw_sha256'] and receipt['page']==fact['page'] and receipt['table']==fact['table']):
                if fact['version_id'] not in seen_quotes:
                    quotes.append({**receipt,'job_id':current['job_id'],'metric':fact['metric']});seen_quotes.add(fact['version_id'])
        parent=current.get('parent_job_id')
        if not parent:break
        current=research.reports.get(parent)
        if current['company_id']!=job['company_id']:break
    return build(payload,attempts,quotes,lineage,job['job_id'],unclassified_attempts)


def role(fact,material):
    """Specific frozen business context overrides legacy default source labels."""
    if fact['business']=='EXTERNAL_VALUATION_INPUT' or fact['business']=='MACRO':return 'EXTERNAL_VALUATION_INPUT'
    upstream=material.get('upstream') or {}
    if upstream.get('source_role')=='EXTERNAL_CONTEXT':return 'EXTERNAL_CONTEXT'
    if fact['business'].startswith('PEER:'):return 'PEER_COMPANY'
    if fact['business'] in ISSUER_BUSINESSES:return 'REGISTERED_ISSUER_FINANCIAL_OR_OPERATING_SOURCE'
    return 'SOURCE_ROLE_UNVERIFIED'


def build(payload,attempts=(),quotes=(),lineage=(),current_job_id=None,unclassified_attempts=()):
    by_material={m['material_id']:m for m in payload['materials']};facts=payload['facts']
    categories={name:dict(state='NOT_CHECKED',material_ids=[],attempts=[]) for name in CATEGORIES}
    unclassified=[];roles={}
    quote_ids={q['fact_version_id'] for q in quotes}
    for material in payload['materials']:
        linked=[f for f in facts if f['material_id']==material['material_id']]
        for fact in linked:
            label=role(fact,material)
            if label=='SOURCE_ROLE_UNVERIFIED' and fact['version_id'] in quote_ids and fact['metric']!='term_definition':label='REGISTERED_LITERAL_COMPANY_QUOTE'
            roles[fact['version_id']]=label
        explicit=(material.get('upstream') or {}).get('category')
        category=explicit if explicit in CATEGORIES else None
        if linked and all(roles[f['version_id']]=='EXTERNAL_VALUATION_INPUT' for f in linked):category='估值序列'
        elif not category and (any(roles[f['version_id']] in {'REGISTERED_ISSUER_FINANCIAL_OR_OPERATING_SOURCE','REGISTERED_LITERAL_COMPANY_QUOTE'} for f in linked)):category='本体披露'
        if category:categories[category]['material_ids'].append(material['material_id'])
        else:unclassified.append(material['material_id'])
    for receipt in attempts:categories[receipt['category']]['attempts'].append(receipt)
    blocks=[]
    for name,row in categories.items():
        receipts=row['attempts'];current=[r for r in receipts if r['relation']=='CURRENT_JOB'];historic=[r for r in receipts if r['relation']!='CURRENT_JOB']
        success=any(r['status']=='SUCCESS' for r in receipts);failure=any(r['status']!='SUCCESS' for r in receipts)
        row['state']='CHECKED_NO_NEW_RECORDS' if receipts and all(r.get('source_status')=='EMPTY' for r in receipts) else 'PARTIAL' if success and failure else 'ACQUIRED' if success else 'FAILED' if failure else 'REFERENCED' if row['material_ids'] else 'NOT_CHECKED'
        status=('引用既有档案/已查无新增记录' if row['material_ids'] else '缺口/已查无新增记录') if row['state']=='CHECKED_NO_NEW_RECORDS' else '已取/本次引用' if row['material_ids'] else '缺口/取得失败' if failure else '缺口/已查尚无所需材料' if receipts else '缺口/本次未发起'
        notes=[]
        def attempt_text(r):
            return (r['status']+' / '+r.get('source_url',r.get('source','未登记URL'))+' / '+str(r.get('check_id',r.get('run_id','未形成run')))
                +' / '+r.get('evidence_kind','证据类型未知')+' / 实际网络检查 '+str(r.get('network_check_performed',False))
                +' / 开始 '+str(r.get('started_at'))+' / 完成 '+str(r.get('finished_at'))
                +' / 新增材料 '+str(r.get('new_material_count','未计算'))+' / 错误 '+str(r.get('error',{})))
        if current:notes.append('本次已执行记录：'+ '; '.join(attempt_text(r) for r in current))
        else:notes.append('本次未发起该类别网络检查；REUSE或未列入请求不代表经营未变')
        if historic:notes.append('明确父任务的历史取得/失败，本次只引用：'+ '; '.join(r['job_id']+' / '+attempt_text(r) for r in historic))
        for r in receipts:
            check=r.get('verified_check') or {}
            if r['status']!='SUCCESS' and check.get('last_success_check_id'):
                notes.append('本次失败；此前成功检查 '+check['last_success_check_id']+' / '+str(check.get('last_success_at'))+' 保留，未刷新成功时间')
        if row['state']=='CHECKED_NO_NEW_RECORDS':notes.append('本次未取得新增记录；不代表经营未变、风险未命中或所需资料已经齐全')
        if row['material_ids']:
            notes.append('固定归档材料：'+ '; '.join(i+' / '+by_material[i]['source_url']+' / 实际入库 '+by_material[i]['received_at'] for i in row['material_ids']))
            if name=='估值序列' and any(roles.get(f['version_id'])=='EXTERNAL_VALUATION_INPUT' for f in facts if f['material_id'] in row['material_ids']):notes.append('含外部估值参数；不是发行人披露，也不等于完整历史价格/估值序列')
        else:notes.append('尚无本类别已绑定原件')
        for identifier in row['material_ids']:
            intermediate=((by_material[identifier].get('upstream') or {}).get('acquisition') or {}).get('status')
            finals=[r['status'] for r in receipts if r.get('material_id')==identifier]
            if intermediate and finals and any(state!=intermediate for state in finals):notes.append('原材料登记的中间状态 '+intermediate+' 保留；明确绑定的最终历史/本次回执 '+str(finals)+'，不是覆盖原记录')
        notes.append('下一渠道：'+CHANNELS[name]+'；需要条件：明确期间、主体、口径及原件坐标')
        blocks.append('## '+name+'\n'+table(['项目','状态','真实记录与缺口'],[[name,status,'；'.join(notes)]]))
    if unclassified_attempts:
        blocks.append('## 未分类的实际检查\n'+table(['来源','真实状态','归类边界'],[[r.get('source'),r.get('status'),'已执行但不冒充公司研报/官方监管；run '+str(r.get('run_id'))] for r in unclassified_attempts]))
    appendix_rows={key:[] for key in TOPICS}
    for fact in facts:
        if fact['version_id'] not in quote_ids or fact['value_type']!='TEXT' or fact['kind']!='DISCLOSED' or roles.get(fact['version_id']) in {'EXTERNAL_VALUATION_INPUT','EXTERNAL_CONTEXT','PEER_COMPANY'}:continue
        for key,topics in TOPICS.items():
            if fact['metric'] in topics and re.search(TOPIC_CUES[fact['metric']],str(fact['value']),re.I) and not re.search(r'未知|未披露|未提供|资料不足|不详',str(fact['value'])):
                material=by_material[fact['material_id']]
                appendix_rows[key].append(dict(topic=fact['metric'],title=topics[fact['metric']],fact_version_id=fact['version_id'],
                    text=fact['value'],period=fact['period_start']+'/'+fact['period_end'],scope=fact['scope'],material_id=material['material_id'],
                    original_sha256=material['raw_sha256'],page=fact['page'],table=fact['table'],original_api='/api/company-research/materials/'+material['material_id']+'/original'))
    appendices={key:'PASS' if set(topics)<={r['topic'] for r in appendix_rows[key]} else 'UNKNOWN' for key,topics in TOPICS.items()}
    return record(dict(categories=categories,unclassified_material_ids=unclassified,fact_source_roles=roles,quote_proofs=list(quotes),lineage=list(lineage),
        ledger_markdown='\n\n'.join(blocks),unclassified_attempts=list(unclassified_attempts),appendices=appendices,appendix_rows=appendix_rows,
        scope='归档取得/本次尝试/明确历史回执分列；原文引文覆盖不是独立事实背书',current_job_id=current_job_id))


def appendix(book,key):
    rows=book['appendix_rows'][key];covered={r['topic'] for r in rows};missing=[title for topic,title in TOPICS[key].items() if topic not in covered]
    body=table(['主题','按原文披露','期间/范围','原件坐标/引用'],[[r['title'],r['text'],r['period']+' / '+str(r['scope']),
        str(r['page'] or '物理页不适用')+' / '+str(r['table'])+' / '+r['fact_version_id']] for r in rows]) if rows else ''
    for row in rows:body+='\n\n[原件 '+cell(str(row['page'] or row['table']))+']('+row['original_api']+')'
    body+='\n\n'+('缺口：'+ '、'.join(missing)+'尚无已核对原文引文；取得原件并核页/表后形成新共享快照，不能靠章节候选补成事实。' if missing else '所列主题有原文引文；覆盖不表示独立事实审计或治理/经营风险结论。')
    return body


DEFINITIONS={
 'FCFF':('企业自由现金流','供全部资本提供者的经营现金流口径，须扣经营再投资。'),
 'WACC':('加权平均资本成本','按资本权重合成的折现率，使用固定经济审核的币种和期间。'),
 'CFO':('经营活动现金流','现金流量表经营活动净额；不直接等于正常化企业自由现金流。'),
 'ROIC':('投入资本回报率','税后经营利润相对投入资本的口径，需保持分子分母一致。'),
 'ROE':('净资产收益率','归属口径一致的净利润相对权益的回报率。'),
 'NOPAT':('税后经营利润','按固定税率口径计算的税后经营利润。'),
 'EBIT':('息税前利润','扣除经营成本费用、尚未扣利息和所得税的口径。'),
 'EPS':('每股收益','归属股东利润相对对应股数，不能用集团经营利润替代。'),
 'PE':('市盈率','股价与同口径每股收益的比值。'),
 'PB':('市净率','股价与同口径每股净资产的比值。'),
 'EV':('企业价值','经营资产价值口径；与归母权益价值须按固定权益桥区别。'),
 'DCF':('现金流折现','按固定现金流路径及折现率计算条件价值的方法。'),
 'EPV':('盈利能力价值','以正常化持续盈利为基础的条件参照。'),
 'NCI':('少数股东权益','合并权益中不归属于母公司股东的权益部分。'),
 'ERP':('权益风险溢价','权益相对无风险利率所要求的风险补偿输入。'),
 'beta':('系统风险暴露系数','无量纲风险系数，不能作为百分比统一换算。'),
 'CNY':('人民币','人民币货币代码；币种本身不决定万元或亿元尺度。')}


def glossary(markdown,book):
    """Only terms actually used before appendices, with the real first chapter location."""
    body=markdown.split('# 附录 A ',1)[0];rows=[];used={};links=[]
    for term,(chinese,definition) in DEFINITIONS.items():
        match=re.search(r'(?<![A-Za-z])'+re.escape(term)+r'(?![A-Za-z])',body)
        if not match:continue
        headings=list(re.finditer(r'^#{1,3} (.+)$',body[:match.start()],re.M));location=headings[-1].group(1) if headings else '速览'
        rows.append([term+' / '+chinese,definition,location,'固定模板与计算口径定义，非公司事实'])
        used[term]=location
    for proof in book['quote_proofs']:
        if proof.get('metric')!='term_definition':continue
        text=proof['quote'];match=re.match(r'([^：:\n]{1,24})[：:]\s*(.+)',text)
        if not match:continue
        term,definition=match.groups()
        if term in used or term not in body:continue
        first=body.index(term);headings=list(re.finditer(r'^#{1,3} (.+)$',body[:first],re.M));location=headings[-1].group(1) if headings else '速览'
        rows.append([term,definition,location,'原件 '+str(proof['page'] or proof['table'])+' / '+proof['original_sha256']]);used[term]=location
        links.append('[定义原件 '+cell(term)+'](/api/company-research/materials/'+proof['material_id']+'/original)')
    return dict(markdown=(table(['术语','一句话解释','首次位置','定义依据'],rows)+'\n\n'+'；'.join(links)) if rows else '正文未使用已核对定义的专业缩写；行业专有定义尚待原文取证，不填未用词凑行。',terms=used)

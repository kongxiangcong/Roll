"""Derived screening worksheet. Candidate conclusions never authorize a PASS."""
from decimal import Decimal,InvalidOperation
import json
import re
import time
from typing import Literal
from pydantic import Field
from .models import Command
from .service import fingerprint

TOPICS={
    1:[['货币资金','cash'],['有息负债','debt'],['举债','borrowing']],
    2:[['经营活动现金流','cfo'],['净利润','net_profit']],
    3:[['总额','净额','商业实质','贸易']],4:[['应收'],['营业收入','营收'],['收现']],
    5:[['毛利率','gross_margin'],['同业']],6:[['关联'],['收入','销售','采购'],['其他应收','重叠']],
    7:[['商誉','goodwill'],['并购','对赌','承诺期']],8:[['坏账','存货跌价','计提'],['同业','历史']],
    9:[['研发'],['资本化'],['同业']],10:[['少数股东'],['权益'],['损益']],
    11:[['税率','税负'],['同业'],['政策']],12:[['审计意见','无保留','audit_opinion'],['改聘','更换','变更','appointed'],['报酬','费用','审计费','fee']],
    13:[['年报'],['延期','修正','更正']],14:[['质押'],['控股股东','持股'],['平仓','无质押','未质押']],
    15:[['减持'],['解禁']],16:[['立案','处罚','市场禁入','谴责']],17:[['问询','关注函'],['回复']],
    18:[['非经营','资金占用'],['违规担保']],19:[['实控人','控制权'],['变更']],
    20:[['诉讼','仲裁'],['担保']],21:[['财务总监'],['董秘','董事会秘书'],['独董','独立董事'],['审计机构']],
    22:[['分红'],['定增','发债','融资']],23:[['前五','前5','top5_customer']],24:[['前五','前5','top5_supplier']],
    25:[['产品','业务线','product'],['区域','市场','region']],26:[['产能利用率'],['扩产']],
    27:[['存货'],['周转','营收']],28:[['账龄'],['大客户','应收']],29:[['股本'],['供股','配售','合股','可转债']],
    30:[['核数师','审计机构'],['辞任','更换','退任']],31:[['审计意见'],['持续经营']],
    32:[['停牌'],['复牌']],33:[['股价'],['成交额','流动性']],34:[['股份抵押','抵押'],['CCASS','集中度']],
    35:[['关连交易'],['年度上限','豁免','独立股东']],36:[['注册','VIE','股权架构'],['权利','分红']],
    37:[['年报','中报'],['延期','及时'],['盈利警告','profit warning']],38:[['私有化'],['摊薄','少数股东']]}
HISTORY_YEARS={2:3,4:2,5:2,8:2,9:2,10:3,11:2,13:3,15:2,19:3,21:2,22:2,26:2,27:2,28:2,29:5,30:3,32:3,37:3,38:3}


class RiskWorkpaperRow(Command):
    number: int = Field(ge=1,le=38)
    fact_version_ids: list[str] = Field(min_length=1,max_length=20)
    candidate_outcome: Literal['CLEAR','HIT','UNKNOWN'] = 'UNKNOWN'
    reason: str = Field(min_length=1,max_length=2000)
    review_method: Literal['AUTO','DISCLOSURE_REVIEW'] = 'AUTO'
    disclosure_scope_reason: str | None = Field(default=None,min_length=30,max_length=2000)


def json_pointer(raw,pointer):
    value=json.loads(raw)
    if not pointer or not pointer.startswith('/'):
        raise ValueError('Original JSON pointer required')
    for part in pointer.split('/')[1:]:
        part=part.replace('~1','/').replace('~0','~')
        value=value[int(part)] if isinstance(value,list) else value[part]
    return value


def build_screening(research,company,items,facts,rows):
    facts={f['version_id']:f for f in facts}
    candidates={row['number']:row for row in rows}
    output=[]
    for item in items:
        deadline=time.monotonic()+20
        row=candidates.get(item['number'])
        result=dict(**item,outcome='UNKNOWN',coverage_outcome='UNKNOWN',fact_version_ids=[],reason='未取得覆盖该项的可核原件/事实及有据判断',
            workpaper_kind='DERIVED_WORKPAPER',verification='UNKNOWN_NOT_FINANCIAL_GREEN_LIGHT')
        if not row:
            output.append(result);continue
        selected=[facts[i] for i in row['fact_version_ids'] if i in facts]
        result.update(fact_version_ids=[f['version_id'] for f in selected],candidate_outcome=row['candidate_outcome'],candidate_reason=row['reason'])
        verified=[]
        for fact in selected:
            material=research.material(fact['material_id'],company['company_id'])
            if fact['kind']!='DISCLOSED' or time.monotonic()>=deadline:continue
            if material['media_type']=='application/pdf' and fact.get('page'):
                try:
                    from .report_quotes import read_pdf_page
                    pages=[int(v) for v in re.findall(r'\d+',fact['page'])]
                    if len(pages)==2 and pages[1]>=pages[0] and pages[1]-pages[0]<=2:
                        pages=list(range(pages[0],pages[1]+1))
                    if not 1<=len(pages)<=3:continue
                    texts=[]
                    for page in pages:
                        if time.monotonic()>=deadline:break
                        texts.append(read_pdf_page(research,material,page))
                    if fact['value_type']=='TEXT' and any(fact['value'] in text for text in texts):verified.append(fact)
                    elif fact['value_type']=='NUMBER':
                        tokens=[v.replace(',','').replace('，','') for text in texts for v in re.findall(r'[-+]?\d[\d,，]*(?:\.\d+)?',text)]
                        if any(Decimal(v)==Decimal(fact['value']) for v in tokens):verified.append(fact)
                except Exception:
                    continue
                continue
            if material['media_type']=='text/plain' and fact['value_type']=='TEXT':
                if fact['value'] in research.material_bytes(material['material_id']).decode('utf-8-sig'):verified.append(fact)
                continue
            if material['media_type']!='application/json':continue
            try:
                original=research.material_bytes(material['material_id'])
                value=json_pointer(original,fact['table'])
                if fact['value_type']=='NUMBER' and Decimal(str(value))==Decimal(fact['value']):
                    verified.append(fact)
                elif fact['value_type']=='TEXT' and str(value)==fact['value']:
                    verified.append(fact)
            except (KeyError,ValueError,TypeError,InvalidOperation):
                continue
        numeric={f['metric']:f for f in verified if f['value_type']=='NUMBER'}
        names={7:('goodwill','equity',Decimal('0.3')),6:('related_sales','revenue',Decimal('0.1'))}.get(item['number'])
        if names and names[0] in numeric and names[1] in numeric:
            a,b=numeric[names[0]],numeric[names[1]]
            aligned=all(a[k]==b[k] and a[k] is not None for k in ['unit','currency','scope','period_start','period_end'])
            denominator=Decimal(b['value'])
            if aligned and denominator>0:
                ratio=Decimal(a['value'])/denominator
                result['calculation']=dict(numerator=a['value'],denominator=b['value'],ratio=str(ratio),threshold=str(names[2]),
                    formula=names[0]+'/'+names[1],fact_version_ids=[a['version_id'],b['version_id']])
                if ratio>names[2]:
                    result.update(outcome='HIT',reason='宿主按同期间/单位/币种/范围的原JSON数值计算，已触发原经验阈值；并非全面风险背书',
                        coverage_outcome='PASS',verification='HOST_ARITHMETIC_THRESHOLD_HIT')
                elif result['outcome']=='UNKNOWN':
                    result['reason']='该数值阈值未触发，但本项目其他定性风险尚无完整依据；不擅自判CLEAR'
        share_names={23:['top5_customer_share'],24:['top5_supplier_share'],25:['largest_product_share','largest_region_share']}.get(item['number'])
        if share_names:
            observed=[]
            for name in share_names:
                fact=numeric.get(name)
                if fact and fact['scope'] and fact['unit'] in {'percent','ratio'}:
                    share=Decimal(fact['value'])/(100 if fact['unit']=='percent' else 1)
                    if 0<=share<=1:observed.append((fact,share))
            threshold=Decimal('0.7') if item['number']==25 else Decimal('0.5')
            if any(v>threshold for _,v in observed) or len(observed)==len(share_names):
                result.update(outcome='HIT' if any(v>threshold for _,v in observed) else 'CLEAR',coverage_outcome='PASS',
                    reason='宿主核对原值及比例单位后按原经验阈值判断集中风险；按披露/非评级，不改变估值与集团债务',
                    calculation=dict(shares=[dict(metric=f['metric'],share=str(v),fact_version_id=f['version_id']) for f,v in observed],threshold=str(threshold)),
                    verification='HOST_DISCLOSED_CONCENTRATION_THRESHOLD')
        if result['outcome']=='UNKNOWN' and row.get('review_method')=='DISCLOSURE_REVIEW' and row.get('disclosure_scope_reason') and row['candidate_outcome'] in {'CLEAR','HIT'}:
            text_facts=[f for f in verified if f['value_type']=='TEXT' and f['scope'] and f['period_start'] and f['period_end']]
            combined=' '.join(f['value']+' '+f['metric'] for f in verified).casefold()
            missing_topics=[terms for terms in TOPICS.get(item['number'],[[item['name']]]) if not any(word.casefold() in combined for word in terms)]
            years={int(f['period_end'][:4]) for f in verified}
            history_ok=len(years)>=HISTORY_YEARS.get(item['number'],1)
            if not missing_topics and history_ok and text_facts and len(verified)==len(selected) and len(row['reason'])>=20:
                result.update(outcome=row['candidate_outcome'],coverage_outcome='PASS',
                    reason='有确切原文和范围依据的派生研究判断（按披露）；宿主核对原件/引文/主体/期间/范围，不声称独立风险事实背书',
                    assessment_scope_reason=row['disclosure_scope_reason'],verification='EVIDENCE_BOUND_DERIVED_RESEARCH_ASSESSMENT_NOT_INDEPENDENT_AUDIT')
            else:
                result.update(missing_topic_groups=missing_topics,observed_reporting_years=sorted(years),required_reporting_years=HISTORY_YEARS.get(item['number'],1))
        result['evidence_sha256']=fingerprint(dict(facts=verified,candidate=row,result=result))
        unknown_refs=sorted(set(row['fact_version_ids'])-set(facts))
        if unknown_refs:
            result.update(outcome='UNKNOWN',coverage_outcome='UNKNOWN',reason='排雷底稿含固定快照外引用，未据此通过该项',unknown_reference_ids=unknown_refs)
        output.append(result)
    return output

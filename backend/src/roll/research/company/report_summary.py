"""Readable summaries from fixed core, accepted observations and actual series only."""
import re
from .report_template import cell,table
from .report_values import literal,unit_label
from .report_data import number,numeric_basis

PARTS={'1':['1','2','3'],'4':['4','5'],'6':['6','7'],'8':['8','9','10']}


def facts(payload):return {f['version_id']:f for f in [*payload['facts'],*payload['peer_facts']]}


def citations(identifiers,payload):
    selected=facts(payload)
    return ' '.join('[原件 '+cell(str(selected[i].get('page') or selected[i].get('table') or '坐标未知'))+'](/api/company-research/materials/'+selected[i]['material_id']+'/original)' for i in dict.fromkeys(identifiers) if i in selected)


def observations(candidate,packet,output_sha256,excluded=()):
    """Extract, never paraphrase, a bounded first sentence with its original paragraph refs."""
    selected=facts(packet['payload']);result=[]
    for index,para in enumerate(candidate['paragraphs']):
        if index in excluded or not para['fact_version_ids']:continue
        headings=re.findall(r'(?m)^\s*#{1,6}\s+(.+)$',para['text']);heading=headings[0] if headings else ''
        lines=[line.strip() for line in para['text'].splitlines() if line.strip() and not re.match(r'^\s*(?:#{1,6}\s|\|)',line)]
        if not lines:continue
        text=lines[0]
        for identifier in re.findall(r'\{\{fact:([^}]+)\}\}',text):
            fact=selected[identifier]
            value='未知' if fact['value'] is None else str(fact['value']) if fact['value_type']=='TEXT' else str(fact['value'])+' '+unit_label(fact,packet['payload']['materials'])
            text=text.replace('{{fact:'+identifier+'}}',value)
        match=re.search(r'[。！？]|(?<![0-9])[.!?](?:\s|$)',text)
        if match:text=text[:match.end()].strip()
        if not text or len(text)>1600:continue
        topic='FALSIFICATION' if re.search(r'最大证伪|最薄弱',heading) else 'ADVANTAGE' if re.search(r'优势|长处',heading) and not re.search(r'未知|缺口|不足|待核',heading+text) else 'RISK' if re.search(r'风险|反证|空头',heading) and not re.search(r'未知|缺口|未取得|未形成|待核实|待验证',heading+text) else 'OBSERVATION'
        result.append(dict(paragraph_index=index,text=text,heading=heading,topic=topic,fact_version_ids=para['fact_version_ids'],output_sha256=output_sha256,verification='REFERENCE_VALIDATED_CANDIDATE_NOT_INDEPENDENT_FACT_ENDORSEMENT'))
    return result


def accepted(sections):
    return {s['section_id']:(s,s.get('observations',[])) for s in sections if s['status']=='COMPLETE'}


def observed(row,payload):
    return cell(row['text'])+' '+citations(row['fact_version_ids'],payload)


def stock_coordinate(payload,sections):
    groups={name:[] for name in ['stock_price','eps','pe']}
    for chart in payload['charts']:
        metric=chart.get('metric',re.sub(r'_20\d\d$','',chart['title'].split(' / ')[0]))
        if metric in groups:groups[metric].append(chart)
    matches=[]
    for price in groups['stock_price']:
        for earnings in groups['eps']:
            years={r['period'][:4] for r in price['data']} & {r['period'][:4] for r in earnings['data']}
            if price['scope']==earnings['scope'] and price['currency']==earnings['currency'] and len(years)>=3:matches.append((price,earnings,years))
    rows=[]
    for name,charts in groups.items():
        for chart in charts:rows.append([name,min(r['period'] for r in chart['data']),max(r['period'] for r in chart['data']),chart['scope'],str(chart['unit'])+' / '+str(chart['currency']),','.join(chart['fact_version_ids'])])
    if matches:
        text='股价节奏坐标：已有同口径价格与盈利时序；原值、期间和来源如下。阶段和调整时长不由曲线存在自动推定。'
    elif rows:text='股价节奏坐标：已有部分价格或盈利时序；尚未形成同范围、同币种的可比配对，未判定反转、中继或见顶。'
    else:text='股价节奏坐标：尚无可用的同口径价格与盈利时序，未判定反转、中继或见顶。'
    if rows:text+='\n'+table(['固定序列','开始','截至','范围','原单位/币种','事实引用'],rows)
    section=accepted(sections).get('8')
    if matches and section and section[1]:text+='\n\n第八节研究观察：'+observed(section[1][0],payload)
    elif matches:text+='\n\n已有时序尚无可引用的第八节阶段结论；不能把数据存在当成阶段已核实。'
    return text


def core_model(payload):
    snapshot=payload['snapshot'];core=snapshot['core'] if snapshot else {};rows=[]
    selected=facts(payload)
    for claim in core.get('business_structure',[]):
        rows.append(['固定业务描述',claim['text'],'分部当年数与利润贡献未核定','不能据整体财务数推定分部贡献',','.join(claim['fact_version_ids'])])
    for h in core.get('hypotheses',[]):
        rows.append([h['business'],h['statement'],'研究假设，非披露财务数','跟踪：'+'；'.join(h['observation_metrics']),','.join(h['support_fact_version_ids'])])
    text=table(['业务/研究层次','固定内容','当年数及口径','报表作用/传导边界','固定引用'],rows) if rows else '尚无可发布的核心经营描述或假设。'
    # Segment contribution needs explicit same-basis financial observations, not six arbitrary company numbers.
    profit=[f for f in payload['facts'] if re.sub(r'_20\d\d$','',f['metric']) in {'segment_operating_profit','segment_profit'} and f['kind']=='DISCLOSED' and numeric_basis(f,payload['materials'])]
    compatible=bool(profit) and len({(f['unit'],f['currency'],f['scope'],f['period_start'],f['period_end']) for f in profit})==1
    if compatible:
        profit=sorted(profit,key=number,reverse=True)
        text+='\n\n同期间、同口径分部利润原值排序；未重新分摊成本：\n'+table(['业务','披露利润','期间/范围','事实'],[[f['business'],literal(f,payload['materials']),f['period_start']+'/'+f['period_end']+' / '+str(f['scope']),f['version_id']] for f in profit])
    else:text+='\n\n未形成有源分部利润贡献排序；以上整体描述与研究假设不能替代分部归因，缺口不以财务属性数字表补齐。'
    if not core.get('hypotheses'):text+='\n\n变量传导链尚无固定经营假设；第九节的估值研究条件不能替代经营贡献归因。'
    ids=[i for row in rows for i in row[-1].split(',') if i in selected]
    if ids:text+='\n\n'+citations(ids,payload)
    return text


def parts(payload,sections=()):
    core=payload['snapshot']['core'] if payload['snapshot'] else {};a=accepted(sections);result={}
    for start,sids in PARTS.items():
        rows=[]
        for sid in sids:
            source=a.get(sid)
            if source and source[1]:rows.append('第'+sid+'节结论摘录：'+observed(source[1][0],payload))
            elif sid=='1' and core.get('business_structure'):
                claim=core['business_structure'][0];rows.append(cell(claim['text'])+' '+citations(claim['fact_version_ids'],payload))
            elif sid=='3' and core.get('hypotheses'):
                rows.append('固定经营假设：'+'；'.join(cell(h['statement']) for h in core['hypotheses']))
            elif sid=='4':
                names={'industry_production':'产出','industry_consumption':'消费','industry_imports':'进口','industry_exports':'出口','industry_inventory':'库存','industry_price':'价格'}
                rows.append('固定资料的行业时序覆盖如下（覆盖年数不是行业产销数值）；不足的类别未形成阶段判断。\n'+table(['统计类别','同口径连续年数'],[[names[k],v] for k,v in payload['coverage']['industry_years'].items()]))
            elif sid=='5':rows.append('已绑定有数值依据的同业公司 '+str(payload['coverage']['peer_count'])+' 家，国际上市 '+str(payload['coverage']['international_peer_count'])+' 家；可比依据与边界见第五节及附录E。')
            elif sid=='7':rows.append('逐项排雷有据覆盖 '+str(sum(r['coverage_outcome']=='PASS' for r in payload['landmines']))+' 项；未知不当未命中，财务信息质量不自动变绿。')
            elif sid=='8':rows.append(stock_coordinate(payload,sections))
            elif sid=='9' and (payload['valuation_binding'].get('review') or {}).get('applicability')=='NOT_APPLICABLE':rows.append('固定经济审核认定本期FCFF方法不适用；保留公司研究与专用方法边界，不生成该方法的价格。')
            elif sid=='9':rows.append('固定当前用途 '+cell(payload['valuation_presentation']['status'])+'；历史基准用途 '+cell(payload['valuation_binding']['baseline']['status'])+'，均按各自条件理解。')
            else:rows.append('第'+sid+'节尚无可引用的有源结论；所需资料和验证条件保留为缺口。')
        result[start]='\n\n'.join(rows)+'\n\n以上研究观察按固定核心与注明条件理解；有源引用不等于独立事实背书。'
    return result


def overview(payload,sections=()):
    core=payload['snapshot']['core'] if payload['snapshot'] else {};a=accepted(sections);out=[]
    out.append('财务信息质量：UNKNOWN（独立质量核查尚未形成；已披露事项及逐项证据见第七节）。')
    if core.get('business_structure'):
        claim=core['business_structure'][0];out.append('一句话：'+cell(claim['text'])+' '+citations(claim['fact_version_ids'],payload))
    else:out.append('一句话：尚无固定、有原件依据的业务主线判断。')
    cycles=[o for sid,(_,rows) in a.items() if sid in {'1','4'} for o in rows if re.search(r'周期|供需|出清|资源约束',o['heading'])]
    out.append('周期坐标：'+observed(cycles[0],payload) if cycles else '周期坐标：'+('已识别周期暴露，尚无可引用的路线/阶段判断；不因省略周期词而排除周期要求。' if payload['cycle_required'] else '未据固定证据选定特定商品周期路线；不据此认定没有需求波动风险。'))
    out.extend(['## 核心经营模型',core_model(payload),table(['必须带走的问题','固定阅读位置'],[['靠什么赚钱及哪个变量决定','第一至三节'],['外部供需和竞争如何影响经营','第四至五节'],['哪些条件决定价值及何时失效','第六至十节']]),stock_coordinate(payload,sections)])
    for topic,title in [('ADVANTAGE','优势'),('RISK','风险')]:
        found=[];seen=set()
        for section,observations_ in a.values():
            for obs in observations_:
                key=tuple(sorted(obs['fact_version_ids']))
                if obs['topic']==topic and key not in seen:found.append(obs);seen.add(key)
        out.append('## '+title+'（有条件研究观察）')
        if found:out.extend(observed(obs,payload) for obs in found[:3])
        if len(found)<3:out.append('尚未形成三条各有来源的'+title+'判断；不以重复事实或资料缺口凑数。')
    out.append('## 最大证伪点与失效条件')
    specific=[o for _,rows in a.values() for o in rows if o['topic']=='FALSIFICATION']
    if specific:out.append(observed(specific[0],payload))
    else:out.append('最大证伪点尚无有源强弱排序；以下只列固定假设的失效条件，不把第一条自动认作最薄弱的一环。')
    for h in core.get('hypotheses',[]):
        out.append(cell(h['business'])+'：'+'；'.join(cell(s) for s in h['invalidation_conditions'])+' '+citations(h['support_fact_version_ids'],payload))
    company=payload['company'];out.append('## 公司档案卡')
    values=[['公司/代码',company['legal_name']+' / '+','.join(i['listing_id'] for i in company['listings'])],['上市地/注册地',','.join(i['exchange'] for i in company['listings'])+' / '+company['jurisdiction']],['会计准则/年结日',str(company['accounting_standard'])+' / '+str(company['year_end'])],['登记行业',company['industry']]]
    for label,metrics in [('上市时间',{'listing_date'}),('总股本',{'share_count','shares_total','total_shares'}),('市值（注明时点）',{'market_cap'}),('实控人',{'controlling_shareholder','ultimate_controller'}),('员工/人员结构',{'employees','staff_count','staff_structure'}),('经营性资产',{'operating_assets'}),('产能/技术原文',{'production_capacity','capacity_technology'}),('审计机构/事项',{'auditor','key_audit_matters'})]:
        rows=[f for f in payload['facts'] if re.sub(r'_20\d\d$','',f['metric']) in metrics and f['kind']=='DISCLOSED' and f['value'] is not None and f['business'] not in {'MACRO','EXTERNAL_VALUATION_INPUT'}]
        values.append([label,'；'.join(literal(f,payload['materials'])+' / '+f['period_end']+' / '+f['version_id'] for f in rows) if rows else '未纳入已核对固定事实；不使用近似值或外部参数补位'])
    out.extend([table(['档案项','登记/披露与缺口'],values),'## 尚未核实'])
    gaps=[*payload['source_gaps'],*core.get('limitations',[]),*payload['valuation_presentation'].get('current_pricing_gaps',[])]
    out.append(table(['缺口','影响','下一渠道及条件'],[[g,'相关结论须保留条件，不能推定经营未变','对应原始披露/统计与第十节；补齐同主体、期间和口径后形成新快照'] for g in gaps[:8]]) if gaps else '现有记录未列额外缺口；不等于已证明资料完整，章节/来源质量检查仍分别适用。')
    return '\n\n'.join(out)


def valuation_context(payload):
    """Display saved cells and supplied comparison sources; never execute a calculator."""
    binding=payload['valuation_binding'];sub=payload['valuation_subsections'];context=binding.get('fixed_result_context') or {};result=context.get('result') or {}
    current=payload['valuation_presentation'];baseline=binding['baseline'];review=binding.get('review') or {}
    if review.get('applicability')!='NOT_APPLICABLE':
        cells=result.get('sensitivity') or [];valid=[];invalid=[]
        from decimal import Decimal,InvalidOperation
        def finite(value):
            try:return value is not None and Decimal(str(value)).is_finite()
            except (InvalidOperation,ValueError,TypeError):return False
        for cell_ in cells:
            (valid if cell_.get('status')=='CONDITIONAL' and all(finite(cell_.get(k)) for k in ['wacc','terminal_g','per_share']) and not cell_.get('error') else invalid).append(cell_)
        lines=[]
        if result.get('scenarios') and baseline.get('usable_range'):
            lines.append('固定原结果的终值占企业价值比例（小数）：\n'+table(['情景','终值占比'],[[s['name'],s.get('terminal_share_of_ev')] for s in result['scenarios']]))
        if valid:
            lines.append('固定敏感性结果有 '+str(len(valid))+' 个有效单元、'+str(len(invalid))+' 个未适用/失败单元；未另算新网格。')
            if baseline.get('usable_range'):
                model=binding.get('fixed_operating_model') or {};meta=model.get('config',{}).get('metadata',{})
                lines.append('以下仅为原基准条件计算，不是当前可用价格或置信区间；每股值为原 '+str(meta.get('currency','币种未知'))+' 金额/股数配套尺度：\n'+table(['WACC（小数）','终值g（小数）','原每股条件值'],[[c['wacc'],c['terminal_g'],c['per_share']] for c in valid]))
            else:lines.append('原经济用途未具备可用条件，不展示诊断单价；单元状态不改变经济审核。')
        elif cells:lines.append('未形成有效敏感性网格；非空错误/NOT_APPLICABLE列表不能当成有效计算。')
        else:lines.append('敏感性网格未请求或未产生；没有用空记录补造网格。')
        if invalid:lines.append(table(['原单元状态','错误代码/原因'],[[c.get('status','UNKNOWN'),c.get('error',{})] for c in invalid]))
        sub['6']='\n\n'.join(lines)
        reverse=result.get('reverse')
        status='当前定价用途状态：'+current['status']+'；'+('有条件可用' if current.get('usable_range') else '不可用')+'。反推是否存在不改变该固定呈现。'
        if not reverse:sub['7']='固定输入未请求或未形成合格反向要求；未补造现价隐含值。'+status
        elif reverse.get('status')=='NOT_APPLICABLE' or reverse.get('error'):
            sub['7']='反向要求未适用/失败，按原记录保留：'+cell(reverse.get('error',reverse.get('status')))+'。'+status
        elif reverse.get('status') in {'conditional_terminal_requirement','no_positive_terminal_requirement'}:
            sub['7']='固定原结果的反向条件状态：'+cell(reverse['status'])+'；不是市场因果。'+status
            if baseline.get('usable_range'):
                sub['7']+='\n'+table(['原结果项目','固定值/口径'],[[k,v] for k,v in reverse.items()])
            else:sub['7']+='原经济用途不可用，不展示诊断反推数值；原文按附录J归档读取。'
        else:sub['7']='反向要求状态UNKNOWN，原结构未识别，不补成成功。'+status
    peers=payload['peers'];lines=[]
    if peers:
        lines.append('已绑定请求指定的同业资料；原币/财年各自列示，不构成独立估值验证。')
        lines.append(table(['公司/固定快照','提供的事实及口径','可比依据与局限'],[[p['company']['legal_name']+' / '+p['snapshot']['snapshot_id'],
            '; '.join(f['metric']+'='+literal(f,p['materials'])+' / '+f['period_end']+' / '+str(f['scope']) for f in p['facts']),
            p['comparison_basis'] or '尚无可比依据，仅为资料引用'] for p in peers]))
        for peer in peers:lines.append(citations([f['version_id'] for f in peer['facts']],payload))
    other=[f for f in payload['facts'] if f['metric'] in {'asset_value_crosscheck','historical_valuation_percentile'} and f['value'] is not None]
    if other:lines.append(table(['其他固定对照资料','原值及口径','引用'],[[f['metric'],literal(f,payload['materials'])+' / '+f['period_end']+' / '+str(f['scope']),f['version_id']] for f in other]));lines.append(citations([f['version_id'] for f in other],payload))
    if not peers and not other:lines.append('固定资料未绑定同业、资产或历史分位对照原件；外部比较缺口保留。')
    lines.append('尚未形成独立价值验证；同源现金流、同源EPV和经营同业表不自动成为独立估值证据。')
    sub['8']='\n\n'.join(lines)

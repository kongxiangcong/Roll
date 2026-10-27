"""Versioned report structure, bundled reference assets, and host-owned assembly."""
import hashlib
import json
import html
from pathlib import Path
from roll.accounts.ledger import encode
from .service import fingerprint
from .report_archive import archive

ROOT = Path(__file__).with_name('report_reference')
TEMPLATE_ID = 'roll-company-research-v1'
TEMPLATE_VERSION = '08.5'
SECTIONS = {
    '1': ('公司判定', '行业、盈利特征、定价权、周期位置。四层判定含观察视角，说明判据和反证。'),
    '2': ('业务与单位经济', '量价、产品地区结构、成本、最小单位经济、客户供应商账期、人效。禁止集团利润除局部产量；缺数据写具体缺口和条件。'),
    '3': ('核心经营变量', '引用固定的经营假设与版本；影响排序、同口径一阶敏感性、好中坏情景、跟踪指标、国际变量。缺敏感性依据禁止造数。'),
    '4': ('行业空间与周期', '上下两种市场空间、近五年产消进出口库存价格、供需时序和事件日历。过剩出清与资源约束分别有据判定；见顶和中继两侧写清。'),
    '5': ('竞争与产业链', '上下游应用占比与年份、同口径利润分配、国内国际可比公司、份额与稀缺性。榜单须核样本定义，不凭荣誉推护城河。'),
    '6': ('财务质量', '三表、杜邦、现金利润质量、营运资金、资本配置、关键资产、母公司与合并对照。披露事实、推算、假设分开；正常化与利息口径固定引用。'),
    '7': ('风险排雷', '依据冻结清单逐项有据检查，A股二十八项，港股及A+H三十八项；未知不得填未命中。财务信息质量未知须明示。'),
    '8': ('历史股价复盘', '中长线上下行对称、利润侧每股收益与估值侧市盈率拆解、调整起止结束信号、公司和行业时长对照。不做日周因果，不把事后资料写成当时先行。'),
    '9': ('估值口径、条件估值与现价要求', '只解释宿主固定九个子节的适用方法、事实正常化、年度经营FCFF、折现率权益桥、情景、敏感性终值、反向要求、交叉参照、经济审核缺口。禁止另算价格或改核心。'),
    '10': ('判断边界与后续验证', '支持与反证、多空对照、证伪条件、下一验证；缺口列已试路径、下一具体渠道、需要条件。另列非空未答问题表：问题、重要性、受影响结论、查找处。'),
    'REVIEW': ('投资人视角复核', '逐条结论、证据与反证，至少六百中文字和三行表；仅候选观察视角，不是独立人工审计或自签通过。'),
    'CHALLENGE': ('反向质疑', '至少五百中文字；分别写前提、死因、激励、空头四表，保留无法作答和取证渠道，禁止橡皮图章。'),
}
DISCLAIMER = ('本报告基于公开信息整理，用于帮助理解该公司及其所处行业，**不构成任何投资建议**，'
    '也不提供买入、卖出或目标价判断。报告中的分析框架与事实判断仅供研究参考，投资者应自行核实并独立决策，据此操作风险自担。'
    '报告不保证所引信息的完整性与时效性；标注“待核实”的内容尤需进一步验证。')
VALUATION_SECTIONS = ['方法适用性', '事实与正常化口径', '年度经营与FCFF预测', '折现率与权益桥接',
    '情景估值', '敏感性与终值依赖', '反向现价要求', '适用交叉参照', '经济审核与缺口']
APPENDICES = {'A': '沿革与资本事件', 'B': '股权与治理', 'C': '产能技术渠道人员', 'D': '逐项排雷',
    'E': '可比公司', 'F': '图表索引', 'G': '关键数字与原件', 'H': '术语与首次解释', 'I': '免责声明',
    'J': '估值输入、模型与审核', 'K': '版本与任务引用索引'}
RUNTIME_FILES=['research/company/report_summary.py','research/company/report_coverage.py','research/company/report_revisions.py','research/company/report_values.py','research/company/reports.py','research/company/report_runtime.py','research/company/report_template.py',
    'research/company/report_quality.py','research/company/report_sources.py','research/company/report_data.py',
    'research/company/report_quotes.py','research/company/report_quote_worker.py','agents/company_report_runtime.py',
    'research/company/report_workpapers.py',
    'research/company/report_archive.py','research/company/report_integrity.py',
    'agents/codex_process.py','agents/codex_worker.py']


def code_hashes():
    root=Path(__file__).parents[2]
    return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in RUNTIME_FILES}


def cell(value):
    if value is None:return '未知'
    if isinstance(value,(dict,list)):
        value=encode(value)
    value=html.escape(str(value)).replace('|','\\|').replace('\n',' ')
    for token in ['`','[',']','!','#']:
        value=value.replace(token,'\\'+token)
    return value


def table(headers,rows):
    return '\n'.join(['|'+'|'.join(headers)+'|','|'+'|'.join('---' for _ in headers)+'|']+
        ['|'+'|'.join(cell(v) for v in row)+'|' for row in rows])


def valuation_summary(value):
    lines=[table(['用途','经济状态','可用价格区间'],[[value.get('purpose','CURRENT_PRICING'),value['status'],'有条件可用' if value.get('usable_range') else '不可用']])]
    if value.get('usable_range'):
        lines.append(table(['情景','企业价值','归母权益价值','每股条件值','终值占比'],[
            [s['name'],s.get('enterprise_value'),s.get('equity_value'),s.get('per_share'),s.get('terminal_share_of_ev')] for s in value.get('scenarios',[])]))
    else:
        lines.append('不展示诊断价格：'+cell(value.get('reason') or '；'.join(value.get('current_pricing_gaps',[]) or value.get('limitations',[])) or '原固定审核未达到本用途条件'))
    return '\n\n'.join(lines)


def template_bundle(evidence):
    manifest = json.loads((ROOT/'manifest.json').read_text(encoding='utf-8-sig'))
    assets = []
    for item in manifest:
        raw = (ROOT/item['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('TEMPLATE_ASSET_CORRUPT')
        assets.append(dict(**item, archive=archive(evidence,raw, 'REPORT_TEMPLATE_REFERENCE')))
    mapping = (ROOT/'gate-rule-map.json').read_bytes()
    return dict(template_id=TEMPLATE_ID, version=TEMPLATE_VERSION, assets=assets,
        manifest_sha256=hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest(),
        gate_map_sha256=hashlib.sha256(mapping).hexdigest(),
        gate_map_archive=archive(evidence,mapping, 'REPORT_GATE_MAP'), structure_sha256=fingerprint(SECTIONS))


def reference_text(section_id):
    names = ['02-问题链与报告结构.md']
    extra = {'1': '01-公司类型判定与模块装配.md', '7': '04-排雷清单.md', '8': '13-历史股价复盘.md',
             '9': '15-基本面估值计算与接入.md', 'REVIEW': '10-投资人视角复核.md', 'CHALLENGE': '11-反向质疑与遗漏排查.md'}
    if section_id in extra:
        names.append(extra[section_id])
    return {name: (ROOT/'references'/name).read_text(encoding='utf-8-sig') for name in names}


def source_reference(fact, material,role='SUBJECT_COMPANY'):
    upstream=material.get('upstream') or {}
    external=fact['business'] in {'EXTERNAL_VALUATION_INPUT','MACRO'}
    source_role='EXTERNAL_VALUATION_INPUT' if external else upstream.get('source_role','REGISTERED_SOURCE_ROLE_UNVERIFIED')
    source_subject=upstream.get('source_subject') if external else upstream.get('source_subject',material['subject_name'])
    return dict(fact_version_id=fact['version_id'], material_id=material['material_id'], source_url=material['source_url'],
        raw_sha256=material['raw_sha256'], page=fact.get('page'), table=fact.get('table'),
        coordinate_kind='ORIGINAL_PDF_PAGE_OR_TABLE' if material['media_type']=='application/pdf' else 'ORIGINAL_JSON_OR_TEXT_COORDINATE',
        original_api='/api/company-research/materials/'+material['material_id']+'/original',
        metric=fact['metric'], value=fact['value'], unit=fact['unit'], currency=fact['currency'], scope=fact['scope'],
        period_start=fact['period_start'], period_end=fact['period_end'], kind=fact['kind'],company_id=fact['company_id'],business=fact['business'],
        source_subject=source_subject,declared_subject_name=material['subject_name'],
        role='EXTERNAL_CONTEXT' if external else role, source_role=source_role)


def assemble(packet, sections, job_id):
    """Model prose is separate from immutable shared results and arithmetic."""
    payload = packet['payload']
    snapshot, company = payload['snapshot'], payload['company']
    by_id = {s['section_id']: s for s in sections}
    from .report_coverage import build,appendix,glossary
    source_book=payload.get('source_coverage') or build(payload)
    from .report_summary import overview,parts
    out = ['# '+cell(company['legal_name'])+' 深度研究与条件估值', DISCLAIMER, '# 速览',overview(payload,sections)]
    part_summaries=parts(payload,sections)
    if snapshot:
        for reason in [*snapshot['core']['business_structure'],*snapshot['core']['attention_reasons']]:
            out.append(cell(reason['text']))
        out.append('以上经营结论绑定与每日研究相同的共享核心；完整引用版本见附录K。')
        from .report_values import company_attributes,unit_label
        numbers=company_attributes(payload)
        if numbers:
            out.extend(['## 已披露公司属性数字（不含反推临界值）',table(['指标','披露值','单位/币种','期间/范围'],[
                [f['metric'],f['value'],unit_label(f,payload['materials']),f['period_end']+' / '+str(f['scope'])] for f in numbers])])
    else:
        out.append('尚无可发布共享经营快照；章节只保留已取得证据及未完成项。')
    presentation = payload['valuation_presentation']
    out.extend(['## 当前定价用途',valuation_summary(presentation)])
    for sid in [str(i) for i in range(1, 11)]:
        if sid in {'1','4','6','8'}:
            part, title = {'1': ('一','生意模式'), '4': ('二','外部条件'), '6': ('三','财务与风险'), '8': ('四','尺子与边界')}[sid]
            out.extend(['# 第'+part+'部分 '+title, part_summaries[sid]])
        out.append('## '+sid+'. '+SECTIONS[sid][0])
        if sid == '9':
            for number, title in enumerate(VALUATION_SECTIONS, 1):
                out.extend(['### 9.'+str(number)+' '+title, payload['valuation_subsections'][str(number)]])
        section = by_id.get(sid)
        out.append(section['rendered'] if section else '本章未完成；未取得有效章节候选。')
        if sid=='7':
            from collections import Counter
            counts=Counter(i['outcome'] for i in payload['landmines'])
            out.append('排雷结果按研究底稿与披露范围理解，不是财务绿灯或资格。'+table(['状态','项目数'],list(counts.items())))
            known=[i for i in payload['landmines'] if i['outcome']!='UNKNOWN']
            if known:
                out.append(table(['项目','按披露研究判断','依据与边界'],[[i['name'],i['outcome'],i.get('candidate_reason',i['reason'])] for i in known]))
        for index,chart in enumerate(payload['charts'],1):
            if chart['section_id']==sid:
                out.append('![图 '+sid+'-'+str(index)+' '+chart['title']+'](/api/company-research/report-charts/'+chart['chart_id']+')')
    for key, title in APPENDICES.items():
        out.append('# 附录 '+key+' '+title)
        if key == 'I':
            out.append(DISCLAIMER)
        elif key in {'A','B','C'}:
            out.append(appendix(source_book,key))
        elif key == 'H':
            out.append(glossary('\n\n'.join(out),source_book)['markdown'])
        elif key == 'D':
            out.extend(['|序号|检查项|结论|依据与缺口|','|---|---|---|---|'])
            out.extend('|'+str(item['number'])+'|'+item['name']+'|'+item['outcome']+'|'+cell(item['reason'])+'；'+cell(item.get('candidate_reason',''))+'；'+cell(item.get('assessment_scope_reason',''))+'；'+','.join(item['fact_version_ids'])+'|' for item in payload['landmines'])
        elif key == 'G':
            out.extend(['|关键数字/事实版本|值与单位/币种/范围/期间|原件坐标|来源|', '|---|---|---|---|'])
            for ref in payload['references']:
                out.append('|'+cell(ref['metric']+' / '+ref['fact_version_id']+' / '+source_book['fact_source_roles'].get(ref['fact_version_id'],'PEER_COMPANY' if ref['role'] in {'PEER','PEER_COMPANY'} else 'SOURCE_ROLE_UNVERIFIED'))+'|'+cell(str(ref['value'])+' '+str(ref['unit'])+' / '+str(ref['currency'])+' / '+str(ref['scope'])+' / '+ref['period_end'])+'|'+cell(str(ref['page'])+' / '+str(ref['table'])+' / '+ref['coordinate_kind'])+'|['+ref['raw_sha256'][:12]+']('+ref['original_api']+')|')
        elif key == 'F' and payload['charts']:
            out.extend(['|编号|标题|正文位置|来源与数据|','|---|---|---|---|'])
            out.extend('|'+str(index)+'|'+chart['title']+'|第'+chart['section_id']+'节|'+','.join(chart['fact_version_ids'])+'|' for index,chart in enumerate(payload['charts'],1))
        elif key == 'E' and payload['peers']:
            out.append(table(['公司','证券/市场','财年/币种','实际披露指标','可比依据与限制'],[
                [p['company']['legal_name'],','.join(i['listing_id'] for i in p['company']['listings']),
                 ','.join(sorted({f['period_end']+' '+str(f['currency']) for f in p['facts']})),
                 '; '.join(f['metric']+'='+str(f['value'])+' '+str(f['unit']) for f in p['facts']),
                 p['comparison_basis'] or '尚无同口径可比依据，不能直接作估值对照'] for p in payload['peers']]))
        elif key == 'J':
            binding=payload['valuation_binding']
            out.append('固定估值输入和原始审计工件按版本读取；当前用途不可用时不把诊断价格作为可用区间。年度路径及正常化见第九节。')
            links=[['冻结报告输入',packet['input_id'],packet['packet_sha256'],'/api/company-research/report-inputs/'+packet['input_id']]]
            if binding.get('review'):
                review=binding['review'];model=binding['fixed_operating_model']
                links.extend([['经营驱动模型',model['operating_model_id'],model['content_sha256'],'/api/company-research/operating-models/'+model['operating_model_id']],
                    ['经济审核',review['review_id'],review['content_sha256'],'/api/company-research/economic-reviews/'+review['review_id']]])
                calculation=binding.get('fixed_calculation_reference')
                if calculation:
                    links.append(['计算结果',calculation['valuation_id'],calculation['content_sha256'],'/api/company-research/valuations/'+calculation['valuation_id']])
                out.append(table(['输入路径','来源种类','单位/币种','范围/期间','事实或假设引用'],[
                    [path,p.get('kind'),str(p.get('unit'))+' / '+str(p.get('currency')),str(p.get('scope'))+' / '+str(p.get('period')),','.join(p.get('references',[]))]
                    for path,p in model['provenance'].items()]))
                out.append(table(['研究假设','说明与限制'],[[a.get('assumption_id',a.get('id','假设')),a.get('reason',a.get('description',a.get('statement','完整内容见冻结输入')))] for a in model['assumptions']]))
            out.append('|工件|版本|SHA-256|读取入口|\n|---|---|---|---|\n'+'\n'.join('|'+cell(kind)+'|'+cell(identifier)+'|'+cell(digest)+'|[固定原文]('+url+')|' for kind,identifier,digest,url in links))
        elif key == 'K':
            if packet.get('host_revision'):
                revision=packet['host_revision']
                out.append(table(['追加修订','固定版本'],[['revision_id',revision['revision_id']],['host version',revision['host_version']],['compiler',revision['compiler_version']],['original plan SHA',revision['original_plan_sha256']],['source generation hashes',revision['generation_code_hashes']],['actual execution/validator hashes',revision['execution_code_hashes']]]))
                out.append('原输出逐字保留；以下为降级隔离记录，不是模型自签事实背书。'+table(['原输出SHA','位置/事实','原因','缺少依据'],[[f['output_sha256'],f['section_id']+'/'+f['location']+'/'+str(f['index'])+' / '+','.join(f['fact_version_ids']),f['reason'],f['missing_basis']] for f in revision['findings']]))
            out.append('来源类别账本（本次尝试/明确历史取得/仅引用归档分别记录）：\n\n'+source_book['ledger_markdown'])
            out.append(table(['对象','固定版本/摘要'],[
                ['公司',company['company_id']],['证券',','.join(i['listing_id'] for i in company['listings'])],
                ['共享快照',snapshot['snapshot_id'] if snapshot else None],['共享核心SHA-256',payload['core_sha256']],
                ['经营假设版本',','.join(snapshot['hypothesis_version_ids']) if snapshot else None],
                ['报告版本',packet['report_id']],['生成任务',job_id],['报告输入',packet['input_id']],['输入SHA-256',packet['packet_sha256']],
                ['模板',packet['template']['template_id']+' / '+packet['template']['version']],
                ['模板manifestSHA-256',packet['template']['manifest_sha256']],['规则映射SHA-256',packet['template']['gate_map_sha256']],
                ['模型固定ID',packet['model']],['知识冻结',payload['knowledge_frozen_at']],['请求报告截止',payload['request_cutoff']],
                ['报告估值用途',payload.get('valuation_purpose','CURRENT_PRICING')],
                ['原件实际取得上限',payload['actually_obtained_through']],['尚未纳入核心的已取得原件',','.join(payload['unincorporated_material_ids'])]]))
        else:
            out.append('尚未取得足够有据资料，未填充占位数据或无来源图表；缺口见第十节。')
    return '\n\n'.join(out)+'\n'

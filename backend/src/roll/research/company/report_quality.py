"""Run the pinned mechanical checks plus conservative host evidence checks.

Only the bundled, hash-verified Python reference is compiled. Neither original
materials nor model output is ever evaluated as code. Its CLI is never called.
"""
import ast
import hashlib
import inspect
import json
from pathlib import Path
import re
import tempfile

from .report_template import ROOT, SECTIONS

SOURCE_HASH = '7434fedc06fdc94b39c9f17b38887a07592f2a7bdfa046c989471d898d1fadcb'


def economic_coverage(payload):
    binding=payload['valuation_binding'];review=binding.get('review')
    if review and review['applicability']=='NOT_APPLICABLE':
        model=binding.get('fixed_operating_model',{})
        app=model.get('economic_basis',{}).get('applicability',{})
        valid=(review.get('policy_version')=='economic-review-2' and review['valuation_id'] is None and
            app.get('category')=='FINANCIAL' and bool(app.get('reason')) and bool(app.get('references')) and not model.get('cashflows'))
        return valid,'有效方法不适用按固定宿主审核核查，未执行FCFF、无价格；不把N/A当缺当前价格，也不升级blocked审核。'
    purpose=payload.get('valuation_purpose','CURRENT_PRICING')
    selected=binding['baseline'] if purpose=='BASELINE_RESEARCH' else binding['current']
    return bool(selected.get('usable_range')),('明确用途 '+purpose+' 按固定review安全呈现；基准条件研究非PIT，当前blocked仍不显示当前可用价格。')


def check_quality(packet, sections, markdown, scratch_root=None):
    source = (ROOT/'scripts'/'check_gates.py').read_bytes()
    if hashlib.sha256(source).hexdigest()!=SOURCE_HASH:
        raise ValueError('REFERENCE_GATE_CORRUPT')
    tree = ast.parse(source)
    rules = json.loads((ROOT/'gate-rule-map.json').read_text(encoding='utf-8-sig'))
    ancestors = {}
    def walk(node, branch=()):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='add':
            ancestors[node.lineno]=branch
        if isinstance(node,ast.If):
            for child in node.body:
                walk(child,branch+((node.lineno,True,ast.unparse(node.test)),))
            for child in node.orelse:
                walk(child,branch+((node.lineno,False,ast.unparse(node.test)),))
            return
        for child in ast.iter_child_nodes(node):
            walk(child,branch)
    walk(tree)
    conditions = {}
    class Trace(ast.NodeTransformer):
        def visit_If(self,node):
            self.generic_visit(node)
            node.test=ast.copy_location(ast.Call(func=ast.Name(id='_trace_condition',ctx=ast.Load()),
                args=[ast.Constant(node.lineno),node.test],keywords=[]),node.test)
            return node
    def trace_condition(line,value):
        conditions[line]=bool(value)
        return value
    namespace={'__name__':'roll_bundled_report_gates','__file__':str(ROOT/'scripts'/'check_gates.py'), '_trace_condition':trace_condition}
    exec(compile(ast.fix_missing_locations(Trace().visit(tree)),str(ROOT/'scripts'/'check_gates.py'),'exec'),namespace)
    executed={}
    class Recorder:
        def add(self,gate,name,ok,detail='',level='fail'):
            line=inspect.currentframe().f_back.f_lineno
            executed[line]=dict(name=name, mechanical_outcome='PASS' if ok else 'FAIL', outcome='PASS' if ok else 'FAIL',
                evidence=[detail],reason='冻结参考表达式的实际机械结果；不代表事实核实')
    payload=packet['payload']
    complete={s['section_id']:s for s in sections if s['status']=='COMPLETE'}
    from .report_coverage import build
    source_book=payload.get('source_coverage') or build(payload)
    ledger=source_book['ledger_markdown']
    with tempfile.TemporaryDirectory(prefix='roll-report-quality-', dir=scratch_root) as directory:
        project=Path(directory)
        wd=project/'02-工作底稿';wd.mkdir()
        for sid,name in [('1','四层判定表'),('8','历史股价复盘'),('REVIEW','投资人视角复核'),('CHALLENGE','反向质疑')]:
            if sid in complete:
                (wd/(name+'.md')).write_text(complete[sid]['rendered'],encoding='utf-8')
        # UNKNOWN rows are retained for the reader, but do not count as completed screening.
        (wd/'排雷表.md').write_text('\n'.join('|'+str(i['number'])+'|'+i['name']+'|'+i['outcome']+'|' for i in payload['landmines']),encoding='utf-8')
        (wd/'估值参照带.md').write_text(json.dumps(payload['valuation_presentation'],ensure_ascii=False),encoding='utf-8')
        count=len(re.findall(r'[\u4e00-\u9fff]',markdown))
        selfcheck='\n'.join(['中文字 '+str(count),('字数不足：取数/有效章节尚未全部完成；不是认定公司本来信息少。' if count<namespace['DRAFT_MIN_CJK'] else '字数达到原触发线；来源、经济与语义覆盖仍须分别检查。')]+
            ['章节 '+sid+'：'+('有受限候选，仍需核对事实' if sid in complete else '未完成有效候选') for sid in SECTIONS]+
            ['来源数据图数 '+str(len(payload['charts']))+'；未造图凑数','未知排雷项 '+str(sum(i['outcome']=='UNKNOWN' for i in payload['landmines']))])
        (wd/'成稿自检记录.md').write_text(selfcheck,encoding='utf-8')
        recorder=Recorder()
        namespace['check_gate1'](recorder,project,ledger)
        namespace['check_gate2'](recorder,project,payload['market'],None,markdown)
        namespace['check_gate3'](recorder,project,markdown)
    originals={m['origin_root_id'] for m in payload['materials'] if m['source_kind']!='METHOD_CASE'}
    # The original filesystem extension heuristic is replaced by source records.
    for line,ok,reason in [(378,len(originals)>=5,'按独立原件根计数，排除模板、派生工件、METHOD与缓存副本；实际 '+str(len(originals))),
                           (383,True,'所有输入原件均引用共享材料档案；派生章节和提取内容不计原件')]:
        executed[line].update(outcome='PASS' if ok else 'FAIL',evidence=[reason],reason='Roll原件档案适配；保留原规则等级')
    for line in [443,447]:
        if line in executed:
            unknown=sum(i['coverage_outcome']!='PASS' for i in payload['landmines'])
            executed[line].update(outcome='UNKNOWN' if unknown else 'PASS',reason='逐项宿主/原披露依据核查；UNKNOWN行不计实质完成，HIT并不影响报告覆盖完成',evidence=['未知排雷项 '+str(unknown),payload['screening_archive']])
    portable={960:('PASS','宿主路径相对于包定位；章节无任意文件读写'),962:('PASS','使用项目声明的Python依赖与既有CODEX探测'),
        972:('PASS','没有注册或执行参考SKILL及其他skill'),977:('NOT_APPLICABLE','Roll应用不发布skill，frontmatter不适用'),
        978:('PASS','Roll公开报告API文档定义环境、边界与复现'),979:('PASS','缺证据/模型不可用明确PARTIAL并保留错误与冻结输入'),
        980:('PASS','本次实际调用报告宿主check_quality入口并逐条登记')}
    results=[]
    for rule in rules:
        line=rule['source_line']
        result=dict(rule_id=rule['rule_id'],source_hash=SOURCE_HASH,source_line=line,source_gate=rule['source_gate'],
            source_name_expression=rule['source_name_expression'],severity=rule['source_severity'],applies=True)
        if line in portable:
            outcome,reason=portable[line]
            result.update(outcome=outcome,applies=outcome!='NOT_APPLICABLE',evidence=[reason],reason=reason)
        elif line in executed:
            result.update(executed[line])
        else:
            path=ancestors.get(line,())
            contrary=[(n,expected,expression) for n,expected,expression in path if n in conditions and conditions[n]!=expected]
            if contrary:
                n,expected,expression=contrary[0]
                result.update(outcome='NOT_APPLICABLE',applies=False,evidence=[dict(if_line=n,expression=expression,actual=conditions[n])],
                    reason='实际条件选择另一分支；本调用点未执行，不记PASS')
            else:
                result.update(outcome='UNKNOWN',evidence=[dict(if_line=n,expression=expression) for n,_,expression in path],
                    reason='依赖材料或前置分支未完成，本调用点未实际执行；不得记PASS')
        results.append(result)
    if payload['cycle_required']:
        for item in results:
            if item['source_line'] in {541,600,619} and item['outcome']=='NOT_APPLICABLE':
                item.update(applies=True,outcome='UNKNOWN',reason='冻结经营事实/经济模型已识别周期暴露；不能靠省略周期词或缺失历史数据排除本项',
                    evidence=[*item['evidence'],dict(classification_fact_version_ids=payload['classification_fact_version_ids'])])
    host=[]
    def check(name,ok,reason):
        host.append(dict(rule_id='roll-'+name,severity='fail',applies=True,outcome='PASS' if ok else 'UNKNOWN',evidence=[reason],reason=reason))
    check('sourceful-appendices',all(state=='PASS' for state in source_book['appendices'].values()),'A/B/C原文主题覆盖 '+str(source_book['appendices'])+'；无已绑定逐字证据不填完整')
    check('shared-core',payload['snapshot'] is not None,'固定snapshot/core，章节不能回写或另算')
    check('requested-source-and-analysis',payload['acquisition']['status'] not in {'FAILED','PARTIAL'} and not payload['pipeline_errors'],
        '请求来源状态 '+payload['acquisition']['status']+'；分析/引文/底稿阶段错误 '+str(payload['pipeline_errors'])+'；失败不刷新成功或旧观点核查时间')
    check('chapters',all(s in complete for s in SECTIONS),'十章及投资人/质疑候选分别有实际受限生成记录；失败章逐项保留')
    check('structure',all('## '+str(i)+'. ' in markdown for i in range(1,11)) and all('### 9.'+str(i)+' ' in markdown for i in range(1,10))
          and all('# 附录 '+x in markdown for x in 'ABCDEFGHIJK'),'速览、四部分十节、估值九子节、附录A–K由宿主组装')
    check('numeric-original-coordinates',all(r['page'] or r['table'] for r in payload['references']), '数值只允许固定事实占位注入；页和JSON/表坐标区分，页码未知不伪造')
    from .report_values import unit_label
    check('literal-unit-evidence',all('未知' not in unit_label(f,payload['materials']) for f in payload['facts'] if f['value_type']=='NUMBER'),
        '数值单位/尺度必须由固定字段或原件单位证据支持；未知不能由币种猜尺度')
    economic_ok,economic_reason=economic_coverage(payload)
    check('economic-use',economic_ok,economic_reason)
    coverage=payload['coverage']
    check('industry-history',coverage['industry_complete'],'原件事实覆盖年数：'+str(coverage['industry_years'])+'；近五年产消进出口库存价格缺项保留UNKNOWN')
    check('peer-basis',coverage['peer_complete'],'有来源且披露口径同业 '+str(coverage['peer_count'])+'、国际上市 '+str(coverage['international_peer_count'])+'；未完成不能以候选名凑数')
    check('real-charts',coverage['chart_count']>=8 and {'3','4','6','8'}<=set(coverage['chart_sections']),'实际生成同口径来源时序图 '+str(coverage['chart_count'])+'；分布 '+str(coverage['chart_sections']))
    check('economic-and-factual-substance',coverage['industry_complete'] and coverage['peer_complete'] and
        economic_ok and all(s.get('reference_ids') for s in complete.values()),
        '经济用途、行业时序、同业对照和每个有效章节来源分别核查；文字与机械通过不构成独立事实审计')
    return dict(reference_rules=results,host_rules=host,completeness='FULL' if all(r['outcome']=='PASS' for r in [*results,*host] if r['applies'] and r['severity']=='fail') else 'PARTIAL',
        self_check=selfcheck,scope='MECHANICAL_AND_HOST_REFERENCE_CHECKS_NOT_INDEPENDENT_FACTUAL_AUDIT')

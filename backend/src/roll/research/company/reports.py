"""Company report checkpoints. The shared snapshot remains the only core authority."""
import json
import os
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4,uuid5,NAMESPACE_URL

from pydantic import Field
from roll.accounts.ledger import encode, now
from .models import Command
from .service import fail, fingerprint, record, verified, page_bounds
from .report_sources import ReportSource
from .report_quotes import ReportQuote
from .report_workpapers import RiskWorkpaperRow
from .report_archive import archive as archived


class ReportCancellation:
    def __init__(self,reports,job_id,outer=None):
        self.reports,self.job_id,self.outer=reports,job_id,outer

    def is_set(self):
        return bool((self.outer and self.outer.is_set()) or self.reports.get(self.job_id)['cancel_requested_at'])


class ReportCommand(Command):
    company_id: str
    snapshot_id: str | None = None
    as_of: str
    source_mode: Literal['REUSE', 'REFRESH'] = 'REFRESH'
    valuation_purpose: Literal['CURRENT_PRICING','BASELINE_RESEARCH'] = 'CURRENT_PRICING'
    idempotency_key: str = Field(min_length=1, max_length=128)
    parent_report_id: str | None = None
    parent_job_id: str | None = None
    additional_material_ids: list[str] = Field(default_factory=list,max_length=40)
    sources: list[ReportSource] = Field(default_factory=list,max_length=4)
    peer_snapshot_ids: list[str] = Field(default_factory=list,max_length=10)
    peer_comparison_basis: dict[str,str] = Field(default_factory=dict,max_length=10)
    source_quotes: list[ReportQuote] = Field(default_factory=list,max_length=12)
    risk_workpaper: list[RiskWorkpaperRow] = Field(default_factory=list,max_length=38)


class ReportState:
    def __init__(self, research):
        self.research = research
        self.worker = None
        self.collectors=[]
        with research.transaction() as db:
            for table, key in [('jobs', 'job_id'), ('report_inputs', 'input_id'),
                               ('report_sections', 'section_version_id'), ('reports', 'report_id'),
                               ('report_runs', 'run_id'), ('report_revisions','revision_id')]:
                db.execute(f'CREATE TABLE IF NOT EXISTS company_research_{table}({key} TEXT PRIMARY KEY, company_id TEXT NOT NULL, value TEXT NOT NULL)')
            from roll.agents.codex_process import owner_alive, recover_directory
            for raw, in db.execute("SELECT value FROM company_research_report_runs WHERE json_extract(value,'$.status')='RUNNING'").fetchall():
                run=verified(json.loads(raw))
                if not owner_alive(run):
                    run.update(status='INTERRUPTED',finished_at=now(),error=dict(code='HOST_INTERRUPTED'))
                    if run.get('process',{}).get('task_root'):
                        run['recovery_cleanup']=recover_directory(run)
                    run=record({k:v for k,v in run.items() if k!='content_sha256'})
                    db.execute('UPDATE company_research_report_runs SET value=? WHERE run_id=?',(encode(run),run['run_id']))
            for raw, in db.execute("SELECT value FROM company_research_jobs WHERE json_extract(value,'$.status')='RUNNING'").fetchall():
                job=verified(json.loads(raw))
                if not owner_alive(job):
                    job.update(status='INTERRUPTED',error=dict(code='HOST_INTERRUPTED',stage=job['stage']))
                    job=record({k:v for k,v in job.items() if k!='content_sha256'})
                    db.execute('UPDATE company_research_jobs SET value=? WHERE job_id=?',(encode(job),job['job_id']))

    def get(self, job_id):
        return self.research.analysis.read('jobs', 'job_id', job_id)

    def save(self, value):
        value = record({k: v for k, v in value.items() if k != 'content_sha256'})
        with self.research.transaction() as db:
            db.execute('UPDATE company_research_jobs SET value=? WHERE job_id=?', (encode(value), value['job_id']))
        return value

    def start(self, command):
        company = self.research.company(command.company_id)
        request=command.model_dump()
        # Optional version-lineage fields added in08.2 do not invalidate08.1 keys.
        if request['parent_job_id'] is None:request.pop('parent_job_id')
        if not request['additional_material_ids']:request.pop('additional_material_ids')
        if request['valuation_purpose']=='CURRENT_PRICING':request.pop('valuation_purpose')
        with self.research.ledger.connection() as db:
            prior=db.execute("SELECT value FROM company_research_jobs WHERE company_id=? AND json_extract(value,'$.idempotency_key')=?",(command.company_id,command.idempotency_key)).fetchone()
        if prior:
            saved=verified(json.loads(prior[0]))
            if saved['request_sha256']!=fingerprint(request):
                fail('IDEMPOTENCY_CONFLICT','Report key already identifies different input',409)
            return saved
        try:
            cutoff = datetime.fromisoformat(command.as_of)
            if cutoff.tzinfo is None or cutoff > datetime.now(timezone.utc):
                raise ValueError()
        except ValueError:
            fail('INVALID_AS_OF', 'Report cutoff must be a timezone-aware past timestamp')
        snapshot = self.research.analysis_snapshot(command.snapshot_id, 'REPORT') if command.snapshot_id else None
        if not snapshot and command.source_mode=='REUSE':
            with self.research.ledger.connection() as db:
                snapshot=self.research.analysis.latest(command.company_id,db)
        if snapshot and snapshot['company_id'] != company['company_id']:
            fail('CROSS_COMPANY_REFERENCE', 'Report snapshot belongs to another company')
        from .report_sources import validate_periods
        if snapshot:
            validate_periods([self.research.fact(i,company['company_id']) for i in snapshot['fact_version_ids']],
                [self.research.material(i,company['company_id']) for i in snapshot['material_ids']],command.as_of)
        for peer_id in command.peer_snapshot_ids:
            peer=self.research.analysis_snapshot(peer_id,'REPORT')
            if peer['company_id']==company['company_id']:
                fail('INVALID_PEER_REFERENCE','Peer must have its own company snapshot')
            validate_periods([self.research.fact(i,peer['company_id']) for i in peer['fact_version_ids']],
                [self.research.material(i,peer['company_id']) for i in peer['material_ids']],command.as_of)
        if not set(command.peer_comparison_basis)<=set(command.peer_snapshot_ids) or any(not 20<=len(s)<=2000 for s in command.peer_comparison_basis.values()):
            fail('PEER_BASIS_INVALID','Peer comparison needs bounded explicit scope differences, not an unbound basis')
        if command.parent_report_id:
            parent = self.read(command.parent_report_id)
            if parent['company_id'] != command.company_id:
                fail('CROSS_COMPANY_REFERENCE', 'Report parent belongs to another company')
        if command.parent_job_id and self.get(command.parent_job_id)['company_id']!=command.company_id:
            fail('CROSS_COMPANY_REFERENCE','Report parent job belongs to another company')
        if command.additional_material_ids:
            validate_periods([], [self.research.material(i,command.company_id) for i in command.additional_material_ids],command.as_of)
        from .report_template import ROOT, TEMPLATE_ID, TEMPLATE_VERSION
        import hashlib
        template_binding=dict(template_id=TEMPLATE_ID,version=TEMPLATE_VERSION,
            manifest_sha256=hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest(),
            gate_map_sha256=hashlib.sha256((ROOT/'gate-rule-map.json').read_bytes()).hexdigest())
        from .report_sources import validate_source
        for source in command.sources:
            validate_source(source, command.company_id, command.as_of)
        for quote in command.source_quotes:
            if quote.material_id:
                self.research.material(quote.material_id,command.company_id)
            elif quote.source_index>=len(command.sources):
                fail('SOURCE_QUOTE_ORIGINAL_MISSING','Quote index must identify an explicitly bound source')
        if len({r.number for r in command.risk_workpaper})!=len(command.risk_workpaper):
            fail('SCREENING_ITEM_DUPLICATED','Each risk workpaper item must have one unambiguous candidate row')
        need=38 if any(i['exchange']=='HKEX' for i in company['listings']) else 28
        if any(row.number>need for row in command.risk_workpaper):
            fail('SCREENING_ITEM_OUTSIDE_MARKET','Screening rows must match the frozen company listing scope')
        with self.research.transaction() as db:
            prior = db.execute("SELECT value FROM company_research_jobs WHERE company_id=? AND json_extract(value,'$.idempotency_key')=?", (command.company_id, command.idempotency_key)).fetchone()
            if prior:
                saved = verified(json.loads(prior[0]))
                if saved['request_sha256'] != fingerprint(request):
                    fail('IDEMPOTENCY_CONFLICT', 'Report key already identifies different input', 409)
                return saved
            pending = db.execute("SELECT count(*) FROM company_research_jobs WHERE json_extract(value,'$.status') IN ('QUEUED','RUNNING')").fetchone()[0]
            if pending >= 16:
                fail('QUEUE_FULL', 'Report queue has sixteen outstanding requests', 409)
            job = record(dict(**{**request,'snapshot_id':snapshot['snapshot_id'] if snapshot else None}, job_id=str(uuid4()), workflow='REPORT', request_sha256=fingerprint(request),
                request_cutoff=command.as_of, requested_at=now(), model=os.environ.get('ROLL_CODEX_MODEL', 'gpt-6.1-sol'),
                stage='ACQUISITION', status='QUEUED', attempts=0, checkpoints=[], errors=[],
                section_ids=[], report_id=None, input_id=None, host_owner=None, cancel_requested_at=None,
                historical_pit_eligible=False,template_binding=template_binding))
            self.research.analysis.insert(db, 'jobs', 'job_id', job)
        return job

    def list(self,company_id,limit=50,offset=0):
        self.research.company(company_id)
        page_bounds(limit,offset,200)
        with self.research.ledger.connection() as db:
            count=db.execute('SELECT count(*) FROM company_research_reports WHERE company_id=?',(company_id,)).fetchone()[0]
            identifiers=[r[0] for r in db.execute('SELECT report_id FROM company_research_reports WHERE company_id=? ORDER BY rowid DESC LIMIT ? OFFSET ?',(company_id,limit,offset))]
        return dict(reports=[self.read(i) for i in identifiers],total=count,limit=limit,offset=offset,has_more=offset+limit<count)

    def cancel(self,job_id):
        with self.research.transaction() as db:
            row=db.execute('SELECT value FROM company_research_jobs WHERE job_id=?',(job_id,)).fetchone()
            if not row:
                fail('REPORT_JOB_NOT_FOUND','Report job is not registered',404)
            job=verified(json.loads(row[0]))
            if job['report_id'] or job['status']=='CANCELLED':
                return job
            running=job['status']=='RUNNING'
            job.update(cancel_requested_at=now(),status='RUNNING' if running else 'CANCELLED')
            job=record({k:v for k,v in job.items() if k!='content_sha256'})
            db.execute('UPDATE company_research_jobs SET value=? WHERE job_id=?',(encode(job),job_id))
        return job

    def retry(self,job_id):
        from roll.agents.codex_process import owner_alive
        job=self.get(job_id)
        if job['report_id'] or job['status']=='QUEUED':
            return job
        if job['status']=='RUNNING' and owner_alive(job):
            fail('REPORT_ALREADY_RUNNING','A live report phase cannot be retried concurrently',409)
        if job['attempts']>=3:
            fail('REPORT_RETRY_LIMIT','Three explicit retries exhausted; create a new version with its parent',409)
        job.update(status='QUEUED',attempts=job['attempts']+1,cancel_requested_at=None,host_owner=None)
        job['checkpoints'].append(dict(stage='EXPLICIT_RETRY',at=now(),attempt=job['attempts']))
        return self.save(job)

    def work(self,owner,stop=None):
        """Called only by Reviews after validating its existing live singleton lease."""
        from roll.agents.codex_process import owner_alive
        with self.research.ledger.connection() as db:
            lease=db.execute('SELECT value FROM review_worker WHERE slot=1').fetchone()
            if not lease or json.loads(lease[0])['host_owner']!=owner or not owner_alive({'host_owner':owner}):
                fail('LEASE_LOST','Report work requires the shared Reviews live lease',409)
            rows=[verified(json.loads(r[0])) for r in db.execute("SELECT value FROM company_research_jobs WHERE json_extract(value,'$.status')='QUEUED'")]
        if not rows or (stop and stop.is_set()):
            return None
        # Least recently advanced first: long reports do not monopolize other reports.
        selected=min(rows,key=lambda j:j.get('last_advanced_at',j['created_at']))
        return self.advance(selected['job_id'],stop,owner)

    def read(self, report_id):
        result = self.research.analysis.read('reports', 'report_id', report_id)
        packet=self.input(result['input_id'])
        snapshot=packet['payload']['snapshot']
        if result['company_id']!=packet['company_id'] or result['snapshot_id']!=(snapshot['snapshot_id'] if snapshot else None) or result['core']!=(snapshot['core'] if snapshot else None):
            fail('RESEARCH_REFERENCE_INVALID','Published report differs from its frozen shared core',409)
        if result.get('host_revision_id'):
            revision=self.revision(result['host_revision_id'])
            if revision['input_id']!=result['input_id'] or revision['input_sha256']!=result['input_sha256'] or result['host_revision_archive']['sha256']!=fingerprint(revision):
                fail('RESEARCH_REFERENCE_INVALID','Report host revision is inconsistent',409)
        self.research.evidence.raw(result['markdown_archive']['sha256'])
        return result

    def markdown(self, report_id):
        return self.research.evidence.raw(self.read(report_id)['markdown_archive']['sha256']).read_text(encoding='utf-8')

    def input(self, identifier):
        value=self.research.analysis.read('report_inputs', 'input_id', identifier)
        wire=self.research.evidence.raw(value['input_archive']['sha256']).read_bytes()
        if json.loads(wire)!=value['payload'] or fingerprint(value['payload'])!=value['packet_sha256']:
            fail('ARTIFACT_CORRUPT','Frozen report payload differs from its archived input',409)
        return value

    def sections(self, job):
        return [self.research.analysis.read('report_sections', 'section_version_id', i) for i in job['section_ids']]

    def revise(self,command):
        from .report_revisions import ReportRevisions
        return ReportRevisions(self).start(command)

    def revision(self,identifier):
        from .report_revisions import ReportRevisions
        return ReportRevisions(self).get(identifier)

    def chapter_preview(self,job_id,section_id):
        from .report_runtime import ReportRuntime
        import hashlib
        job=self.get(job_id)
        if not job['input_id']:
            fail('REPORT_INPUT_NOT_FROZEN','Chapter preview requires the fixed report input',409)
        packet=self.input(job['input_id']);command=ReportRuntime(self).command(job,packet,section_id)
        return dict(job_id=job_id,input_id=packet['input_id'],input_sha256=packet['packet_sha256'],section_id=section_id,
            command_sha256=hashlib.sha256(encode(command).encode()).hexdigest(),command=command,network_calls=0,model_calls=0)

    def freeze(self, job):
        from .report_template import ROOT, template_bundle, source_reference, code_hashes, table, valuation_summary, cell
        import re
        with self.research.ledger.connection() as db:
            prior=db.execute("SELECT value FROM company_research_report_inputs WHERE json_extract(value,'$.job_id')=? ORDER BY rowid LIMIT 1",(job['job_id'],)).fetchone()
        if prior:
            return self.input(verified(json.loads(prior[0]))['input_id'])
        snapshot = self.research.analysis_snapshot(job['snapshot_id'], 'REPORT') if job['snapshot_id'] else None
        company = self.research.company(job['company_id'])
        facts = [self.research.fact(i, job['company_id']) for i in snapshot['fact_version_ids']] if snapshot else []
        material_ids = [f['material_id'] for f in facts]+job.get('additional_material_ids',[])+[r['material_id'] for r in job.get('acquisition',{}).get('receipts',[]) if r.get('material_id')]
        materials = [self.research.material(i, job['company_id']) for i in dict.fromkeys(material_ids)]
        from .report_sources import validate_periods
        validate_periods(facts,materials,job['request_cutoff'])
        by_material = {m['material_id']: m for m in materials}
        references = [source_reference(f, by_material[f['material_id']]) for f in facts]
        peers=[];peer_facts=[]
        for peer_id in dict.fromkeys(job['peer_snapshot_ids']):
            peer_snapshot=self.research.analysis_snapshot(peer_id,'REPORT')
            peer_company=self.research.company(peer_snapshot['company_id'])
            selected=[self.research.fact(i,peer_company['company_id']) for i in peer_snapshot['fact_version_ids']]
            if len(peer_facts)+len(selected)>80:
                fail('REPORT_PEER_INPUT_TOO_LARGE','Peer facts exceed the separate eighty-fact bound')
            peer_facts.extend(selected)
            peer_materials={f['material_id']:self.research.material(f['material_id'],peer_company['company_id']) for f in selected}
            references.extend(source_reference(f,peer_materials[f['material_id']],role='PEER') for f in selected)
            peers.append(dict(snapshot=peer_snapshot,company=peer_company,facts=selected,materials=list(peer_materials.values()),
                comparison_basis=job['peer_comparison_basis'].get(peer_id),
                limitation='原币/财年/产品结构各自列示；没有独立同口径转换依据时不直接比较或混算'))
        reviews = snapshot.get('economic_review_ids', []) if snapshot else []
        missing = dict(status='UNAVAILABLE', usable_range=False, scenarios=[], reason='固定快照无唯一可用经济审核；未读取独立latest估值')
        presentation = self.research.valuation_presentation(reviews[0], 'CURRENT_PRICING') if len(reviews)==1 else missing
        baseline = self.research.valuation_presentation(reviews[0], 'BASELINE_RESEARCH') if len(reviews)==1 else missing
        binding = dict(snapshot_id=job['snapshot_id'], economic_review_ids=reviews,
            valuation_ids=snapshot.get('valuation_ids', []) if snapshot else [], current=presentation,
            baseline=baseline, historical_pit_eligible=False,
            limitation='BASELINE_RESEARCH仅条件研究；材料当前取得，不表示历史时点已可得。当前用途独立按冻结审核安全呈现。')
        landmine_text = (ROOT/'references'/'04-排雷清单.md').read_text(encoding='utf-8-sig')
        need = 38 if any(i['exchange']=='HKEX' for i in company['listings']) else 28
        landmines = [dict(number=int(m[0]), name=m[1]) for m in re.findall(r'^\|\s*(\d+)\s*\|\s*\*\*([^*]+)\*\*', landmine_text, re.M) if int(m[0])<=need]
        from .report_workpapers import build_screening
        landmines=build_screening(self.research,company,landmines,facts,[])
        completed={r['result']['number']:r['result'] for r in job.get('risk_receipts',[])}
        landmines=[completed.get(item['number'],item) for item in landmines]
        screening_archive=archived(self.research.evidence,encode(landmines).encode(),'REPORT_DERIVED_SCREENING_WORKPAPER')
        sub = {str(i): '未取得足够同口径依据；本项UNKNOWN，不补造计算或经济判断。' for i in range(1,10)}
        sub['1'] = '仅消费固定快照已有方法与审核。银行保险等专用模型未实现时保留方法缺口；不强套现金流模型。'
        sub['5'] = valuation_summary(presentation)
        sub['9'] = '固定快照无唯一经济审核。未形成可用条件区间，继续保留经营研究。'
        if len(reviews)==1:
            review = self.research.economic_review(reviews[0])
            binding['review'] = review
            model=self.research.operating_model(review['operating_model_id'])
            fixed_request=model['request']
            binding['fixed_operating_model']=dict(operating_model_id=model['operating_model_id'],
                content_sha256=model['content_sha256'],algorithm_archive=model['algorithm_archive'],
                normalization_schedule=model['normalization_schedule'],cashflows=model['cashflows'],
                config=fixed_request['config'],drivers=fixed_request['drivers'],
                economic_basis=fixed_request['economic_basis'],provenance=fixed_request['provenance'],
                assumptions=fixed_request['assumptions'])
            sub['1']='固定审核方法适用性为 '+str(review['applicability'])+'；研究条件与限制：\n'+table(['限制'],[[s] for s in fixed_request['economic_basis']['limitations']])
            sub['2']='固定正常化调整，原件引用、公式和版本见附录J；不由章节另算。\n'+table(
                ['调整项','目标口径','调整前','调整后','差额','依据'],[[r['adjustment_id'],r['target'],r['before'],r['after'],r['delta'],r['reason']] for r in model['normalization_schedule']])
            sub['3']='固定年度经营与现金流路径（研究假设，不是披露或收益预测）；金额单位、范围沿用附录J固定输入。\n'+table(
                ['情景','期间','收入','经营利润','税','税后经营利润','折旧','维持投资','增长投资','营运资金变化','企业自由现金流'],
                [[s['name'],y['period'],y['revenue'],y['operating_profit'],y['tax'],y['nopat'],y['normalized_inputs']['depreciation'],
                    y['normalized_inputs']['maintenance_capex'],y['normalized_inputs']['growth_capex'],y['normalized_inputs']['delta_working_capital'],y['fcff']]
                    for s in model['cashflows'] for y in s['years']])
            wacc=fixed_request['economic_basis']['wacc'];config=fixed_request['config']
            sub['4']='折现率及权益桥仅引用原受控输入；没有把现金、债务、少数股东再次桥接。\n'+table(['项目','固定值'],[
                *[[k,wacc.get(k)] for k in ['as_of','currency','risk_free','beta','equity_risk_premium','cost_of_debt','tax_rate','equity_weight','debt_weight','tax_shield_reason']],
                ['WACC',config.get('wacc')],['g',config.get('terminal_g')],['稀释股数',config.get('shares')]])+'\n\n'+table(
                    ['桥接项','金额','说明'],[[i.get('name',i.get('id','桥接项')),i.get('amount'),i.get('reason','逐项来源见附录J')] for i in config.get('equity_bridge',[])])
            sub['5']='当前定价用途：\n'+valuation_summary(presentation)+'\n\n历史财务基准条件研究（非历史PIT，非当前可用价格或置信区间）：\n'+valuation_summary(baseline)
            raw=self.research.valuation(review['valuation_id']) if review['valuation_id'] else None
            if raw:
                binding['fixed_result_context']=dict(result=raw['result'],valuation_id=raw['valuation_id'],valuation_sha256=raw['content_sha256'],result_archive=raw['result_archive'])
                binding['fixed_calculation_reference']=dict(valuation_id=raw['valuation_id'],content_sha256=raw['content_sha256'],
                    input_sha256=raw['input_sha256'],result_archive=raw['result_archive'],algorithm=raw['algorithm'])
            if raw and baseline.get('usable_range'):
                result=raw['result']
                sub['6']='固定计算结果中的终值依赖；超过四分之三触发复核提示，不等于自动无效。没有重算新敏感性。\n'+table(['情景','终值占企业价值比例'],[[s['name'],s['terminal_share_of_ev']] for s in result['scenarios']])
                sub['6']+='\n\n'+'敏感性状态与有效单元按原结果逐项核查；不以列表非空当作成功。'
                sub['7']='固定前期现金流路径的反向要求，仅在原件同口径价格/各股类股数/汇率满足时有效，不是市场因果。\n'+(
                    table(['项目','固定结果'],list(result['reverse'].items())) if result.get('reverse') else '原固定输入未请求或未形成合格反向条件；当前经济用途按独立固定呈现判断。')
            sub['8']='外部对照按已绑定同行/资产/历史资料分别呈现，不从同源EPV推定独立验证。'
            from collections import Counter
            checks=Counter(c.get('status','UNKNOWN') for c in review['checks'])
            sub['9']='固定经济审核 '+cell(review['status'])+'；逐项检查及原件依据见附录J。计算成功不等于收益或正式资格。\n'+table(['检查结论','项数'],list(checks.items()))+'\n\n'+valuation_summary(presentation)
            if review['applicability']=='NOT_APPLICABLE':
                sub['1']='固定经济审核确认本期FCFF/WACC执行器不适用：'+cell(fixed_request['economic_basis']['applicability']['reason'])+'。保留公司研究与专用方法/资料缺口，不强套现金流模型。'
                for number in range(2,9):
                    sub[str(number)]='本期FCFF/WACC执行器不适用；未执行或呈现该计算。专用模型尚未实现，方法与资料限制保留，不生成价格、年度现金流或概率。'
        template = template_bundle(self.research.evidence)
        if any(template[k]!=v for k,v in job['template_binding'].items()):
            fail('INPUT_CHANGED','Template changed since report request; create a new version',409)
        from .report_data import prepare_data
        data=prepare_data(self.research.evidence,facts,materials)
        from .economics import classification_sources
        classification=classification_sources(facts)
        if len(reviews)==1:
            classification=list({f['version_id']:f for f in [*classification,*model.get('classification_context',[])]}.values())
        text=' '.join(str(f['value']) for f in classification).casefold()
        cycle_required=any(word in text for word in ['lme','commodity','mining','铜价','铜周期','tc/rc','采矿','大宗商品']) or (
            len(reviews)==1 and fixed_request['economic_basis']['applicability']['category'] in {'CYCLICAL','CYCLICAL_GROUP'})
        from .report_data import qualified_peer
        qualified={}
        for peer in peers:
            if qualified_peer(peer):qualified.setdefault(peer['company']['company_id'],peer)
        intl=sum(any(i['exchange']=='HKEX' for i in p['company']['listings']) or p['company']['jurisdiction']!='CN' for p in qualified.values())
        data['coverage'].update(peer_count=len(qualified),international_peer_count=intl,
            peer_complete=len(qualified)>=5 and intl>=2 and all(p['comparison_basis'] for p in qualified.values()))
        payload = dict(company=company, snapshot=snapshot, core_sha256=snapshot['core_sha256'] if snapshot else None,
            facts=facts, materials=materials, references=references, peers=peers,peer_facts=peer_facts,landmines=landmines, market='HK' if need==38 else 'A',
            request_cutoff=job['request_cutoff'], material_report_cutoff=job['request_cutoff'],parent_job_id=job.get('parent_job_id'),
            actually_obtained_through=max((m['received_at'] for m in materials), default=None), knowledge_frozen_at=now(),
            historical_pit_eligible=False, cutoff_meaning='请求资料/价格报告截止独立于实际取得/知识冻结；不得回填历史可得性',
            valuation_presentation=presentation, valuation_binding=binding, valuation_subsections=sub, part_conclusions={},
            valuation_purpose=job.get('valuation_purpose','CURRENT_PRICING'),
            acquisition=job.get('acquisition'), source_gaps=[*job.get('source_gaps', []),*[str(e) for e in job['errors']]],pipeline_errors=job['errors'],**data,
            cycle_required=cycle_required,classification_fact_version_ids=[f['version_id'] for f in classification],
            screening_archive=screening_archive,
            unincorporated_material_ids=[m['material_id'] for m in materials if m['material_id'] not in {f['material_id'] for f in facts}])
        from .report_summary import parts
        payload['part_conclusions']=parts(payload)
        from .report_coverage import capture
        payload['source_coverage']=capture(self.research,job,payload)
        from .report_values import typed_packet
        payload=typed_packet(dict(payload=payload))['payload']
        archive = archived(self.research.evidence,encode(payload).encode(), 'REPORT_FROZEN_INPUT')
        from pathlib import Path
        hashes=code_hashes();code_root=Path(__file__).parents[2]
        algorithm_archives={name:archived(self.research.evidence,(code_root/name).read_bytes(),'REPORT_HOST_ALGORITHM_SOURCE') for name in hashes}
        packet = record(dict(input_id=str(uuid4()), company_id=job['company_id'], job_id=job['job_id'],
            payload=payload, packet_sha256=fingerprint(payload), input_archive=archive, template=template, model=job['model'],code_hashes=hashes,algorithm_archives=algorithm_archives,
            report_id=str(uuid5(NAMESPACE_URL,'roll-company-report:'+job['job_id']))))
        import sys
        from importlib.metadata import version
        packet=record({k:v for k,v in packet.items() if k!='content_sha256'} | dict(runtime_versions={name:version(name) for name in ['pypdf','jsonschema','openai-codex']},python_version=sys.version.split()[0]))
        with self.research.transaction() as db:
            self.research.analysis.insert(db, 'report_inputs', 'input_id', packet)
        return packet

    def advance(self, job_id, cancel=None,lease_owner=None):
        """Exactly one finite phase or chapter. The caller yields to daily work afterwards."""
        from roll.agents.codex_process import process_creation, owner_alive
        from .report_template import SECTIONS, assemble
        with self.research.transaction() as db:
            row=db.execute('SELECT value FROM company_research_jobs WHERE job_id=?',(job_id,)).fetchone()
            if not row:
                fail('REPORT_JOB_NOT_FOUND','Report job is not registered',404)
            job=verified(json.loads(row[0]))
            if job['status'] in {'COMPLETE','PARTIAL','CANCELLED','FAILED','INTERRUPTED'}:
                return job
            if job['status']=='RUNNING':
                fail('REPORT_ALREADY_RUNNING', 'An existing phase must finish or recover before retry', 409)
            job.update(status='RUNNING', host_owner={'pid': os.getpid(), 'creation_ticks': process_creation(os.getpid())}, phase_started_at=now())
            if lease_owner:
                job['worker_lease_owner']=lease_owner
            job=record({k:v for k,v in job.items() if k!='content_sha256'})
            db.execute('UPDATE company_research_jobs SET value=? WHERE job_id=?',(encode(job),job_id))
        cancel=ReportCancellation(self,job_id,cancel)
        stage = job['stage']
        try:
            if stage=='ACQUISITION':
                if job['source_mode']=='REUSE':
                    job['acquisition'] = dict(status='NOT_REQUESTED', network_check_performed=False, reason='显式REUSE已有资料')
                    job['stage']='SOURCE_QUOTES' if job['source_quotes'] else 'SHARED_FACTS'
                else:
                    from .report_sources import acquire
                    acquisition=job.setdefault('acquisition',dict(receipts=[],network_check_performed=False,status='RUNNING'))
                    index=len(acquisition['receipts'])
                    total=len(job['sources']) if job['sources'] else len(self.collectors)
                    if index<len(job['sources']):
                        receipt=acquire(self.research,job,ReportSource(**job['sources'][index]),index)
                        acquisition['receipts'].append(receipt)
                        acquisition['network_check_performed'] |= receipt['network_check_performed']
                    elif not job['sources'] and index<len(self.collectors):
                        import asyncio
                        collector=self.collectors[index]
                        company=self.research.company(job['company_id'])
                        instrument=next((i['listing_id'] for i in company['listings'] if i['share_class']=='A'),company['listings'][0]['listing_id'])
                        receipt=dict(source=collector['source_id'],started_at=now(),network_check_performed=False,status='FAILED')
                        try:
                            command=collector['command'](idempotency_key='report:'+job_id+':provider:'+str(index),basis='公司完整报告有界来源补充；不承诺研究完整或历史可得')
                            async def collect():
                                return await asyncio.wait_for(collector['service'].collect(instrument,command),timeout=20)
                            run=asyncio.run(collect())
                            receipt.update(run_id=run['run_id'],status='SUCCESS' if run['status'] in {'COMPLETE','EMPTY'} else 'PARTIAL' if run['status']=='PARTIAL' else 'FAILED',
                                source_status=run['status'],network_check_performed=run.get('network_calls',0)>0,evidence_kind=run['evidence_kind'])
                        except Exception as error:
                            receipt['error']=dict(code='ACQUISITION_TIMEOUT' if isinstance(error,TimeoutError) else 'SOURCE_UNAVAILABLE',type=type(error).__name__)
                        receipt['finished_at']=now()
                        acquisition['receipts'].append(receipt)
                        acquisition['network_check_performed'] |= receipt['network_check_performed']
                    if len(acquisition['receipts'])==total:
                        good=sum(r['status']=='SUCCESS' for r in acquisition['receipts'])
                        acquisition['status']='SUCCESS' if good and good==total else 'PARTIAL' if good else 'FAILED'
                        if not total:
                            job.setdefault('source_gaps',[]).append('NO_REGISTERED_PRIMARY_DOCUMENTS; 未配置具体发行人来源，未扫描全市场')
                        job['stage']='SOURCE_QUOTES' if job['source_quotes'] else 'SHARED_FACTS'
            elif stage=='SOURCE_QUOTES':
                from .report_quotes import verify_quote
                receipts=job.setdefault('quote_receipts',[])
                index=len(receipts)
                quote=ReportQuote(**job['source_quotes'][index])
                try:
                    receipt=verify_quote(self.research,job,quote,index)
                except Exception as error:
                    code=error.detail.get('code') if hasattr(error,'detail') and isinstance(error.detail,dict) else 'SOURCE_QUOTE_TIMEOUT' if isinstance(error,TimeoutError) else 'SOURCE_QUOTE_UNAVAILABLE'
                    receipt=record(dict(index=index,status='FAILED',error=dict(code=code,type=type(error).__name__),finished_at=now()))
                    job['errors'].append(dict(stage=stage,code=code,index=index))
                receipts.append(receipt)
                if len(receipts)==len(job['source_quotes']):
                    job['stage']='SHARED_FACTS'
            elif stage=='SHARED_FACTS':
                if (job['source_mode']=='REFRESH' or job.get('quote_receipts')) and not job['snapshot_id']:
                    shared=self.research.refresh_daily(job['company_id'],'report:'+job['job_id'])
                    job['shared_update']=shared
                    job['analysis_input_id']=shared['analysis_input_id']
                    if job['analysis_input_id']:
                        from .report_sources import validate_periods
                        packet=self.research.analysis_input(job['analysis_input_id'])
                        validate_periods(packet['payload']['facts'],packet['payload']['materials'],job['request_cutoff'])
                    if shared.get('gap'):
                        job.setdefault('source_gaps',[]).append(shared['gap'])
                    if shared['snapshot_id']:
                        job['snapshot_id']=shared['snapshot_id']
                elif job['snapshot_id']:
                    job.setdefault('source_gaps',[]).append('PINNED_SHARED_CORE; 新取得但无结构化依据的材料不修改固定核心，后续新任务才能纳入分析')
                job['stage']='ANALYSIS'
            elif stage=='ANALYSIS':
                if job.get('analysis_input_id'):
                    from .model_runtime import AnalysisRuntime
                    runtime=AnalysisRuntime(self.research)
                    run=runtime.execute(job['analysis_input_id'],cancel,90,job['model'])
                    job['analysis_run_id']=run['run_id']
                    if run['status'] in {'COMPLETE','PARTIAL'} and run.get('snapshot_id'):
                        accepted=self.research.analysis_snapshot(run['snapshot_id'])
                        if accepted['company_id']!=job['company_id'] or accepted['input_id']!=job['analysis_input_id']:
                            fail('INPUT_CHANGED','Published shared snapshot differs from fixed report analysis input',409)
                        job['snapshot_id']=accepted['snapshot_id']
                    if run['status']!='COMPLETE':
                        job['errors'].append(dict(stage='ANALYSIS',code=run['status']))
                job['stage']='WORKPAPERS' if job['risk_workpaper'] else 'VALUATION'
            elif stage=='WORKPAPERS':
                from .report_workpapers import build_screening
                from .report_template import ROOT
                import re
                receipts=job.setdefault('risk_receipts',[])
                index=len(receipts);row=job['risk_workpaper'][index]
                definitions=(ROOT/'references'/'04-排雷清单.md').read_text(encoding='utf-8-sig')
                item=next(dict(number=int(n),name=name) for n,name in re.findall(r'^\|\s*(\d+)\s*\|\s*\*\*([^*]+)\*\*',definitions,re.M) if int(n)==row['number'])
                snapshot=self.research.analysis_snapshot(job['snapshot_id']) if job['snapshot_id'] else None
                facts=[self.research.fact(i,job['company_id']) for i in snapshot['fact_version_ids']] if snapshot else []
                result=build_screening(self.research,self.research.company(job['company_id']),[item],facts,[row])[0]
                archive=archived(self.research.evidence,encode(result).encode(),'REPORT_DERIVED_SCREENING_ROW')
                receipts.append(record(dict(index=index,result=result,archive=archive)))
                if len(receipts)==len(job['risk_workpaper']):job['stage']='VALUATION'
            elif stage=='VALUATION':
                packet = self.freeze(job)
                job.update(input_id=packet['input_id'], stage='CHAPTERS')
            elif stage=='CHAPTERS':
                packet = self.input(job['input_id'])
                done = {s['section_id'] for s in self.sections(job)}
                sid = next((s for s in SECTIONS if s not in done), None)
                if sid:
                    from .report_runtime import ReportRuntime
                    section = ReportRuntime(self).execute(job, packet, sid, cancel)
                    job['section_ids'].append(section['section_version_id'])
                    if section['status']!='COMPLETE':
                        job['errors'].append(dict(stage='CHAPTERS', section_id=sid,
                            code='MODEL_TIMEOUT' if section['status']=='TIMED_OUT' else 'MODEL_UNAVAILABLE' if section['status']=='UNAVAILABLE' else section['status']))
                if len(job['section_ids'])==len(SECTIONS):
                    job['stage']='QUALITY'
            elif stage=='QUALITY':
                from .report_quality import check_quality
                packet = self.input(job['input_id'])
                sections = self.sections(job)
                if job.get('host_revision_id'):
                    from .report_revisions import ReportRevisions
                    packet=ReportRevisions(self).presentation_packet(job,packet)
                markdown = assemble(packet, sections, job['job_id'])
                job['quality'] = check_quality(packet, sections, markdown, self.research.evidence.directory)
                if job.get('host_revision_id') and packet['host_revision']['findings']:
                    job['quality']['host_rules'].append(dict(rule_id='semantic-quarantine',severity='fail',applies=True,outcome='UNKNOWN',reason='Retained raw model statements were quarantined; no factual endorsement',evidence=packet['host_revision']['findings']))
                    job['quality']['completeness']='PARTIAL'
                job['markdown_archive'] = archived(self.research.evidence,markdown.encode(), 'COMPANY_REPORT_MARKDOWN')
                job['stage']='PUBLISH'
            elif stage=='PUBLISH':
                current = self.get(job_id)
                if current['cancel_requested_at'] or (cancel and cancel.is_set()):
                    job.update(status='CANCELLED', cancel_requested_at=now())
                    return self.save(job)
                packet = self.input(job['input_id'])
                with self.research.transaction() as db:
                    if job.get('worker_lease_owner'):
                        lease=db.execute('SELECT value FROM review_worker WHERE slot=1').fetchone()
                        if not lease or json.loads(lease[0])['host_owner']!=job['worker_lease_owner']:
                            fail('LEASE_LOST','Shared worker lease changed before report publication',409)
                    existing = db.execute("SELECT value FROM company_research_reports WHERE json_extract(value,'$.job_id')=?", (job_id,)).fetchone()
                    if existing:
                        report = verified(json.loads(existing[0]))
                    else:
                        report = record(dict(report_id=str(uuid5(NAMESPACE_URL,'roll-company-report:'+job_id)) if job.get('host_revision_id') else packet['report_id'], company_id=job['company_id'], job_id=job_id,
                            parent_report_id=job['parent_report_id'],parent_job_id=job.get('parent_job_id'),snapshot_id=job['snapshot_id'], input_id=job['input_id'],
                            input_sha256=packet['packet_sha256'], core=packet['payload']['snapshot']['core'] if packet['payload']['snapshot'] else None,
                            core_sha256=packet['payload']['core_sha256'], quality=job['quality'],
                            completeness=job['quality']['completeness'], section_ids=job['section_ids'], model=job['model'], template=packet['template'],
                            valuation_purpose=packet['payload'].get('valuation_purpose','CURRENT_PRICING'),
                            markdown_archive=job['markdown_archive'], delivery_status='MARKDOWN_ONLY_PDF_NOT_REQUESTED', published_at=now(),
                            historical_pit_eligible=False, formal_authority=False))
                        kinds={s['evidence_kind'] for s in self.sections(job)}
                        report=record({k:v for k,v in report.items() if k!='content_sha256'} | dict(
                            evidence_kind='METHOD_CASE' if 'METHOD_CASE' in kinds else 'REAL_MODEL_REPORT' if kinds=={'REAL_MODEL_CHAPTER'} else 'PARTIAL_MODEL_EXECUTION',
                            host_revision_id=job.get('host_revision_id'),host_revision_archive=job.get('host_revision_archive'),
                            core_origin='REUSED_SHARED_SNAPSHOT_NEVER_CHAPTER_RECOMPUTED'))
                        self.research.analysis.insert(db, 'reports', 'report_id', report)
                    job.update(report_id=report['report_id'], stage='PUBLISHED', status='COMPLETE' if report['completeness']=='FULL' else 'PARTIAL')
            job['checkpoints'].append(dict(stage=stage, completed_at=now(), section_count=len(job['section_ids'])))
            job['last_advanced_at']=now()
            if job['status']=='RUNNING':
                job['status']='QUEUED'
        except Exception as error:
            job.update(status='FAILED', error=dict(code=getattr(error,'detail',None) or type(error).__name__, stage=stage))
        if cancel.is_set() and not job['report_id']:
            job.update(status='CANCELLED',cancel_requested_at=self.get(job_id)['cancel_requested_at'] or now())
        return self.save(job)

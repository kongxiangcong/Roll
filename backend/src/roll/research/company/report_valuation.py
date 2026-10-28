"""Report research to controlled operating model, without a second core authority."""
import json
import os
import threading
from pathlib import Path
from uuid import uuid4
from fastapi import HTTPException
from roll.accounts.ledger import encode, now
from roll.agents.company_valuation_runtime import INSTRUCTIONS, OUTPUT
from .models import OperatingValuationCommand
from .model_runtime import AnalysisRuntime
from .report_archive import archive
from .service import fail, fingerprint

LIMITATION = 'Automated research candidate; sourced assumptions remain conditional and require subsequent economic verification'


class ReportValuationRuntime(AnalysisRuntime):
    def __init__(self, reports):
        self.research = reports.research
        self.worker = reports.worker

    def command(self, job):
        """Local reviewable wire preparation. Does not read auth or execute a model."""
        snapshot = self.research.analysis_snapshot(job['snapshot_id'], 'REPORT')
        packet = self.research.analysis_input(snapshot['input_id'])
        contract = Path(__file__).with_name('valuation_candidate_contract.md').read_text(encoding='utf-8')
        prompt = dict(snapshot=snapshot, input_sha256=snapshot['content_sha256'],
                      evidence=packet['payload'], valuation_purpose=job.get('valuation_purpose', 'CURRENT_PRICING'),
                      request_cutoff=job['request_cutoff'], valuation_contract=contract)
        command = dict(model=job['model'], tools=[], output_schema=OUTPUT,
                       instructions=INSTRUCTIONS, prompt=encode(prompt))
        if len(encode(command).encode()) > 262144:
            fail('VALUATION_INPUT_TOO_LARGE', 'Frozen valuation command exceeds 256 KiB')
        return command

    def apply(self, job, snapshot, candidate):
        import jsonschema
        jsonschema.validate(candidate, OUTPUT)
        if candidate['snapshot_id'] != snapshot['snapshot_id'] or candidate['input_sha256'] != snapshot['content_sha256']:
            fail('INPUT_CHANGED', 'Valuation candidate changed its frozen shared snapshot', 409)
        if candidate['command_json'] is None:
            if not candidate['gaps']:
                fail('MODEL_OUTPUT_INVALID', 'Unavailable valuation requires explicit evidence gaps')
            return dict(status='BLOCKED', gaps=candidate['gaps'])
        request = json.loads(candidate['command_json'])
        if {'snapshot_id', 'idempotency_key', 'parent_version_id'} & set(request):
            fail('INPUT_CHANGED', 'Candidate cannot select another snapshot or valuation parent', 409)
        command = OperatingValuationCommand(**request, snapshot_id=snapshot['snapshot_id'],
            idempotency_key='report:' + job['job_id'], parent_version_id=None)
        basis = command.economic_basis
        if not basis.get('valuation_basis') or not basis.get('assumption_basis'):
            fail('PROVENANCE_REQUIRED', 'Automatic candidate requires explicit temporal and assumption audits')
        facts = {f['version_id']: f for f in self.research.analysis_input(snapshot['input_id'])['payload']['facts']}
        bridge_day = basis['valuation_basis']['bridge_as_of']
        for path, origin in command.provenance.items():
            if path != 'shares' and not path.startswith('equity_bridge/'):
                continue
            refs = origin['references'] if origin['kind'] != 'ASSUMED' else basis['assumption_basis'].get('config/' + path, {}).get('support_fact_version_ids', [])
            if not any(i in facts and facts[i]['value_type'] == 'NUMBER' and facts[i]['period_end'] == bridge_day
                       and facts[i]['scope'] == origin['scope'] and facts[i]['unit'] == origin['unit']
                       and facts[i]['currency'] == origin['currency'] for i in refs):
                fail('PROVENANCE_REQUIRED', 'Automatic bridge and diluted shares need numeric sources at the declared bridge date')
        if len(command.drivers.get('scenarios', [])) < 2:
            fail('OPERATING_MODEL_INVALID', 'Automatic valuation requires multiple operating scenarios')
        from .calculator import valuation_cutoff
        if valuation_cutoff(command.config['metadata']['as_of']) != valuation_cutoff(snapshot['as_of']):
            fail('INPUT_CHANGED', 'Automatic calculation cutoff must match the bound research day', 409)
        # A model proposal can never erase its own independent-verification limit.
        basis['limitations'] = list(dict.fromkeys([*basis.get('limitations', []), LIMITATION, *candidate['gaps']]))
        receipt = self.research.calculate_operating_valuation(command)
        return dict(status='COMPLETE', **receipt)

    def execute_report(self, job, cancel=None):
        snapshot = self.research.analysis_snapshot(job['snapshot_id'], 'REPORT') if job['snapshot_id'] else None
        if not snapshot:
            return dict(status='BLOCKED', gaps=['No accepted shared analysis snapshot; acquire and reconcile source facts'])
        if snapshot.get('economic_review_ids'):
            return dict(status='REUSED', snapshot_id=snapshot['snapshot_id'])
        facts = [self.research.fact(i, job['company_id']) for i in snapshot['fact_version_ids']]
        if len([f for f in facts if f['value_type'] == 'NUMBER']) < 3:
            return dict(status='BLOCKED', gaps=['Insufficient quantitative evidence for operating cashflows, discount rate and equity bridge'])
        company = self.research.analysis_input(snapshot['input_id'])['payload']['company']
        if company['industry'].upper() in {'BANK', 'BANKING', 'INSURANCE', 'FINANCIAL', '银行', '保险'}:
            return dict(status='BLOCKED', gaps=['Financial company: FCFF is not applicable; a dedicated valuation method is required'])
        # A completed host receipt is replayed on checkpoint retry, never re-estimated.
        with self.research.ledger.connection() as db:
            prior = db.execute("SELECT result FROM company_research_commands WHERE scope=? AND key=?",
                ('operating-valuation:' + job['company_id'], 'report:' + job['job_id'])).fetchone()
        if prior:
            return dict(status='COMPLETE', **json.loads(prior[0]))
        from roll.agents.codex_process import execute, process_creation
        command = self.command(job)
        from .report_template import code_hashes
        root = Path(__file__).parents[2]
        sources = {name: archive(self.research.evidence, (root / name).read_bytes(), 'OPERATING_VALUATION_RUNTIME_SOURCE')
                   for name in [*code_hashes(), 'research/company/economics.py', 'research/company/valuation.py',
                                'research/company/calculator.py', 'research/company/valuation_reference/fundamental_valuation.py']}
        run = dict(run_id=str(uuid4()), company_id=job['company_id'], job_id=job['job_id'], input_id=snapshot['input_id'],
            source_snapshot_id=snapshot['snapshot_id'], input_sha256=snapshot['content_sha256'],
            task_kind='COMPANY_OPERATING_VALUATION', backend='CODEX', model=job['model'],
            status='RUNNING', started_at=now(), archives=[], tools=[], formal_authority=False,
            evidence_kind='METHOD_CASE' if self.worker else 'CODEX_VALUATION_ATTEMPT', model_executed=False,
            command_archive=archive(self.research.evidence, encode(command).encode(), 'OPERATING_VALUATION_COMMAND'),
            command_sha256=fingerprint(command),
            execution_code_hashes={name: value['sha256'] for name, value in sources.items()}, execution_sources=sources,
            limits=dict(timeout_seconds=90, runtime_operations=8, tool_calls=0),
            host_owner=dict(pid=os.getpid(), creation_ticks=process_creation(os.getpid())))
        self.save(run)
        result = None
        try:
            configured = os.environ.get('ROLL_CODEX_AUTH_FILE')
            if not configured:
                raise FileNotFoundError()
            auth = json.loads(Path(configured).read_text(encoding='utf-8'))
            if auth.get('auth_mode') != 'chatgpt' or not auth.get('tokens'):
                raise ValueError('CHATGPT_AUTH_REQUIRED')
            run['model_executed'] = True
            execute(self, run, {'command': command}, cancel or threading.Event(), auth)
            if run['status'] == 'COMPLETE':
                result = self.apply(job, snapshot, run['candidate'])
                run['status'] = result['status']
                if result.get('snapshot_id'):
                    run['snapshot_id'] = result['snapshot_id']
        except (ValueError, OSError, HTTPException) as error:
            detail = error.detail if isinstance(error, HTTPException) and isinstance(error.detail, dict) else {}
            run.update(status='UNAVAILABLE' if isinstance(error, OSError) else 'FAILED',
                       error=dict(code=detail.get('code', 'MODEL_UNAVAILABLE' if isinstance(error, OSError) else 'MODEL_OUTPUT_INVALID'),
                                  reason=detail.get('reason'), type=type(error).__name__))
        except Exception as error:
            run.update(status='FAILED', error=dict(code='MODEL_OUTPUT_INVALID', type=type(error).__name__))
        finally:
            run['finished_at'] = now()
            self.save(run)
        return {**(result or dict(status=run['status'], gaps=[run.get('error', {}).get('code', run['status'])])),
                'run_id': run['run_id'], 'source_snapshot_id': snapshot['snapshot_id']}

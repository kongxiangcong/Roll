from pathlib import Path
from datetime import date, datetime
import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from roll.accounts.csv_import import CsvImports, CsvRevision, template, guide,VERSION

from roll.accounts.ledger import ConfirmCommand, DraftCommand, EquityHint, Ledger
from roll.accounts.cash_events import EVENT_FIELDS
from roll.accounts.reconcile import UseCheck,use_check,consistency
from roll.accounts.valuation import Valuations,ValuationRequest
from roll.accounts.corrections import active_events,fact_command
from roll.config import data_directory, load_runtime_environment
from roll.market.directory import MarketDirectory, WatchCommand, IdentityCommand, ScopeCommand
from roll.market.status_evidence import query as status_evidence_query
from roll.market.action_evidence import query as action_evidence_query
from roll.market.evidence import EvidenceStore, DataRequest
from roll.market.source_facts import REGISTRY
from roll.agents.codex_evidence import CodexEvidence, CodexQuestion
from roll.agents.deepseek_evidence import DeepSeekEvidence, DeepSeekQuestion
from roll.agents.settings import AgentSettings, BackendSelection, AgentQuestion, require_current_backend
from roll.market.resolution import SourceResolutions, ResolutionCommand
from roll.market.verification import IndependentVerifications, VerificationCommand
from roll.research.registry import ExperimentRegistry, ProtocolCommand, AttemptCommand, FinishCommand, FreezeCommand, ReasonCommand, CheckpointCommand, deadline_preview
from roll.research.datasets import DatasetCommand
from roll.research.reconstruction import ReconstructionCommand,reconstruct
from roll.research.execution import DailyExecutions,ExecutionCommand,AssessmentCommand
from roll.research.models import TransparentModels,ModelCommand,ForecastCommand
from roll.research.shadow import ShadowLab,CompleteFreezeCommand,AdvanceCommand,ConditionalCommand
from roll.research.policy_successors import PolicySuccessors,SuccessorCommand,MigrationCommand,PolicyEvaluation
from roll.research.successor_shadow import SuccessorShadow,SuccessorFreezeCommand,SuccessorAdvanceCommand
from roll.research.validation import AutomaticValidation,ValidationCommand
from roll.research.technical_review import TechnicalReviews,ReviewCommand as TechnicalReviewCommand
from roll.research.training_preflight import training_preflight,TrainingPurpose,admit_model_training
from roll.research.prospective import ProspectiveEvidence, CollectionCommand
from roll.market.post_close_packet import PacketCommand, ObligationCommand
from roll.market.sse_price_quotes import PriceQuotes, PriceQuoteCommand, PricePacketCommand
from roll.market.sse_company_actions import CompanyActionPages
from roll.market.sse_action_assessments import ActionAssessments,ActionAssessmentCommand,ActionPacketCommand
from roll.market.action_window import ActionWindows,ActionWindowCommand
from roll.research.forward import ForwardArchive, ForwardCommand, CheckCommand, StopCommand
from roll.research.synthetic import SyntheticDevelopment
from roll.market.collection_sources import SourcePolicyCommand
from roll.research.corporate_actions import CashRightsCommand, assess_cash_rights
from roll.research.risk_policy import IndependentRiskPolicies,PolicyCommand,PolicyEvaluationCommand
from roll.decisions.funding import Funding, FundingConfirmation, LossSample, capabilities
from roll.decisions.capabilities import Capabilities, GrantCommand, LifecycleCommand
from roll.decisions.actions import Actions, EvaluationCommand
from roll.decisions.broker_costs import BrokerCosts, BrokerCostConfirmation, BrokerCostEstimate
from roll.runtime.reviews import Reviews,ReviewCommand,MaintenanceCommand,VerificationRequest
from roll.runtime.backups import bootstrap,rollback_bootstrap,finish_bootstrap


def _create_app(directory: Path | None = None, market_transport=None, market_clock=None, codex_worker: Path | None = None, deepseek_endpoint: str | None = None, review_clock=None, baostock_worker: Path | None = None,technical_review_method_file:Path|None=None,capability_method_file:Path|None=None,runtime_role:str|None=None,notification_transport=None):
    @asynccontextmanager
    async def lifespan(application):
        try:
            started=application.state.reviews.start()
            if runtime_role == 'WORKER' and not started:
                raise RuntimeError('BACKGROUND_WORKER_ALREADY_RUNNING')
            if runtime_role != 'API':
                application.state.backups.start()
            yield
        finally:
            await asyncio.to_thread(application.state.research.close)
            await asyncio.to_thread(application.state.reviews.close)
            await asyncio.to_thread(application.state.codex.close)
            await asyncio.to_thread(application.state.deepseek.close)
            await asyncio.to_thread(application.state.technical_reviews.close)
            await asyncio.to_thread(application.state.backups.close)
            if not (application.state.reviews.thread and application.state.reviews.thread.is_alive()):
                application.state.host_marker.unlink(missing_ok=True)

    app = FastAPI(title="Roll", version="0.1.0", lifespan=lifespan)
    ledger = Ledger(directory or data_directory())
    app.state.ledger = ledger
    imports = CsvImports(ledger)

    @app.post('/api/research/cash-rights/assess')
    def research_cash_rights(command: CashRightsCommand):
        return assess_cash_rights(command)

    @app.get("/api/account/csv/template")
    def csv_template(version: str = VERSION):
        content = template(version)
        return Response(content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="roll-csv-{version[-1]}.csv"'})

    @app.get("/api/account/csv/guide")
    def csv_guide():
        return Response(guide(), media_type="text/html")

    @app.post("/api/account/csv/drafts", status_code=201)
    async def csv_draft(request: Request, filename: str, encoding: str, expected_account_version: int, revision_of: str | None = None):
        if expected_account_version < 0:
            raise HTTPException(422, "账户版本必须非负")
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 4 * 1024 * 1024:
                raise HTTPException(413, "CSV 最多4MiB")
        return imports.upload(bytes(raw), filename, encoding, expected_account_version, revision_of)

    @app.get("/api/account/csv/drafts/{draft_id}")
    def csv_get(draft_id: str):
        return imports.get(draft_id)

    @app.post("/api/account/csv/drafts/{draft_id}/revise", status_code=201)
    def csv_revise(draft_id: str, command: CsvRevision):
        return imports.revise(draft_id, command)

    @app.get("/api/account/csv/files/{fingerprint}")
    def csv_file(fingerprint: str):
        return Response(imports.file(fingerprint), media_type="application/octet-stream")
    market = MarketDirectory(ledger)
    app.state.market = market
    evidence=EvidenceStore(ledger,market,market_transport,baostock_worker)
    app.state.evidence=evidence
    research=ExperimentRegistry(ledger,evidence)
    app.state.research=research
    executions=DailyExecutions(research)
    research.executions=executions
    app.state.executions=executions
    models=TransparentModels(research,executions)
    research.models=models
    app.state.models=models
    shadow=ShadowLab(research,models)
    app.state.shadow=shadow
    policy_successors = PolicySuccessors(shadow)
    successor_shadow = SuccessorShadow(policy_successors)

    @app.post('/api/research/policy-successors/{proposal_id}/freezes', status_code=201)
    def successor_freeze(proposal_id: str, command: SuccessorFreezeCommand):
        return successor_shadow.freeze(proposal_id, command)

    @app.get('/api/research/policy-successor-freezes/{freeze_id}')
    def successor_freeze_get(freeze_id: str):
        return successor_shadow.get(freeze_id)

    @app.post('/api/research/policy-successor-freezes/{freeze_id}/shadow/advance', status_code=201)
    def successor_shadow_advance(freeze_id: str, command: SuccessorAdvanceCommand):
        return successor_shadow.advance(freeze_id, command)

    @app.get('/api/research/policy-successor-freezes/{freeze_id}/shadow')
    def successor_shadow_current(freeze_id: str):
        return successor_shadow.current(freeze_id)

    @app.post('/api/research/policy-successor-freezes/{freeze_id}/shadow/replay')
    def successor_shadow_replay(freeze_id: str):
        return successor_shadow.replay(freeze_id)

    @app.post('/api/research/policy-successors', status_code=201)
    def policy_successor_register(command: SuccessorCommand):
        return policy_successors.register(command)

    @app.get('/api/research/policy-successors/{proposal_id}')
    def policy_successor_get(proposal_id: str):
        return policy_successors.get(proposal_id)

    @app.post('/api/research/policy-successors/{proposal_id}/migrations', status_code=201)
    def policy_successor_migrate(proposal_id: str, command: MigrationCommand):
        return policy_successors.migrate(proposal_id, command)

    @app.post('/api/research/policy-successors/{proposal_id}/evaluations', status_code=201)
    def policy_successor_evaluate(proposal_id: str, command: PolicyEvaluation):
        return policy_successors.evaluate(proposal_id, command)

    @app.get('/api/research/policy-successors/{proposal_id}/evaluations/{evaluation_id}')
    def policy_successor_evaluation(proposal_id: str, evaluation_id: str):
        return policy_successors.evaluation(proposal_id, evaluation_id)

    @app.post('/api/research/policy-successors/{proposal_id}/evaluations/{evaluation_id}/replay')
    def policy_successor_replay(proposal_id: str, evaluation_id: str):
        return policy_successors.replay(proposal_id, evaluation_id)

    validation=AutomaticValidation(shadow)
    app.state.validation=validation

    @app.post('/api/research/complete-freezes/{freeze_id}/validations',status_code=201)
    def validation_create(freeze_id:str,command:ValidationCommand):
        return validation.create(freeze_id,command)

    @app.get('/api/research/complete-freezes/{freeze_id}/validations')
    def validation_list(freeze_id:str):
        return validation.list(freeze_id)

    @app.get('/api/research/complete-freezes/{freeze_id}/validation-attempts')
    def validation_attempts(freeze_id:str):
        return validation.attempts(freeze_id)

    @app.get('/api/research/validations/{validation_id}')
    def validation_get(validation_id:str):
        return validation.get(validation_id)

    @app.post('/api/research/validations/{validation_id}/replay')
    def validation_replay(validation_id:str):
        return validation.replay(validation_id)

    @app.post('/api/research/protocols/{protocol_id}/complete-freezes',status_code=201)
    def complete_freeze(protocol_id:str,command:CompleteFreezeCommand):
        return shadow.freeze(protocol_id,command)

    @app.get('/api/research/protocols/{protocol_id}/complete-freezes')
    def complete_freezes(protocol_id:str):
        return shadow.list(protocol_id)

    @app.get('/api/research/complete-freezes/{freeze_id}')
    def complete_freeze_get(freeze_id:str):
        return shadow.get(freeze_id)

    @app.post('/api/research/shadow/{freeze_id}/advance',status_code=201)
    def shadow_advance(freeze_id:str,command:AdvanceCommand):
        return shadow.advance(freeze_id,command)

    @app.get('/api/research/shadow/{freeze_id}')
    def shadow_get(freeze_id:str):
        return shadow.current(freeze_id)

    @app.post('/api/research/shadow/{freeze_id}/replay')
    def shadow_replay(freeze_id:str):
        return shadow.replay(freeze_id)

    @app.post('/api/research/shadow/{freeze_id}/account-conditional',status_code=201)
    def shadow_conditional(freeze_id:str,command:ConditionalCommand):
        return shadow.conditional(freeze_id,command)

    @app.get('/api/research/results')
    def shadow_results(freeze_id:str):
        return shadow.results(freeze_id)
    prospective=ProspectiveEvidence(evidence,research)
    price_quotes=PriceQuotes(prospective)
    company_actions=CompanyActionPages(prospective)
    action_assessments=ActionAssessments(company_actions,price_quotes)
    action_windows=ActionWindows(action_assessments)
    forward=ForwardArchive(shadow,prospective,review_clock)
    forward.action_windows=action_windows
    app.state.forward=forward

    @app.post('/api/research/complete-freezes/{freeze_id}/forward',status_code=201)
    def forward_register(freeze_id:str,command:ForwardCommand):return forward.register(freeze_id,command)

    @app.get('/api/research/complete-freezes/{freeze_id}/forward')
    def forward_get(freeze_id:str):return forward.state(freeze_id)

    @app.post('/api/research/complete-freezes/{freeze_id}/forward/check',status_code=201)
    def forward_check(freeze_id:str,command:CheckCommand):return forward.check(freeze_id,command)

    @app.post('/api/research/complete-freezes/{freeze_id}/forward/replay')
    def forward_replay(freeze_id:str):return forward.replay(freeze_id)

    @app.post('/api/research/complete-freezes/{freeze_id}/forward/settle',status_code=201)
    def forward_settle(freeze_id:str,command:CheckCommand):return forward.settle(freeze_id,command)

    @app.post('/api/research/complete-freezes/{freeze_id}/forward/stop')
    def forward_stop(freeze_id:str,command:StopCommand):return forward.stop(freeze_id,command)
    app.state.prospective=prospective
    @app.post('/api/research/collections/{plan_id}/post-close',status_code=201)
    def post_close_capture(plan_id:str,command:PacketCommand):
        return prospective.post_close.capture(plan_id,command.basis)

    @app.post('/api/research/collections/{plan_id}/post-close/check',status_code=201)
    def post_close_job(plan_id:str,command:PacketCommand):
        return prospective.post_close.capture_once(plan_id,command.basis)

    @app.post('/api/research/collections/{plan_id}/post-close-packets',status_code=201)
    def post_close_build(plan_id:str,command:PacketCommand):
        return prospective.post_close.build(plan_id,command.basis)

    @app.post('/api/research/collections/{plan_id}/sse-history-assessments',status_code=201)
    def assess_sse_history(plan_id: str,command: PacketCommand):
        return prospective.post_close.assess_history(plan_id,command.basis)

    @app.post('/api/research/collections/{plan_id}/cninfo-history-assessments',status_code=201)
    def cninfo_history_assessment(plan_id:str,command:PacketCommand):
        return prospective.post_close.assess_cninfo_history(plan_id,command.basis)

    @app.post('/api/research/collections/{plan_id}/known-obligation-audits',status_code=201)
    def known_obligation_audit(plan_id:str,command:ObligationCommand):
        return prospective.post_close.assess_obligations(plan_id,command)

    @app.get('/api/research/collections/{plan_id}/known-obligation-audits')
    def known_obligation_audits(plan_id:str,protocol_id:str|None=None):
        return prospective.post_close.obligations(plan_id,protocol_id=protocol_id)

    @app.get('/api/research/collections/{plan_id}/source-gaps')
    def post_close_source_gaps(plan_id: str):
        return {**prospective.post_close.source_gaps(plan_id),
                'price_quote_assessments': price_quotes.assessments(plan_id),
                'price_quote_current': price_quotes.current(plan_id),
                'action_source_receipts':company_actions.receipts(plan_id),
                'action_assessments':action_assessments.assessments(plan_id),
                'action_current':action_assessments.current(plan_id)}

    @app.post('/api/research/collections/{plan_id}/sse-suspension',status_code=201)
    def sse_suspension_capture(plan_id:str,command:PacketCommand):
        return prospective.post_close.capture_suspension(plan_id,command.basis)

    @app.get('/api/research/collections/{plan_id}/sse-suspension-receipts')
    def sse_suspension_receipts(plan_id:str):
        return prospective.post_close.suspension_receipts(plan_id)

    @app.post('/api/research/collections/{plan_id}/sse-suspension/check',status_code=201)
    def sse_suspension_worker(plan_id:str,command:PacketCommand):
        return prospective.post_close.capture_suspension_once(plan_id,command.basis)

    @app.post('/api/research/collections/{plan_id}/sse-stock-suspension',status_code=201)
    def sse_stock_suspension_capture(plan_id:str,command:PacketCommand):
        return prospective.post_close.stock_suspensions.capture(plan_id,command.basis)

    @app.post('/api/research/collections/{plan_id}/sse-company-contract',status_code=201)
    def sse_company_contract_capture(plan_id:str,command:PacketCommand):
        return prospective.post_close.company_contracts.capture(plan_id,command.basis)

    @app.post('/api/research/collections/{plan_id}/sse-company-actions',status_code=201)
    def sse_company_action_capture(plan_id:str,command:PacketCommand):
        return company_actions.capture_once(plan_id,command.basis)

    @app.get('/api/research/collections/{plan_id}/sse-company-action-receipts')
    def sse_company_action_receipts(plan_id:str):
        return company_actions.receipts(plan_id)

    @app.post('/api/research/collections/{plan_id}/sse-action-assessments',status_code=201)
    def sse_action_assess(plan_id:str,command:ActionAssessmentCommand):
        return action_assessments.assess(plan_id,command)

    @app.get('/api/research/collections/{plan_id}/sse-action-assessments')
    def sse_action_assessment_query(plan_id:str):return action_assessments.assessments(plan_id)

    @app.get('/api/research/collections/{plan_id}/action-evidence')
    def action_evidence(plan_id:str,known_by:datetime|None=Query(None)):
        return action_evidence_query(action_assessments,plan_id,known_by)

    @app.get('/api/research/collections/{plan_id}/sse-action-assessments/current')
    def sse_action_current(plan_id:str):return action_assessments.current(plan_id)

    @app.post('/api/research/collections/{plan_id}/sse-action-packets',status_code=201)
    def sse_action_packet(plan_id:str,command:ActionPacketCommand):return action_assessments.build(plan_id,command)

    @app.get('/api/research/collections/{plan_id}/sse-action-packets/{packet_id}')
    def sse_action_packet_query(plan_id:str,packet_id:str):return action_assessments.packet(plan_id,packet_id)

    @app.post('/api/research/collections/{plan_id}/action-window-packets',status_code=201)
    def action_window_build(plan_id:str,command:ActionWindowCommand):return action_windows.build(plan_id,command)

    @app.get('/api/research/collections/{plan_id}/action-window-packets/{packet_id}')
    def action_window_packet(plan_id:str,packet_id:str):return action_windows.packet(plan_id,packet_id)

    @app.get('/api/research/collections/{plan_id}/action-window-inputs')
    def action_window_inputs(plan_id:str,protocol_id:str):return action_windows.consume(plan_id,protocol_id)

    @app.post('/api/research/collections/{plan_id}/sse-price-quotes',status_code=201)
    def sse_price_assess(plan_id:str,command:PriceQuoteCommand):
        return price_quotes.assess(plan_id,command)

    @app.get('/api/research/collections/{plan_id}/sse-price-quotes')
    def sse_price_assessments(plan_id:str):
        return price_quotes.assessments(plan_id)

    @app.get('/api/research/collections/{plan_id}/sse-price-quotes/current')
    def sse_price_current(plan_id:str):
        return price_quotes.current(plan_id)

    @app.post('/api/research/collections/{plan_id}/sse-price-packets',status_code=201)
    def sse_price_packet(plan_id:str,command:PricePacketCommand):
        return price_quotes.build(plan_id,command)

    @app.get('/api/research/collections/{plan_id}/sse-price-packets/{packet_id}')
    def sse_price_packet_get(plan_id:str,packet_id:str):
        return price_quotes.packet(plan_id,packet_id)

    @app.get('/api/research/collections/{plan_id}/sse-company-contract-receipts')
    def sse_company_contract_receipts(plan_id:str):
        return prospective.post_close.company_contracts.receipts(plan_id)

    @app.get('/api/research/collections/{plan_id}/status-evidence')
    def status_evidence(plan_id:str,known_by:datetime|None=Query(None)):
        return status_evidence_query(prospective.post_close,plan_id,known_by)

    @app.post('/api/research/collections/{plan_id}/sse-company-contract/check',status_code=201)
    def sse_company_contract_worker(plan_id:str,command:PacketCommand):
        return prospective.post_close.company_contracts.capture_once(plan_id,command.basis)

    @app.get('/api/research/collections/{plan_id}/sse-stock-suspension-receipts')
    def sse_stock_suspension_receipts(plan_id:str):
        return prospective.post_close.stock_suspensions.receipts(plan_id)

    @app.post('/api/research/collections/{plan_id}/sse-stock-suspension/check',status_code=201)
    def sse_stock_suspension_worker(plan_id:str,command:PacketCommand):
        return prospective.post_close.stock_suspensions.capture_once(plan_id,command.basis)

    @app.post('/api/research/post-close-packets/{packet_id}/replay')
    def post_close_replay(packet_id:str):
        if action_windows.saved_packet(packet_id):
            return action_windows.replay(packet_id)
        if action_assessments.saved_packet(packet_id):
            return action_assessments.replay(packet_id)
        if price_quotes.saved_packet(packet_id):
            return price_quotes.replay(packet_id)
        return prospective.post_close.replay(packet_id)
    app.state.collection_sources=prospective.sources
    development=SyntheticDevelopment(research,executions,models)
    app.state.development=development

    @app.post('/api/research/collections',status_code=201)
    def collection_start(command:CollectionCommand):
        return prospective.start(command)

    @app.get('/api/research/collections')
    def collection_plans():
        return prospective.plans()

    @app.post('/api/research/collections/{plan_id}/collect',status_code=201)
    def collection_collect(plan_id:str):
        return prospective.collect(plan_id)

    @app.get('/api/research/collections/{plan_id}/batches')
    def collection_batches(plan_id:str):
        return prospective.batches(plan_id)

    @app.get('/api/research/collections/{plan_id}/as-of')
    def collection_asof(plan_id:str,cutoff:datetime):
        return prospective.as_of(plan_id,cutoff)

    @app.get('/api/research/collections/{plan_id}/readiness')
    def collection_readiness(plan_id:str):
        return prospective.readiness(plan_id)

    @app.get('/api/research/collection-sources')
    def collection_sources():
        return prospective.sources.listing()

    @app.post('/api/research/collection-sources/{source_id}/policy')
    def collection_source_policy(source_id:str,command:SourcePolicyCommand):
        return prospective.sources.change(source_id,command)

    @app.get('/api/research/collection-cleaning')
    def collection_cleaning():
        return prospective.sources.reports()

    @app.post('/api/research/collection-integrity')
    def collection_integrity():
        return prospective.sources.integrity()

    @app.get('/api/research/collections/{plan_id}/comparisons')
    def collection_comparisons(plan_id:str):
        prospective.plan(plan_id)
        return prospective.sources.comparisons(plan_id)

    @app.post('/api/research/development-runs',status_code=201)
    def virtual_development():
        return development.create()

    @app.get('/api/research/development-runs')
    def virtual_development_runs():
        return development.runs()

    @app.post('/api/research/protocols/{protocol_id}/models',status_code=201)
    def research_model_create(protocol_id:str,command:ModelCommand):
        if shadow.list(protocol_id):raise HTTPException(409,'完整实验已冻结；新模型须登记关联后继实验')
        admit_model_training(research,protocol_id,command.purpose)
        return models.create(protocol_id,command)

    @app.get('/api/research/protocols/{protocol_id}/models')
    def research_models(protocol_id:str):
        return models.list(protocol_id)

    @app.get('/api/research/protocols/{protocol_id}/training-preflight')
    def research_training_preflight(protocol_id:str,purpose:TrainingPurpose='RESEARCH'):
        return training_preflight(research,protocol_id,purpose)

    @app.get('/api/research/models/{model_id}')
    def research_model_get(model_id:str):
        return models.get(model_id)

    @app.post('/api/research/models/{model_id}/forecasts',status_code=201)
    def research_forecast(model_id:str,command:ForecastCommand):
        return models.forecast(model_id,command)

    @app.get('/api/research/forecasts/{forecast_id}')
    def research_forecast_get(forecast_id:str):
        return models.get_forecast(forecast_id)

    @app.post('/api/research/forecasts/{forecast_id}/replay')
    def research_forecast_replay(forecast_id:str):
        return models.replay(forecast_id)

    @app.post('/api/research/protocols/{protocol_id}/executions',status_code=201)
    def research_execution(protocol_id:str,command:ExecutionCommand):
        return executions.create(protocol_id,command)

    @app.get('/api/research/executions/{execution_id}')
    def research_execution_get(execution_id:str):
        return executions.get(execution_id)

    @app.post('/api/research/executions/{execution_id}/replay')
    def research_execution_replay(execution_id:str):
        return executions.replay(execution_id)

    @app.post('/api/research/executions/{execution_id}/assessments',status_code=201)
    def research_execution_assess(execution_id:str,command:AssessmentCommand):
        return executions.assess(execution_id,command)

    @app.get('/api/research/protocols/{protocol_id}/execution-support')
    def research_execution_support(protocol_id:str,partition:str|None=None):
        if partition is not None and partition not in {'DEVELOPMENT','CALIBRATION'}:raise HTTPException(422,'支持查询仅开发/校准')
        return executions.support(protocol_id,partition)

    @app.get('/api/research/deadline-preview')
    def research_deadline_preview(start:datetime):
        return deadline_preview(start)

    @app.post('/api/research/datasets',status_code=201)
    def register_research_dataset(command:DatasetCommand):
        return research.register_dataset(command)

    @app.get('/api/research/datasets')
    def research_datasets():
        return research.datasets()

    @app.post('/api/research/datasets/{dataset_id}/reconstruct',status_code=201)
    def research_reconstruct(dataset_id:str,command:ReconstructionCommand):
        return reconstruct(research,dataset_id,command)

    @app.get('/api/research/datasets/{dataset_id}')
    def research_dataset(dataset_id:str):
        return research.dataset(dataset_id)

    @app.get('/api/research/datasets/{dataset_id}/partitions/{name}')
    def research_partition(dataset_id:str,name:str):
        return research.partition(dataset_id,name)

    @app.post('/api/research/protocols',status_code=201)
    def register_protocol(command:ProtocolCommand):
        return research.register(command)

    @app.get('/api/research/protocols')
    def research_protocols():
        return research.protocols()

    @app.get('/api/research/protocols/{protocol_id}')
    def research_protocol(protocol_id:str):
        return research.get(protocol_id)

    @app.post('/api/research/protocols/{protocol_id}/attempts',status_code=201)
    def research_attempt(protocol_id:str,command:AttemptCommand):
        if shadow.list(protocol_id):raise HTTPException(409,'完整实验已冻结；修改政策/方法须登记关联后继实验')
        return research.start_attempt(protocol_id,command)

    @app.get('/api/research/protocols/{protocol_id}/attempts')
    def research_attempts(protocol_id:str):
        return research.attempts(protocol_id)

    @app.get('/api/research/protocols/{protocol_id}/attempt-manifest')
    def research_attempt_manifest(protocol_id:str):
        return research.attempt_manifest(protocol_id)

    @app.post('/api/research/attempts/{attempt_id}/finish')
    def finish_research_attempt(attempt_id:str,command:FinishCommand):
        return research.finish_attempt(attempt_id,command)

    @app.get('/api/research/protocols/{protocol_id}/audit')
    def research_audit(protocol_id:str):
        return research.audit(protocol_id)

    @app.post('/api/research/protocols/{protocol_id}/freeze')
    def research_freeze(protocol_id:str,command:FreezeCommand):
        return research.freeze(protocol_id,command)

    @app.post('/api/research/protocols/{protocol_id}/sealed-input')
    def research_sealed(protocol_id:str,command:ReasonCommand):
        return research.sealed_input(protocol_id,command)

    @app.post('/api/research/protocols/{protocol_id}/checkpoints',status_code=201)
    def research_checkpoint(protocol_id:str,command:CheckpointCommand):
        return research.checkpoint(protocol_id,command)
    reviews=Reviews(ledger,market,evidence,review_clock,worker_enabled=runtime_role != "API")
    reviews.forward=forward
    app.state.reviews=reviews

    @app.post('/api/reviews/tasks',status_code=202)
    def start_review(command:ReviewCommand):
        return reviews.submit(command)

    @app.get('/api/reviews/tasks/{identifier}')
    def get_review(identifier:str):
        return reviews.get(identifier)

    @app.post('/api/reviews/tasks/{identifier}/cancel')
    def cancel_review(identifier:str):
        return reviews.cancel(identifier)

    @app.post('/api/reviews/tasks/{identifier}/replay')
    def replay_review(identifier:str):
        return reviews.replay(identifier)

    @app.post('/api/reviews/tasks/{identifier}/verification-request',status_code=201)
    def review_verification_request(identifier:str,command:VerificationRequest):
        return reviews.verification_request(identifier,command)

    @app.get('/api/reviews/verification-requests/{identifier}')
    def get_review_verification_request(identifier:str):
        return research.market_input_exposed(verifications.review_request(identifier),'verification-review-request')

    @app.post('/api/reviews/verification-requests/{identifier}/verify')
    def consume_review_verification_request(identifier:str):
        return research.market_input_exposed(verifications.consume_review(identifier),'verification-review-consume')

    @app.get('/api/reviews/summary')
    def review_summary():
        return reviews.summary()

    @app.get('/api/reviews/history')
    def review_history():
        return reviews.history()

    @app.get('/api/reviews/health')
    def review_health():
        return reviews.health()

    @app.get('/api/reviews/audits/{identifier}')
    def review_audit(identifier:str):
        return reviews.get_audit(identifier)

    @app.get('/api/reviews/audits')
    def review_audits():
        return reviews.audits()

    @app.post('/api/reviews/recover',status_code=202)
    def recover_reviews():
        reviews.start()
        reviews.check_maintenance()
        return reviews.submit(ReviewCommand(mode='RECOVERY'))

    @app.get('/api/reviews/coverage')
    def review_coverage():
        return reviews.coverage()

    @app.post('/api/reviews/maintenance',status_code=201)
    def maintenance_register(command:MaintenanceCommand):
        return reviews.register_maintenance(command)

    @app.get('/api/reviews/maintenance')
    def maintenance_schedules():
        return reviews.maintenance()

    @app.get('/api/reviews/maintenance/checks')
    def maintenance_checks():
        return reviews.maintenance_checks()

    @app.post('/api/reviews/maintenance/check')
    def check_due_maintenance():
        return reviews.check_maintenance()
    valuations=Valuations(ledger,evidence)
    app.state.valuations=valuations
    risk_policies=IndependentRiskPolicies(research,valuations)
    app.state.risk_policies=risk_policies

    @app.post('/api/research/protocols/{protocol_id}/risk-policies',status_code=201)
    def risk_policy_register(protocol_id:str,command:PolicyCommand):
        return risk_policies.register(protocol_id,command)

    @app.get('/api/research/protocols/{protocol_id}/risk-policies')
    def risk_policy_list(protocol_id:str):
        return risk_policies.list(protocol_id)

    @app.get('/api/research/risk-policies/{policy_id}')
    def risk_policy_get(policy_id:str):
        return risk_policies.get(policy_id)

    @app.post('/api/research/risk-policies/{policy_id}/evaluations',status_code=201)
    def risk_policy_evaluate(policy_id:str,command:PolicyEvaluationCommand):
        return risk_policies.evaluate(policy_id,command)

    @app.get('/api/research/risk-policies/{policy_id}/evaluations')
    def risk_policy_evaluations(policy_id:str):
        return risk_policies.evaluations(policy_id)

    @app.get('/api/research/risk-policies/{policy_id}/validation')
    def risk_policy_validation(policy_id:str):
        return risk_policies.validation(policy_id)

    @app.get('/api/research/risk-evaluations/{evaluation_id}')
    def risk_policy_evaluation_get(evaluation_id:str):
        return risk_policies.get_evaluation(evaluation_id)

    @app.post('/api/research/risk-evaluations/{evaluation_id}/replay')
    def risk_policy_evaluation_replay(evaluation_id:str):
        return risk_policies.replay(evaluation_id)

    @app.post('/api/account/valuations',status_code=201)
    def publish_valuation(command:ValuationRequest):
        return valuations.publish(command)

    @app.get('/api/account/valuation-basis')
    def valuation_basis():
        return valuations.basis()

    @app.get('/api/account/valuations')
    def valuation_history():
        return valuations.history()

    @app.get('/api/account/valuations/current')
    def current_valuation():
        return valuations.get()

    @app.get('/api/account/valuations/{identifier}')
    def get_valuation(identifier:str):
        return valuations.get(identifier)

    @app.post('/api/account/valuations/{identifier}/replay')
    def replay_valuation(identifier:str):
        return valuations.get(identifier,replay=True)
    resolutions=SourceResolutions(evidence,market_clock)
    app.state.resolutions=resolutions
    codex = CodexEvidence(evidence, codex_worker, input_observer=research.market_input_exposed,
        archive_reuse_check=resolutions.can_reuse_archives)
    app.state.codex = codex
    deepseek=DeepSeekEvidence(evidence,deepseek_endpoint,input_observer=research.market_input_exposed,
        archive_reuse_check=resolutions.can_reuse_archives)
    app.state.deepseek=deepseek
    agent_settings=AgentSettings(ledger)
    app.state.agent_settings=agent_settings
    technical_reviews=TechnicalReviews(validation,agent_settings,worker=codex_worker,endpoint=deepseek_endpoint,risk_policies=risk_policies,method_file=technical_review_method_file)
    app.state.technical_reviews=technical_reviews

    @app.get('/api/research/method-review-materials')
    def technical_method_materials():
        return technical_reviews.method_materials()

    @app.post('/api/research/validations/{validation_id}/review-materials',status_code=201)
    def technical_review_materials(validation_id:str):
        return technical_reviews.material(validation_id)

    @app.get('/api/research/validations/{validation_id}/review-materials')
    def validation_review_material_list(validation_id:str):
        return technical_reviews.basis_materials(validation_id)

    @app.post('/api/research/risk-evaluations/{evaluation_id}/review-materials',status_code=201)
    def risk_technical_review_materials(evaluation_id:str):
        return technical_reviews.risk_material(evaluation_id)

    @app.get('/api/research/risk-evaluations/{evaluation_id}/review-materials')
    def risk_review_material_list(evaluation_id:str):
        return technical_reviews.basis_materials(evaluation_id)

    @app.get('/api/research/review-materials')
    def saved_technical_review_materials():
        return technical_reviews.materials()

    @app.get('/api/research/review-materials/{material_id}')
    def technical_review_material(material_id:str):
        return technical_reviews.get_material(material_id)

    @app.post('/api/research/review-materials/{material_id}/reviews',status_code=202)
    def technical_review_start(material_id:str,command:TechnicalReviewCommand):
        return technical_reviews.start(material_id,command)

    @app.get('/api/research/review-materials/{material_id}/reviews')
    def technical_review_runs(material_id:str):
        return technical_reviews.runs(material_id)

    @app.get('/api/research/technical-reviews/{run_id}')
    def technical_review_get(run_id:str):
        return technical_reviews.get(run_id)

    @app.post('/api/research/technical-reviews/{run_id}/cancel')
    def technical_review_cancel(run_id:str):
        return technical_reviews.cancel(run_id)

    @app.get('/api/research/review-materials/{material_id}/delivery')
    def validation_delivery(material_id:str):
        return technical_reviews.delivery(material_id)

    @app.post('/api/research/review-materials/{material_id}/export',status_code=201)
    def validation_delivery_export(material_id:str):
        return technical_reviews.export(material_id)

    @app.get('/api/agents/settings')
    def backend_settings():
        current=agent_settings.get()
        return {**current,'supported_backends':['CODEX'],'resave_required':current['backend']!='CODEX'}

    @app.get('/api/agents/settings/history')
    def backend_settings_history():
        return agent_settings.history()

    @app.post('/api/agents/settings')
    def select_backend(command:BackendSelection):
        return agent_settings.select(command)

    @app.post('/api/data/requests/{request_id}/agent',status_code=202)
    def agent_start(request_id:str,command:AgentQuestion):
        selection=agent_settings.get()
        require_current_backend(selection['backend'])
        return codex.start(request_id,command,selection)

    @app.post('/api/data/requests/{request_id}/deepseek',status_code=202)
    def deepseek_start(request_id:str,command:DeepSeekQuestion):
        return deepseek.start(request_id,command)

    @app.post('/api/data/requests/{request_id}/codex', status_code=202)
    def codex_start(request_id: str, command: CodexQuestion):
        return codex.start(request_id, command)

    @app.post('/api/data/runs/{run_id}/cancel')
    def codex_cancel(run_id: str):
        run=evidence.get('retrieval_runs',run_id)
        return deepseek.cancel(run_id) if run['backend']=='DEEPSEEK' else codex.cancel(run_id)
    verifications=IndependentVerifications(evidence)
    app.state.verifications=verifications

    @app.post('/api/data/verifications',status_code=201)
    def verify_review_evidence(command:VerificationCommand):
        return research.market_input_exposed(verifications.create(command),'verification-create')

    @app.get('/api/data/verifications')
    def verification_history():
        return research.market_input_exposed(verifications.history(),'verification-history')

    @app.get('/api/data/verifications/{verification_id}')
    def verification(verification_id:str):
        return research.market_input_exposed(verifications.get(verification_id),'verification-query')

    @app.post('/api/data/verifications/{verification_id}/replay')
    def verification_replay(verification_id:str):
        return research.market_input_exposed(verifications.replay(verification_id),'verification-replay')
    reviews.resolutions=resolutions

    @app.post('/api/data/requests/{request_id}/resolve',status_code=202)
    def data_resolve(request_id:str,command:ResolutionCommand):
        return resolutions.start(request_id,command)

    @app.get('/api/data/resolutions')
    def data_resolutions():
        return resolutions.history()

    @app.get('/api/data/resolutions/{resolution_id}')
    def data_resolution(resolution_id:str):
        return research.market_input_exposed(resolutions.get(resolution_id),'resolution')

    @app.get('/api/data/dependencies')
    def data_dependencies(resolution_id:str|None=None):
        return resolutions.dependencies(resolution_id)

    @app.post('/api/data/resolutions/{resolution_id}/replay')
    def replay_resolution(resolution_id:str):
        return research.market_input_exposed(resolutions.replay(resolution_id),'resolution-replay')

    @app.get('/api/data/replays/{replay_id}')
    def data_resolution_replay(replay_id:str):
        return research.market_input_exposed(evidence.get('source_resolution_replays',replay_id),'resolution-replay-query')

    @app.get('/api/data/sources')
    def data_sources():
        return REGISTRY+[p for p in prospective.sources.listing() if p['engine']=='CNEQUITY']

    @app.get('/api/data/runs')
    def data_runs():
        with ledger.connection() as db:
            import json
            return [json.loads(row[0]) for row in db.execute('SELECT value FROM retrieval_runs ORDER BY rowid DESC LIMIT 100')]

    @app.get('/api/data/snapshots')
    def data_snapshots(instrument:str|None=None,group:str|None=None,available_before:datetime|None=None):
        return research.market_input_exposed(evidence.snapshots(instrument,group,available_before),'snapshots-query')

    @app.get('/api/data/coverage')
    def data_coverage(instrument:str|None=None,group:str|None=None):
        return evidence.coverage(instrument,group)

    @app.get('/api/data/observations')
    def data_observations(instrument:str|None=None):
        return research.market_input_exposed([{**observation,'snapshot_id':snapshot['snapshot_id'],'run_id':snapshot['run_id'],
            'dependency_status':'INVALIDATED' if resolutions.dependencies(target_id=observation['observation_id']) else 'CURRENT'}
            for snapshot in evidence.snapshots(instrument) for observation in snapshot['observations']
            if not instrument or observation['instrument']==instrument],'observations-query')

    @app.post('/api/data/requests',status_code=201)
    def data_request(command:DataRequest):
        return evidence.request(command)

    @app.get('/api/data/requests/{request_id}')
    def get_data_request(request_id:str):
        return evidence.get('data_requests',request_id)

    @app.post('/api/data/requests/{request_id}/retrieve')
    def data_retrieve(request_id:str):
        return research.market_input_exposed(evidence.retrieve(request_id),'direct-retrieval')

    @app.get('/api/data/runs/{run_id}')
    def data_run(run_id:str):
        return evidence.get('retrieval_runs',run_id)

    @app.get('/api/data/snapshots/{snapshot_id}')
    def data_snapshot(snapshot_id:str):
        return research.market_input_exposed(evidence.get('market_evidence_snapshots',snapshot_id),'snapshot-query')

    @app.get('/api/data/archives/{sha}')
    def data_archive(sha:str):
        path=evidence.raw(sha)
        research.archive_exposed(sha)
        return FileResponse(path,media_type='application/octet-stream',filename=path.name,headers={'X-Content-Type-Options':'nosniff'})

    @app.post('/api/data/runs/{run_id}/replay')
    def data_replay(run_id:str):
        return research.market_input_exposed(evidence.replay(run_id),'run-replay')

    @app.get('/api/market/list')
    def market_list():
        return market.listing()

    @app.get('/api/market/list/versions/{version}')
    def market_version(version: int):
        return market.listing(version)

    @app.post('/api/market/watch')
    def market_watch(command: WatchCommand):
        return market.watch(command)

    @app.post('/api/market/identities')
    def market_identity(command: IdentityCommand):
        return market.identify(command)

    @app.post('/api/market/scope/check')
    def market_scope(command: ScopeCommand):
        return market.check_scope(command)

    @app.get('/api/market/history')
    def market_history():
        return market.history()

    @app.get('/api/market/calendar')
    def market_calendar(exchange: str, on: date = Query(alias='date'), at: datetime | None = None):
        result = market.rules.calendar(exchange, on, at)
        result['next_trading_day'] = market.rules.next_trading_day(exchange, on) if result['coverage'] != 'UNKNOWN' else None
        return result

    @app.get('/api/market/rules')
    def market_rules(exchange: str, board: str, instrument_type: str = 'STOCK', on: date | None = Query(None, alias='date')):
        return market.rules.rule(exchange, board, instrument_type, on)

    @app.get('/api/market/resale-date')
    def resale_date(exchange: str, board: str, buy_date: date, instrument_type: str = 'STOCK'):
        rule = market.rules.rule(exchange, board, instrument_type, buy_date)
        calendar = market.rules.calendar(exchange, buy_date)
        allowed = rule['implementation_status'] == 'ADAPTED' and calendar['is_trading_day'] is True
        return {'buy_date': buy_date.isoformat(), 'earliest_sell_date': market.rules.next_trading_day(exchange, buy_date) if allowed else None,
                'rule': rule, 'calendar': calendar, 'resale_source': market.rules.source('szse-a-share-resale'),
                'limitation': '最早日期不代表实际可卖数量或可成交，停牌/当前状态与账户事实须另核对'}

    @app.get('/api/market/sources')
    def market_sources():
        return list(market.rules.sources.values())

    @app.get('/api/market/sources/{source_id}/raw')
    def market_source_raw(source_id: str):
        source = market.rules.source(source_id)
        return FileResponse(market.rules.directory / source['archive_path'], media_type='application/octet-stream', filename=source['file'],headers={'X-Content-Type-Options':'nosniff'})
    funding = Funding(ledger)
    broker_costs = BrokerCosts(ledger, funding, evidence)

    @app.post('/api/actions/broker-costs/confirm', status_code=201)
    def confirm_broker_costs(command: BrokerCostConfirmation):
        return broker_costs.confirm(command)

    @app.get('/api/actions/broker-costs')
    def current_broker_costs():
        return broker_costs.listing()

    @app.get('/api/actions/broker-costs/versions/{version}')
    def broker_cost_version(version: int):
        return broker_costs.get(version)

    @app.post('/api/actions/broker-costs/estimate')
    def estimate_broker_costs(command: BrokerCostEstimate):
        return broker_costs.preview(command)

    if os.environ.get("ROLL_ENV") == "test":
        @app.post("/api/testing/funding-loss-samples")
        def loss_sample(command: LossSample):
            return funding.sample(command)

        @app.get("/api/testing/funding-loss-samples/{series_id}")
        def loss_samples(series_id: str):
            return funding.samples(series_id)

    @app.get("/api/funding")
    def current_funding():
        return funding.current()

    @app.get("/api/funding/versions/{version}")
    def funding_version(version: int):
        return funding.current(version)

    @app.post("/api/funding/confirm")
    def confirm_funding(command: FundingConfirmation):
        return funding.confirm(command)

    @app.get("/api/capabilities")
    def current_capabilities():
        recovery=app.state.backups.recovery()
        return capability_service.current()

    capability_service = Capabilities(ledger, funding, technical_reviews, valuations, capability_method_file, lambda: app.state.backups.recovery())
    app.state.capabilities = capability_service
    reviews.capabilities = capability_service
    capability_service.observation_reviews = reviews

    @app.post('/api/capabilities/grants', status_code=201)
    def grant_capability(command: GrantCommand):
        return capability_service.grant(command)

    @app.get('/api/capabilities/proposal')
    def capability_proposal(material_id: str, review_run_id: str):
        return capability_service.proposal(material_id, review_run_id)

    @app.get('/api/capabilities/grants')
    def capability_grants():
        return capability_service.grants()

    @app.get('/api/capabilities/grants/{grant_id}/status')
    def capability_grant_status(grant_id: str):
        return capability_service.current(grant_id=grant_id)

    @app.get('/api/capabilities/events')
    def capability_events():
        return capability_service.events()

    @app.get('/api/capabilities/proofs')
    def capability_proofs():
        return capability_service.proofs()

    @app.get('/api/capabilities/proofs/{proof_id}/check')
    def capability_proof_check(proof_id: str):
        return capability_service.verify_proof(proof_id)

    actions = Actions(ledger, funding, capability_service, evidence, shadow, risk_policies, valuations)
    actions.broker_costs = broker_costs
    capability_service.actions = actions
    from roll.decisions.notifications import Notifications, ReadNotice
    from roll.runtime.notification_channel import NotificationChannel
    notification_channel = NotificationChannel(Path(ledger.path).parent, notification_transport)
    app.state.notification_channel = notification_channel
    notifications = Notifications(ledger, capability_service, notification_channel)
    app.state.notifications = notifications
    capability_service.notifications = notifications
    actions.notifications = notifications
    reviews.notifications = notifications

    @app.get('/api/notification-channel')
    def channel_configuration(): return notification_channel.get()

    @app.post('/api/notification-channel')
    async def channel_configuration_update(request: Request):
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 16384: raise HTTPException(413, 'CHANNEL_CONFIG_TOO_LARGE')
        try:
            import json
            command = json.loads(raw)
        except (ValueError, UnicodeError): raise HTTPException(422, 'CHANNEL_CONFIG_INVALID') from None
        return notification_channel.save(command)

    @app.get('/api/notifications')
    def notification_list(): return notifications.listing()

    @app.get('/api/notifications/audit')
    def notification_audit(): return notifications.audit()

    @app.get('/api/notifications/time-chain')
    def notification_time_chain(decision_id: str, evaluation_id: str, intent_id: str | None = None):
        return notifications.time_chain(decision_id, evaluation_id, intent_id)

    @app.get('/api/notifications/{identifier}/current')
    def notification_current(identifier: str): return notifications.current(identifier)

    @app.post('/api/notifications/{identifier}/read')
    def notification_read(identifier: str, command: ReadNotice): return notifications.read(identifier, command)

    @app.post('/api/notifications/{identifier}/retry')
    def notification_retry(identifier: str, command: ReadNotice): return notifications.retry(identifier, command)
    from roll.decisions.recovery import AuthorizationRecovery, RecoveryCommand
    authorization_recovery = AuthorizationRecovery(capability_service)
    app.state.authorization_recovery = authorization_recovery

    @app.get('/api/capabilities/recovery')
    def capability_recovery(): return authorization_recovery.status()

    @app.post('/api/capabilities/recovery', status_code=201)
    def capability_recovery_check(command: RecoveryCommand): return authorization_recovery.check(command)

    @app.get('/api/capabilities/lifecycle')
    def capability_lifecycle(): return capability_service.lifecycle()

    @app.post('/api/capabilities/lifecycle')
    def capability_lifecycle_change(command: LifecycleCommand): return capability_service.change_lifecycle(command)
    app.state.actions = actions
    reviews.actions = actions
    from roll.decisions.intents import Intents, PrepareIntent, DeclareIntent
    intents = Intents(ledger, actions)
    app.state.intents = intents
    ledger.execution_intents = intents
    actions.execution_intents = intents
    from roll.decisions.monitoring import Monitoring, MonitoringCommand, CorrectionCommand
    monitoring = Monitoring(capability_service, validation, forward, intents)
    capability_service.monitoring = monitoring
    app.state.monitoring = monitoring
    reviews.monitoring = monitoring
    from roll.research.reports import ResearchReports
    reports = ResearchReports(shadow, valuations, intents, notifications, monitoring)
    app.state.reports = reports
    reviews.reports = reports

    @app.get('/api/research/reports/{freeze_id}')
    def research_report(freeze_id: str, valuation_id: str | None = None, decision_id: str | None = None,
                        evaluation_id: str | None = None, intent_id: str | None = None, monitoring_check_id: str | None = None):
        return reports.get(freeze_id, valuation_id, decision_id, evaluation_id, intent_id, monitoring_check_id)

    @app.get('/api/research/reports/{freeze_id}/export')
    def research_report_export(freeze_id: str, valuation_id: str | None = None, decision_id: str | None = None,
                               evaluation_id: str | None = None, intent_id: str | None = None,
                               monitoring_check_id: str | None = None,
                               format: str = Query('json', pattern='^(json|text)$')):
        value = reports.get(freeze_id, valuation_id, decision_id, evaluation_id, intent_id, monitoring_check_id)
        content = reports.text(value) if format == 'text' else __import__('json').dumps(value, ensure_ascii=False, sort_keys=True)
        return Response(content, media_type='text/plain' if format == 'text' else 'application/json',
                        headers={'Content-Disposition': 'attachment; filename="roll-research-report.' + ('txt' if format == 'text' else 'json') + '"'})

    @app.get('/api/capabilities/corrections')
    def capability_corrections(): return monitoring.corrections()

    @app.post('/api/capabilities/corrections', status_code=201)
    def capability_correction(command: CorrectionCommand): return monitoring.record_correction(command)

    @app.get('/api/capabilities/monitoring')
    def capability_monitoring_records(): return monitoring.records()

    @app.post('/api/capabilities/monitoring/check', status_code=201)
    def capability_monitoring_check(command: MonitoringCommand): return monitoring.check(command)

    @app.get('/api/capabilities/monitoring/{check_id}')
    def capability_monitoring_record(check_id: str): return monitoring.get(check_id)

    @app.post('/api/capabilities/monitoring/{check_id}/replay')
    def capability_monitoring_replay(check_id: str): return monitoring.replay(check_id)
    reviews.intents = intents

    @app.post('/api/intents/prepare', status_code=201)
    def prepare_intent(command: PrepareIntent):
        return intents.prepare(command)

    @app.get('/api/intents')
    def execution_intents():
        return intents.listing()

    @app.post('/api/intents/{intent_id}/declare')
    def declare_intent(intent_id: str, command: DeclareIntent):
        return intents.declare(intent_id, command)

    @app.get('/api/intents/allocations')
    def intent_allocations():
        return intents.allocations()

    @app.get('/api/intents/audit')
    def intent_audit():
        return intents.metrics()

    @app.post('/api/actions/evaluate', status_code=201)
    def evaluate_actions(command: EvaluationCommand):
        return actions.evaluate(command)

    @app.get('/api/actions/current')
    def current_actions(instrument: str | None = None):
        return actions.current(instrument)

    @app.get('/api/actions/evaluations/{evaluation_id}')
    def action_evaluation(evaluation_id: str):
        return actions.get(evaluation_id)

    @app.post('/api/actions/evaluations/{evaluation_id}/replay')
    def action_replay(evaluation_id: str):
        return actions.replay(evaluation_id)

    @app.get('/api/actions/events')
    def action_events():
        return actions.events()

    @app.get('/api/actions/audit')
    def action_audit():
        return actions.metrics()

    @app.post("/api/formal/evaluate")
    @app.post("/api/formal/probability")
    def formal_closed():
        if app.state.backups.recovery()["state"]=="RECOVERY_LOCK":raise HTTPException(403,{"code":"RECOVERY_LOCK","reason":"恢复后账户、当前授权和撤回尚未核实，仅可观察。"})
        raise HTTPException(403, {"code": "TECHNICAL_CAPABILITY_UNGRANTED", "reason": capabilities()["reason"]})

    @app.get("/api/runtime/health")
    def runtime_health():
        ledger.account()
        return {"service": "RUNNING", "storage": "READABLE", "market": "FINITE_REQUEST_ADAPTER_AVAILABLE",
                "backend": "NOT_CONFIGURED", "reason": "本机账户与有限市场取证接口在线；实际覆盖、缺口及时效逐请求核对，模型接入尚未配置"}

    @app.get("/api/health")
    def health():
        return {"status": "ok","runtime_role":runtime_role,"environment":"test" if os.environ.get("ROLL_ENV")=="test" else "local"}

    @app.post("/api/account/use-check")
    def account_use(command:UseCheck):
        from roll.accounts.ledger import timestamp
        return use_check(ledger.account(),ledger.pending_drafts(),command,timestamp,ledger.events())

    @app.get("/api/account")
    def account():
        account=ledger.account()
        account["state"],reasons=consistency(account,ledger.pending_drafts())
        if reasons:account["state_reasons"]=reasons
        return account

    @app.get("/api/account/versions/{version}")
    def version(version: int):
        return ledger.account(version)

    @app.get("/api/account/as-of")
    def as_of(known_by: datetime | None = None, effective_at: datetime | None = None):
        from roll.accounts.ledger import timestamp,now
        known=timestamp(known_by.isoformat(),"known_by") if known_by else now()
        effective=timestamp(effective_at.isoformat()) if effective_at else now()
        return {"known_by":known,"effective_at":effective,"account":ledger.replay(known_by=known,effective_at=effective),"limitation":"按当时已知与实际发生时点重建；已发布版本仍由原版本查询"}

    @app.post("/api/account/drafts", status_code=201)
    def draft(command: DraftCommand):
        if command.kind == "CSV_BATCH":
            raise HTTPException(422, "CSV 整批草稿只接受原文件上传，不接受外部生成的批命令")
        return ledger.draft(command)

    @app.get("/api/account/drafts/{draft_id}")
    def get_draft(draft_id: str):
        return ledger.get_draft(draft_id)

    @app.post("/api/account/confirm")
    def confirm(command: ConfirmCommand):
        return ledger.confirm(command)

    @app.get("/api/account/receipts/{receipt_id}")
    def receipt(receipt_id: str):
        return ledger.receipt(receipt_id)

    @app.get("/api/account/events")
    def events():
        return ledger.events()

    @app.get("/api/account/correction-candidates")
    def correction_candidates():
        history=ledger.events()
        active,chain,heads=active_events(history)
        candidates=[]
        for root,head in heads.items():
            original=next(e for e in history if e["event_id"]==root)
            if original["event_type"] in {"INITIAL_CASH","INITIAL_POSITION"}:continue
            fact=next((e for e in active if e.get("root_event_id",e.get("event_id"))==root),original)
            candidates.append({"root_event_id":root,"target_event_id":head,"reversed":not any(e.get("root_event_id",e.get("event_id"))==root for e in active),"command":fact_command(fact)})
        return candidates

    @app.get("/api/account/audit")
    def audit():
        return ledger.audit()

    @app.get("/api/account/replay")
    def replay():
        return ledger.replay()

    @app.get("/api/account/quarantined-drafts")
    def quarantined_drafts():
        return ledger.quarantined_drafts()

    @app.get("/api/account/pending-drafts")
    def pending_drafts():
        return ledger.pending_drafts()

    @app.post("/api/account/equity-hints",status_code=201)
    def equity_hint(command: EquityHint):
        return ledger.equity_hint(command)

    @app.get("/api/account/equity-hints")
    def equity_hints():
        return ledger.equity_hints()

    @app.get("/api/today")
    def today():
        account = ledger.account()
        account["state"],reasons=consistency(account,ledger.pending_drafts())
        if reasons:account["state_reasons"]=reasons
        pending = list(reasons)
        for position in account["positions"]:
            if position["sellable_quantity"] is None:
                pending.append(f"{position['instrument']} 可卖数量未知")
        for field, label in [("broker_available", "券商可用资金"), ("broker_frozen", "冻结资金")]:
            if account[field] is None:
                pending.append(f"{label}未知")
        if not account["permission_profile"] or any(p["status"] == "UNKNOWN" for p in account["permission_profile"]):
            pending.append("账户部分交易权限未知，未登记范围也按未知处理")
        for record in account.get("fees_pending",[]):
            pending.append(f"成交 {record} 费用暂估，现金与净收益待核")
        if ledger.quarantined_drafts():
            account["state"]="RECONCILE_REQUIRED"
            if any(d["command"]["kind"] in {"FILL","FEE_ADJUSTMENT"} for d in ledger.quarantined_drafts()):
                pending.append("成交输入待核，原始材料已保留，尚未影响账面现金与持仓")
            if any(d["command"]["kind"] in EVENT_FIELDS for d in ledger.quarantined_drafts()):
                pending.append("资金或权益输入待核，原始材料已保留，尚未影响账面现金与持仓")
            if any(d["command"]["kind"] == "CSV_BATCH" for d in ledger.quarantined_drafts()):
                pending.append("CSV文件输入待核，原始材料已保留，尚未影响账面现金与持仓")
        pending.extend(account.get("latest_fill_facts",[]))
        for record in account.get("rights_fee_breakdown_pending",[]):
            pending.append(f"配股 {record} 费用分拆待核；实际总支付已确认，费用前损益未知")
        for item in account.get("pending_items",[]):
            if item["status"] in {"OPEN","PARTIAL"}:
                pending.append(f"{item['record_id']} {'应收' if item['flow_category']=='INVESTMENT_INCOME' else '应付'}待结算 {item['outstanding_amount']} 元")
        for hint in ledger.equity_hints():
            pending.append(f"外部权益线索待核：{hint['content']}；来源 {hint['source']}，获知于 {hint['learned_at']}，未确认个人账户实际发生")
        capability = capability_service.current()
        return {"account": account, "formal_judgment": capability['formal_judgment'], "pending_items": pending,
                "funding": funding.current(), "technical_capability": capability, "runtime_health": runtime_health(), "recovery": app.state.backups.recovery(), "current_actions": actions.current()}

    return app



def create_app(directory: Path | None = None, market_transport=None, market_clock=None, codex_worker: Path | None = None, deepseek_endpoint: str | None = None, review_clock=None, backup_clock=None, baostock_worker: Path | None = None,technical_review_method_file:Path|None=None,capability_method_file:Path|None=None,runtime_role:str|None=None,notification_transport=None):
    if capability_method_file is not None and os.environ.get('ROLL_ENV') != 'test':
        raise ValueError('CAPABILITY_METHOD_HOST_TEST_ONLY')
    if directory is None:
        load_runtime_environment()
    runtime_role=runtime_role or os.environ.get('ROLL_RUNTIME_ROLE') or ('IN_PROCESS' if directory is not None or os.environ.get('ROLL_ENV')=='test' else 'API')
    if runtime_role not in {'API','WORKER','IN_PROCESS'}:
        raise ValueError('INVALID_RUNTIME_ROLE')
    directory=directory or data_directory()
    backups,marker,previous=bootstrap(directory)
    if backup_clock:backups.clock=backup_clock
    try:
        if os.environ.get('ROLL_ENV')=='test' and os.environ.get('ROLL_TEST_BOOTSTRAP_FAULT')=='before_ddl':os._exit(87)
        app=_create_app(directory,market_transport,market_clock,codex_worker,deepseek_endpoint,review_clock,baostock_worker,technical_review_method_file,capability_method_file,runtime_role,notification_transport)
        if os.environ.get('ROLL_ENV')=='test' and os.environ.get('ROLL_TEST_BOOTSTRAP_FAULT')=='after_ddl':os._exit(87)
        if os.environ.get('ROLL_ENV')=='test' and os.environ.get('ROLL_TEST_BOOTSTRAP_FAULT')=='migration_failure':raise RuntimeError('TEST_INITIALIZATION_FAILURE')
        app.state.backups=backups;app.state.host_marker=marker
        backups.authorization_check=app.state.authorization_recovery.status
        app.state.forward.recovery=backups.recovery
        finish_bootstrap(backups)
    except BaseException:
        rollback_bootstrap(backups,marker,previous)
        raise

    @app.middleware('http')
    async def local_recovery_access(request:Request,call_next):
        if request.url.path.startswith(('/api/runtime/backups','/api/runtime/restores','/api/notification-channel')):
            import ipaddress
            from urllib.parse import urlparse
            host=request.client.host if request.client else ''
            local=host=='testclient'
            if not local:
                try:local=ipaddress.ip_address(host).is_loopback
                except ValueError:local=False
            origin=request.headers.get('origin')
            if not local or (origin and urlparse(origin).hostname not in {'localhost','127.0.0.1','::1'}):
                return JSONResponse(status_code=403,content={'detail':{'code':'LOCAL_RECOVERY_ACCESS_ONLY'}})
        return await call_next(request)

    @app.get('/api/runtime/backups/status')
    def backup_status():return backups.status()

    @app.get('/api/runtime/backups')
    def backup_list():return backups.list()

    @app.post('/api/runtime/backups',status_code=201)
    def create_backup():return backups.create()

    @app.post('/api/runtime/backups/check')
    def check_backup():return backups.check()

    @app.get('/api/runtime/backups/{identifier}/export')
    def export_backup(identifier:str):
        return Response(backups.export(identifier),media_type='application/zip',headers={'Content-Disposition':'attachment; filename="roll-recovery.zip"'})

    @app.post('/api/runtime/restores',status_code=202)
    async def stage_restore(request:Request):
        raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>256*1024*1024:raise HTTPException(413,'恢复包压缩大小最多256MiB')
        return await asyncio.to_thread(backups.stage_restore,bytes(raw))

    return app

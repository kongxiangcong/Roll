"""HTTP adapter for shared company records. No account authority is exposed."""
import base64
import binascii
from typing import Literal

from fastapi import APIRouter, Response, Query
from pydantic import Field

from .models import Command, CompanyCommand, MaterialCommand, FactCommand, ConflictResolution, ExistingSourceCommand, AnalysisCommand, ValuationCommand, OperatingValuationCommand
from .service import fail


class ResolveCommand(Command):
    query: str = Field(min_length=1, max_length=160)


class MaterialImport(MaterialCommand):
    content_base64: str = Field(min_length=1, max_length=24 * 1024 * 1024)


class CandidateSubmission(Command):
    candidate: dict


def router(research):
    routes = APIRouter(prefix='/api/company-research', tags=['company-research'])

    @routes.post('/companies', status_code=201)
    def register(command: CompanyCommand):
        return research.register(command)

    @routes.get('/companies')
    def companies(limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
        return research.companies(limit, offset)

    @routes.post('/resolve')
    def resolve(command: ResolveCommand):
        return research.resolve(command.query)

    @routes.get('/companies/{company_id}')
    def company(company_id: str):
        return research.company(company_id)

    @routes.post('/materials', status_code=201)
    def import_material(command: MaterialImport):
        try:
            content = base64.b64decode(command.content_base64, validate=True)
        except (ValueError, binascii.Error):
            fail('MATERIAL_ENCODING_INVALID', 'Material must contain valid base64 bytes')
        metadata = MaterialCommand(**command.model_dump(exclude={'content_base64'}))
        return research.import_material(metadata, content)

    @routes.post('/materials/from-source', status_code=201)
    def import_existing(command: ExistingSourceCommand):
        return research.import_existing(command)

    @routes.get('/companies/{company_id}/materials')
    def materials(company_id: str, purpose: Literal['DAILY', 'REPORT', 'CURRENT_RESEARCH'] = 'CURRENT_RESEARCH',
                  limit: int = Query(200, ge=1, le=200), offset: int = Query(0, ge=0)):
        return research.materials(company_id, purpose, limit, offset)

    @routes.get('/materials/{material_id}')
    def material(material_id: str):
        return research.material(material_id)

    @routes.get('/materials/{material_id}/original')
    def original(material_id: str):
        return Response(research.material_bytes(material_id), media_type='application/octet-stream',
                        headers={'X-Content-Type-Options': 'nosniff', 'Content-Disposition': 'attachment; filename="source-original.bin"'})

    @routes.post('/facts', status_code=201)
    def add_fact(command: FactCommand):
        return research.add_fact(command)

    @routes.get('/facts/{version_id}')
    def fact(version_id: str):
        return research.fact(version_id)

    @routes.get('/companies/{company_id}/facts')
    def facts(company_id: str, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0), fact_id: str | None = None):
        return research.facts(company_id, limit, offset, fact_id)

    @routes.post('/conflicts/resolutions', status_code=201)
    def resolve_conflict(command: ConflictResolution):
        return research.resolve_conflict(command)

    @routes.get('/companies/{company_id}/checks')
    def checks(company_id: str, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        return research.checks(company_id, limit, offset)

    @routes.post('/analysis/inputs', status_code=201)
    def freeze_analysis(command: AnalysisCommand):
        return research.freeze_analysis(command)

    @routes.get('/analysis/inputs/{input_id}')
    def analysis_input(input_id: str):
        return research.analysis_input(input_id)

    @routes.post('/analysis/inputs/{input_id}/candidates', status_code=201)
    def apply_candidate(input_id: str, command: CandidateSubmission):
        return research.apply_analysis_candidate(input_id, command.candidate)

    @routes.get('/analysis/inputs/{input_id}/candidates')
    def candidates(input_id: str, limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
        return research.analysis_candidates(input_id, limit, offset)

    @routes.post('/analysis/inputs/{input_id}/run')
    def run_analysis(input_id: str):
        return research.run_analysis(input_id)

    @routes.get('/analysis/runs/{run_id}')
    def analysis_run(run_id: str):
        return research.analysis_run(run_id)

    @routes.get('/hypotheses/{version_id}')
    def hypothesis(version_id: str):
        return research.operating_hypothesis(version_id)

    @routes.get('/snapshots/{snapshot_id}')
    def snapshot(snapshot_id: str, purpose: Literal['DAILY', 'REPORT'] = 'DAILY'):
        return research.analysis_snapshot(snapshot_id, purpose)

    @routes.get('/companies/{company_id}/snapshots')
    def snapshots(company_id: str, limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0)):
        return research.analysis_snapshots(company_id, limit, offset)

    @routes.post('/valuations', status_code=201)
    def calculate_valuation(command: ValuationCommand):
        return research.calculate_valuation(command)

    @routes.get('/valuation-inputs/{version_id}')
    def valuation_input(version_id: str):
        return research.valuation_input(version_id)

    @routes.get('/valuations/{valuation_id}')
    def valuation(valuation_id: str):
        return research.valuation(valuation_id)

    @routes.get('/valuations/{valuation_id}/presentation')
    def diagnostic_presentation(valuation_id: str, purpose: Literal['CURRENT_PRICING', 'BASELINE_RESEARCH'] = 'CURRENT_PRICING'):
        return research.valuation_presentation(valuation_id, purpose)

    @routes.get('/valuations/{valuation_id}/bundle')
    def valuation_bundle(valuation_id: str):
        return research.valuation_bundle(valuation_id)

    @routes.post('/valuations/{valuation_id}/replay')
    def replay_valuation(valuation_id: str):
        return research.replay_valuation(valuation_id)

    @routes.post('/operating-valuations', status_code=201)
    def operating_valuation(command: OperatingValuationCommand):
        return research.calculate_operating_valuation(command)

    @routes.get('/operating-models/{model_id}')
    def operating_model(model_id: str):
        return research.operating_model(model_id)

    @routes.get('/economic-reviews/{review_id}')
    def economic_review(review_id: str):
        return research.economic_review(review_id)

    @routes.get('/economic-reviews/{review_id}/presentation')
    def valuation_presentation(review_id: str, purpose: Literal['CURRENT_PRICING', 'BASELINE_RESEARCH'] = 'CURRENT_PRICING'):
        return research.valuation_presentation(review_id, purpose)

    return routes

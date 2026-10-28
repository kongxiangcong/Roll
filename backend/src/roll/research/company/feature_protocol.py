"""A supplement to an existing experiment, never a new budget or fit executor."""
import copy
import hashlib
import json
from pathlib import Path
from pydantic import Field
from .models import Command
from .service import fail, fingerprint

VERSION = 'company-feature-incremental-protocol-1'


class FeatureProtocolCommand(Command):
    company_ids: list[str] = Field(min_length=1, max_length=20)
    baseline_protocol_id: str | None = None
    baseline_model_id: str | None = None
    basis: str = Field(min_length=1, max_length=2000)
    idempotency_key: str = Field(min_length=1, max_length=128)


def design(research, command, definitions):
    companies = [research.company(i) for i in dict.fromkeys(command.company_ids)]
    gaps, baseline = [], None
    if bool(command.baseline_model_id) != bool(command.baseline_protocol_id):
        fail('BASELINE_BINDING_REQUIRED', 'Supply both original protocol and frozen model IDs, or leave both explicitly unbound')
    if command.baseline_model_id:
        with research.ledger.connection() as db:
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'research_protocols','research_models'} <= names:
                fail('BASELINE_NOT_FOUND', 'Original experiment and model metadata are not registered', 404)
            protocol = db.execute('SELECT value FROM research_protocols WHERE id=?', (command.baseline_protocol_id,)).fetchone()
            model = db.execute('SELECT value FROM research_models WHERE id=?', (command.baseline_model_id,)).fetchone()
        if not protocol or not model:
            fail('BASELINE_NOT_FOUND', 'Original experiment or frozen model is missing', 404)
        protocol, model = json.loads(protocol[0]), json.loads(model[0])
        if model['protocol_id'] != command.baseline_protocol_id:
            fail('BASELINE_BINDING_INVALID', 'Frozen model belongs to a different original experiment')
        if model.get('model_freeze_status') != 'FROZEN' or model.get('status') != 'RESEARCH_ARTIFACT_FROZEN':
            gaps.append('REAL_PRICE_VOLUME_BASELINE_NOT_FROZEN')
        actual = set(protocol.get('scope', {}).get('instruments', []))
        if not all(any(l['exchange']+':'+l['code'] in actual for l in company['listings']) for company in companies):
            gaps.append('BASELINE_COMPANY_LISTING_SCOPE_NOT_COVERED')
        baseline = dict(protocol_id=command.baseline_protocol_id, protocol_sha256=fingerprint(protocol),
            model_id=command.baseline_model_id, model_metadata_sha256=fingerprint(model),
            model_artifact=copy.deepcopy(model.get('model_artifact')), design=copy.deepcopy(protocol['design']))
    else:
        gaps.append('ORIGINAL_FROZEN_PRICE_VOLUME_BASELINE_AND_PROTOCOL_UNBOUND')
    source = Path(__file__).parents[1]/'design.py'
    inherited = baseline['design'] if baseline else {}
    result = dict(version=VERSION, feature_definition_version=definitions['version'],
        hypothesis='Source-timed operating candidates may add information to the SAME frozen price-volume baseline; no improvement assumed',
        event=inherited.get('event', 'Bind original frozen positive20-session RAW round-trip net-return label; unresolved outcomes remain missing'),
        horizon_sessions=inherited.get('horizon_sessions',20),
        baseline=baseline, baseline_required='ORIGINAL_FROZEN_PRICE_VOLUME_MODEL_AND_EXISTING_FAMILY',
        feature_fields=list(definitions['definitions']), variants=['FROZEN_BASELINE','BASELINE_PLUS_FIXED_COMPANY_CANDIDATES'],
        same_sample_controls='Identical company/date/label/cost/execution cohort and timestamps; retain missing indicators; no selective complete-case deletion or stock/date search',
        time_out_windows=dict(inherit=copy.deepcopy(inherited.get('windows')), rule='Chronological development/calibration/out-of-time windows fixed BEFORE any labels;20-session purge and embargo; no shuffled split; unbound windows prohibit execution'),
        scores=['BRIER','LOG_LOSS','CALIBRATION'],
        scoring=dict(brier='mean((p-y)^2)', log_loss='-mean(y*log(p)+(1-y)*log(1-p)); same predeclared numerical clipping as baseline',
            calibration='Fixed five equal-width reliability bins; disclose support/uncertainty; missing outcomes are not negatives',
            comparison='Paired same-sample differences versus original frozen baseline and development base rate; cluster dependent overlapping events and issuer disclosure roots'),
        costs=dict(inherit=copy.deepcopy(inherited.get('costs')), rule='Same source-bound historical statutory/broker/slippage/corporate-action treatment as baseline; unknown is not zero; report fees and turnover'),
        risk_exposure_controls='Matched gross/net/industry/size/beta exposures, drawdown and turnover; separate timing from sector/exposure effects, no unqualified excess-return claim',
        maturity=dict(minimum_independent_mature_events=200, minimum_per_occupied_reliability_bin=20,
            label_rule='Only actual completed20-session outcomes under identical frozen event; later revisions cannot alter historical features',
            independence='Issuer/origin-root/reporting-period clusters; repeated quarterly reports/dailies/A-H listings do not add independent operating evidence'),
        stopping=dict(inherited=copy.deepcopy(inherited.get('stopping')), budget='Existing family residual budget INCLUDING prior failed/aborted attempts and reservations; NEVER reset or allocate here',
            no_new_fit_without='Explicit fitting authorization AND frozen fully bound supplement AND unchanged original family budget gates',
            evidence_deadline='Inherit original calendar deadline, never restart it for this entry',
            hard_stop=['PIT leakage','blocked valuation numeric leakage','corrupt references','budget exhausted','SEALED access attempted'],
            insufficient='INCONCLUSIVE at insufficient support/deadline; preserve all failures, no retuning/search to obtain PASS'),
        frozen_design_source=dict(path='research/design.py',sha256=hashlib.sha256(source.read_bytes()).hexdigest()),
        authority='SUPPLEMENT_ONLY_NOT_AN_EXECUTOR_OR_NEW_EXPERIMENT_FAMILY')
    return result, gaps

"""Daily presentation of one shared snapshot; never an independent valuation."""
from roll.accounts.ledger import now
import json
from .service import fail, record, verified, fingerprint
from .models import ChangeSetCommand, CheckCommand, AnalysisCommand, ExistingSourceCommand


def recent_checks(research, company_id):
    first = research.checks(company_id, limit=20)
    return research.checks(company_id, limit=20, offset=first['total']-20)['attempts'] if first['total']>20 else first['attempts']


def archive_failures(research, company_id):
    with research.ledger.connection() as db:
        selection = '''SELECT DISTINCT json_extract(error.value,'$.source_type') AS source_type,
            json_extract(error.value,'$.record_id') AS record_id FROM company_research_checks c,json_each(c.value,'$.errors') error
            WHERE c.company_id=? AND json_extract(error.value,'$.record_id') IS NOT NULL
            AND NOT EXISTS(SELECT 1 FROM company_research_checks good,json_each(good.value,'$.source_receipts') receipt
                WHERE good.company_id=c.company_id AND json_extract(receipt.value,'$.record_id')=json_extract(error.value,'$.record_id')
                AND json_extract(receipt.value,'$.source_type')=json_extract(error.value,'$.source_type'))'''
        count = db.execute('SELECT count(*) FROM ('+selection+')', (company_id,)).fetchone()[0]
        examples = [dict(source_type=row[0],record_id=row[1]) for row in db.execute(selection+' LIMIT 20',(company_id,))]
    return dict(unresolved_record_count=count, examples=examples,
        meaning='默认下一批跳过已失败/拒绝记录以继续处理新材料；原缺口未消除，修正来源或身份依据后可显式重查')


def archive_supplier(research, company_id, retry_rejected=False):
    """Read bounded existing source records. This is explicitly NOT a public-source check."""
    instruments = {i['listing_id'] for i in research.company(company_id)['listings']}
    def supply(category):
        table, source_type = {'NEWS_NEXT20_UNIMPORTED': ('news_facts', 'NEWS_FACT'), 'FINANCIAL_NEXT20_UNIMPORTED': ('financial_income_facts', 'FINANCIAL_FACT')}[category]
        with research.ledger.connection() as db:
            if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                return []
            placeholders = ','.join('?' for _ in instruments)
            rows = db.execute(f'''SELECT id,value FROM {table} src WHERE instrument IN ({placeholders})
                AND NOT EXISTS(SELECT 1 FROM company_research_materials m WHERE m.company_id=?
                    AND json_extract(m.value,'$.upstream.source_type')=? AND json_extract(m.value,'$.upstream.record_id')=src.id)
                AND NOT EXISTS(SELECT 1 FROM company_research_checks c,json_each(c.value,'$.source_receipts') receipt
                    WHERE c.company_id=? AND json_extract(receipt.value,'$.source_type')=? AND json_extract(receipt.value,'$.record_id')=src.id)
                AND (? OR NOT EXISTS(SELECT 1 FROM company_research_checks c,json_each(c.value,'$.errors') rejection
                    WHERE c.company_id=? AND json_extract(rejection.value,'$.source_type')=? AND json_extract(rejection.value,'$.record_id')=src.id
                    ))
                ORDER BY rowid LIMIT 20''', (*sorted(instruments), company_id, source_type, company_id, source_type, retry_rejected, company_id, source_type)).fetchall()
        return [ExistingSourceCommand(company_id=company_id, source_type=source_type, record_id=row[0]) for row in rows]
    return supply


def refresh_daily(research, company_id, key, supplier=None, retry_rejected=False):
    """Archive check + frozen analysis input. Model execution is a separate worker phase."""
    research.company(company_id)
    scope = 'daily-update:' + company_id
    request = dict(company_id=company_id, archive_categories=['FINANCIAL_NEXT20_UNIMPORTED', 'NEWS_NEXT20_UNIMPORTED'], retry_rejected=retry_rejected)
    with research.ledger.connection() as db:
        prior = db.execute('SELECT result,request_hash FROM company_research_commands WHERE scope=? AND key=?', (scope, key)).fetchone()
    if prior:
        if prior[1] != fingerprint(request):
            fail('IDEMPOTENCY_CONFLICT', 'Daily key was used with different retry scope', 409)
        return verified(json.loads(prior[0]))
    check = research.check_source(CheckCommand(company_id=company_id, source_id='saved-archive-catalog',
        requested_scopes=request['archive_categories'], idempotency_key=key), supplier or archive_supplier(research, company_id, retry_rejected))
    from .financial_facts import adapt_financial_fields, pending_materials
    pending,pending_count = pending_materials(research, company_id, retry_rejected)
    adaptation = adapt_financial_fields(research, company_id, pending, key)
    adaptation.update(batch_material_count=len(pending),pending_before_count=pending_count)
    with research.ledger.connection() as db:
        snapshot = research.analysis.latest(company_id, db)
        rows = [verified(json.loads(r[0])) for r in db.execute('SELECT value FROM company_research_facts WHERE company_id=? ORDER BY rowid', (company_id,))]
    superseded = {f['supersedes'] for f in rows if f['supersedes']}
    ids = [f['version_id'] for f in rows if f['version_id'] not in superseded]
    old_ids = set(snapshot['fact_version_ids']) if snapshot else set()
    input_id, gap = None, None
    # Unstructured new materials remain explicit evidence gaps until facts are extracted.
    # A metadata-only catalog change cannot silently modify an operating hypothesis.
    if set(ids) != old_ids and ids:
        if len(ids) > 80:
            gap = 'ANALYSIS_FACT_BOUND_EXCEEDED_NARROW_SCOPE'
        else:
            packet = research.freeze_analysis(AnalysisCommand(company_id=company_id, as_of=now(), fact_version_ids=ids,
                parent_snapshot_id=snapshot['snapshot_id'] if snapshot else None))
            input_id = packet['input_id']
    if check['new_material_count'] and not input_id and gap is None:
        gap = 'NEW_ARCHIVED_MATERIAL_REQUIRES_SOURCED_FACT_EXTRACTION'
    result = record(dict(company_id=company_id, check=check, snapshot_id=snapshot['snapshot_id'] if snapshot else None,
        financial_adaptation=adaptation,
        archive_failures=archive_failures(research, company_id),
        analysis_input_id=input_id, model_executed=False, network_check_performed=False,
        archive_scope='检查已归档财务/新闻材料的下一批未纳入记录（每类最多20条，默认跳过已失败/拒绝记录，原缺口未消除；非完整历史核查）；未执行公网核查', gap=gap,
        status='ANALYSIS_READY' if input_id else 'SOURCE_FAILED' if check['status']=='FAILED' else 'SAME_SNAPSHOT'))
    with research.transaction() as db:
        prior = db.execute('SELECT result FROM company_research_commands WHERE scope=? AND key=?', (scope, key)).fetchone()
        if prior:
            return verified(json.loads(prior[0]))
        research.save_command(db, scope, key, request, result)
    return result


def daily_view(research, company_id, snapshot_id=None):
    from .financial_facts import adaptation_state
    company = research.company(company_id)
    if snapshot_id:
        snapshot = research.analysis_snapshot(snapshot_id)
        if snapshot['company_id'] != company_id:
            fail('CROSS_COMPANY_REFERENCE', 'Daily view requires the selected company snapshot')
    else:
        with research.ledger.connection() as db:
            snapshot = research.analysis.latest(company_id, db)
    missing = dict(status='UNAVAILABLE', scenarios=[], reason='尚无固定且通过适用性检查的估值；其余经营研究继续展示')
    unavailable = dict(status='NOT_COMPARABLE', reason='尚无两个明确的共享快照或可比报价')
    changes = {k: dict(unavailable) for k in ['OPERATING_EVIDENCE', 'PRICE', 'VALUATION_ASSUMPTION_OR_METHOD']}
    if not snapshot:
        return dict(company=company, snapshot=None, attention_reasons=[], catalysts=[], risks=[],
                    valuation=missing, changes=changes, information_state=None, change_set_id=None,
                    latest_checks=recent_checks(research, company_id),
                    archive_failures=archive_failures(research, company_id),
                    financial_adaptation_state=adaptation_state(research, company_id),
                    gap='尚无共享分析快照；先取得可追溯资料并完成经营分析')
    reviews = snapshot.get('economic_review_ids', [])
    presentation = research.valuation_presentation(reviews[0], 'CURRENT_PRICING') if len(reviews) == 1 else missing
    change = None
    if snapshot['parent_snapshot_id']:
        change = research.compare_snapshots(ChangeSetCommand(old_snapshot_id=snapshot['parent_snapshot_id'],
            new_snapshot_id=snapshot['snapshot_id'], idempotency_key='daily:'+snapshot['snapshot_id']))
        changes = change['changes']
    core = snapshot['core']
    if not presentation.get('usable_range'):
        # Raw diagnostic arithmetic remains at the explicit change-set endpoint.
        # It is never a quick current valuation or part of the model's price packet.
        changes = {**changes, **{k: {a: b for a, b in changes[k].items() if a in {'status', 'reason', 'changed', 'old_snapshot_id', 'new_snapshot_id'}}
            for k in ['PRICE', 'VALUATION_ASSUMPTION_OR_METHOD']}}
    return dict(company=company, snapshot=snapshot, attention_reasons=core['attention_reasons'],
                catalysts=[h['next_validation_event'] for h in core['hypotheses']],
                risks=[*[dict(**c, kind='COUNTEREVIDENCE_CLAIM', verified_fact=False) for c in core['counterevidence']], *[dict(text=c,
                    kind='INVALIDATION_CONDITION', verified_fact=False, hypothesis_version_id=h['version_id'], hypothesis_statement=h['statement'],
                    fact_version_ids=h['counter_fact_version_ids'])
                    for h in core['hypotheses'] for c in h['invalidation_conditions']]],
                valuation=presentation, changes=changes, change_set_id=change['change_set_id'] if change else None,
                information_state=research.changes.information(snapshot, now(), 604800),
                gap=core['valuation_unavailable_reason'],
                evidence=[research.material(i, company_id) for i in snapshot['material_ids']],
                facts=[research.fact(i, company_id) for i in snapshot['fact_version_ids']],
                conflicts=research.analysis_input(snapshot['input_id'])['payload']['conflicts'],
                latest_checks=recent_checks(research, company_id),
                archive_failures=archive_failures(research, company_id),
                financial_adaptation_state=adaptation_state(research, company_id),
                conflict_note='经营假设与量价辅助观点分别保留；方向、期限或依据不一致时并列解释，未经独立验证不合成为胜率')

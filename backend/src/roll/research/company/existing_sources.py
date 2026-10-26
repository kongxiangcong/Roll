"""Read existing source records; this adapter neither fetches nor rewrites them."""
import hashlib
import json

from roll.accounts.ledger import encode

from .models import MaterialCommand


def news_context(evidence, company, fact):
    from .service import fail
    from roll.market.news_events import associate, group_facts
    with evidence.ledger.connection() as db:
        identities = {}
        for instrument, raw in db.execute('SELECT instrument,identity FROM market_identities ORDER BY revision'):
            identity = json.loads(raw)
            identities[instrument] = {'instrument': instrument, 'name': identity.get('name'), 'code': identity.get('code')}
        facts = [json.loads(r[0]) for r in db.execute('SELECT value FROM news_facts WHERE instrument=? ORDER BY rowid', (fact['instrument'],))]
    identities.setdefault(fact['instrument'], {'instrument': fact['instrument'], 'name': company['legal_name'], 'code': fact['instrument'].split(':')[1]})
    associations = {f['fact_id']: associate(f, list(identities.values())) for f in facts}
    association = associations[fact['fact_id']]
    if association['classification'] not in {'COMPANY_SUBJECT', 'COMPANY_MENTIONED'}:
        fail('SOURCE_IDENTITY_UNCONFIRMED', 'Keyword search alone does not establish company evidence', association=association)
    memberships, events = group_facts(facts, associations)
    return {'association': association, 'event': memberships[fact['fact_id']],
            'body_status': fact.get('body_status'), 'errors': fact.get('errors', []),
            'body_received_at': fact.get('body_received_at'), 'list_received_at': fact.get('first_received_at')}


def material_source(evidence, company, command):
    from .service import fail
    tables = {'FINANCIAL_FACT': 'financial_income_facts', 'NEWS_FACT': 'news_facts',
              'MARKET_SNAPSHOT': 'market_evidence_snapshots'}
    table = tables[command.source_type]
    with evidence.ledger.connection() as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            fail('SOURCE_RECORD_NOT_FOUND', 'The source has no stored records', 404)
        row = db.execute(f'SELECT value FROM {table} WHERE id=?', (command.record_id,)).fetchone()
    if not row:
        fail('SOURCE_RECORD_NOT_FOUND', 'Source record does not exist', 404)
    source = json.loads(row[0])
    fact = source
    if command.source_type == 'MARKET_SNAPSHOT':
        if command.fact_index >= len(source.get('facts', [])):
            fail('SOURCE_RECORD_NOT_FOUND', 'Selected market fact does not exist', 404)
        fact = source['facts'][command.fact_index]
    elif command.fact_index != 0:
        fail('SOURCE_RECORD_NOT_FOUND', 'Only market snapshots have fact indexes', 404)
    listings = {i['listing_id'] for i in company['listings']}
    if fact.get('instrument') not in listings:
        fail('CROSS_COMPANY_REFERENCE', 'Existing source instrument does not belong to selected company')
    raw_sha = (fact.get('raw_sha256') if command.source_type == 'FINANCIAL_FACT' else
               fact.get('body_sha256') or fact.get('list_sha256') if command.source_type == 'NEWS_FACT' else fact.get('raw_hash'))
    if not raw_sha:
        fail('SOURCE_ORIGINAL_MISSING', 'Existing source has no registered original')
    original = evidence.raw(raw_sha).read_bytes()
    with evidence.ledger.connection() as db:
        archive = json.loads(db.execute('SELECT value FROM evidence_archives WHERE sha256=?', (raw_sha,)).fetchone()[0])
    source_id = fact.get('source_id') or 'existing-market'
    url = fact.get('source_url') or fact.get('url') or archive.get('source_url') or 'registered-source:' + raw_sha
    period_end = fact.get('report_period') or fact.get('trade_date')
    period_start = period_end
    if command.source_type == 'FINANCIAL_FACT':
        period_start = (period_end if fact.get('period_basis') == 'POINT_IN_TIME' else
                        period_end[:4] + '-01-01' if period_end and fact.get('period_basis') == 'YEAR_TO_DATE' else None)
    root = f"{source_id}:{fact['instrument']}:{fact.get('statement') or fact.get('group') or 'NEWS'}:{period_end or raw_sha}"
    limitations = ['SOURCE_RECORD_REUSED_NO_NEW_NETWORK_REQUEST', 'SOURCE_STRUCTURE_IS_NOT_FACTUAL_ENDORSEMENT']
    news = {}
    if command.source_type == 'NEWS_FACT':
        news = news_context(evidence, company, fact)
        root = 'news-event:' + news['event']['event_id']
        limitations.append('NEWS_ASSOCIATION_AND_PUBLICATION_PRECISION_RETAINED_IN_UPSTREAM')
    kind = 'PUBLIC_ACQUISITION' if source.get('evidence_kind') == 'REAL_ACQUISITION' else 'METHOD_CASE'
    metadata = MaterialCommand(company_id=company['company_id'], subject_name=company['legal_name'],
        source_id=source_id, origin_root_id=root, source_url=url,
        media_type='application/pdf' if archive['path'].endswith('.pdf') else 'application/octet-stream',
        period_start=period_start, period_end=period_end, disclosed_at=None,
        currency=fact.get('currency'), unit=None if (fact.get('unit') or fact.get('volume_unit')) == 'UNKNOWN' else fact.get('unit') or fact.get('volume_unit'),
        scope=None if fact.get('statement_scope') == 'UNKNOWN' else fact.get('statement_scope') or fact.get('group'), limitations=limitations)
    upstream = {'source_type': command.source_type, 'record_id': command.record_id, 'fact_index': command.fact_index,
                'source_record_sha256': hashlib.sha256(encode(source).encode()).hexdigest(),
                'original_received_at': (fact.get('body_received_at') if command.source_type == 'NEWS_FACT' and fact.get('body_sha256') else
                                         fact.get('first_received_at') or fact.get('received_at')),
                'original_available_at': fact.get('available_at'),
                'reported_publication': fact.get('reported_publication_date') or fact.get('reported_published_at') or fact.get('published_at'),
                'publication_precision': fact.get('publication_precision') or fact.get('time_precision') or 'UNKNOWN',
                'evidence_kind': source.get('evidence_kind'), 'raw_sha256': raw_sha,
                'statement': fact.get('statement'), 'period_basis': fact.get('period_basis'), **news}
    return metadata, original, kind, upstream

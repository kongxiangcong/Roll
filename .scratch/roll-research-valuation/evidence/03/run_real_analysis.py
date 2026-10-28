"""Real local original + bounded real CODEX attempt; never changes production data."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'backend' / 'src'))
from roll.accounts.ledger import Ledger, encode
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch, CompanyCommand, MaterialCommand, FactCommand, AnalysisCommand
from roll.runtime.backups import Backups
from pypdf import PdfReader

parser = argparse.ArgumentParser()
parser.add_argument('--source-pdf', required=True)
parser.add_argument('--data-directory', required=True)
parser.add_argument('--output-directory', required=True)
args = parser.parse_args()
out = Path(args.output_directory)
out.mkdir(parents=True, exist_ok=True)
source = Path(args.source_pdf)
original = source.read_bytes()
anchors = json.loads((Path(__file__).parent / 'source-excerpts.json').read_text(encoding='utf-8'))
assert hashlib.sha256(original).hexdigest() == anchors['source']['sha256']
reader = PdfReader(source)
assert '600362' in reader.pages[1].extract_text() and '江西铜业' in reader.pages[1].extract_text()
ledger = Ledger(Path(args.data_directory))
research = CompanyResearch(EvidenceStore(ledger, MarketDirectory(ledger)))
issuer = research.register(CompanyCommand(legal_name='江西铜业股份有限公司', aliases=['江西铜业'],
    jurisdiction='CN', accounting_standard='CAS', year_end='12-31', industry='NON_FINANCIAL',
    identity_basis='Issuer original identity PDF page 2; original SHA verified; PRC GAAP HKEX repost',
    listings=[dict(exchange='SSE', code='600362', share_class='A', currency='CNY'),
              dict(exchange='HKEX', code='00358', share_class='H', currency='HKD')]))
material = research.import_material(MaterialCommand(company_id=issuer['company_id'],
    source_id='issuer-hkex-2025-cas', origin_root_id='jiangxi-copper:2025:prc-gaap-annual',
    source_url=anchors['source']['url'], subject_name=issuer['legal_name'], media_type='application/pdf',
    period_start='2025-01-01', period_end='2025-12-31', disclosed_at=None, unit=None, currency=None, scope=None,
    limitations=['REAL_LOCAL_ORIGINAL_NOT_FRESH_NETWORK_ACQUISITION', 'PRECISE_DISCLOSURE_UNKNOWN_NOT_HISTORICAL_PIT',
        'PRC_GAAP_GROUP_FINANCIAL_SCOPE_NARRATIVE_NOT_INDIVIDUAL_AUDIT_ENDORSEMENT',
        'SELECTED_EXCERPTS_NOT_FULL_REPORT_REVIEW', 'INDUSTRIAL_TRADE_FINANCE_ASSOCIATES_NOT_A_COMPLETE_FCFF_BASIS']), original)
facts = []
for item in anchors['items']:
    for index, quote in enumerate(item['quotes']):
        text = quote['verbatim_text']
        assert text in reader.pages[quote['pdf_page_1based'] - 1].extract_text()
        assert hashlib.sha256(text.encode()).hexdigest() == quote['excerpt_sha256']
        facts.append(research.add_fact(FactCommand(company_id=issuer['company_id'], material_id=material['material_id'],
            metric=item['excerpt_id'] + ':' + str(index), business=item['topic'], value=text, value_type='TEXT',
            unit=None, currency=None, scope=item['source_scope'], period_start='2025-01-01', period_end='2025-12-31',
            page='PDF ' + str(quote['pdf_page_1based']) + '; printed ' + str(quote['printed_page']),
            table=quote['printed_page_namespace'], change_reason='Verbatim page excerpt; host exact substring and excerpt SHA check; not independent factual verification')))
prior_total = research.analysis_snapshots(issuer['company_id'], limit=1)['total']
parent = research.analysis_snapshots(issuer['company_id'], limit=1, offset=prior_total-1)['snapshots'][0] if prior_total else None
packet = research.freeze_analysis(AnalysisCommand(company_id=issuer['company_id'],
    parent_snapshot_id=parent['snapshot_id'] if parent else None,
    as_of=datetime.now(timezone.utc).isoformat(), fact_version_ids=[f['version_id'] for f in facts]))
(out / 'real-input.json').write_text(encode(packet), encoding='utf-8')
run = research.run_analysis(packet['input_id'])
(out / 'real-run.json').write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding='utf-8')
if run.get('candidate_output_archive'):
    raw = research.evidence.raw(run['candidate_output_archive']['sha256']).read_bytes()
    (out / 'real-output.raw').write_bytes(raw)
if run.get('snapshot_id'):
    saved = research.analysis_snapshot(run['snapshot_id'])
    (out / 'real-snapshot.json').write_text(encode(saved), encoding='utf-8')
    assert research.analysis_snapshot(saved['snapshot_id'], purpose='DAILY') == research.analysis_snapshot(saved['snapshot_id'], purpose='REPORT')
backup = Backups(Path(args.data_directory))
backup_saved = backup.create()
backup.export(backup_saved['backup_id'])
receipt = dict(kind='REAL_CODEX_OPERATING_ANALYSIS', data_directory=str(Path(args.data_directory).resolve()),
    source_sha256=anchors['source']['sha256'], material_id=material['material_id'], company_id=issuer['company_id'],
    input_id=packet['input_id'], packet_sha256=packet['packet_sha256'], run_id=run['run_id'],
    status=run['status'], snapshot_id=run.get('snapshot_id'), original_received_at=material['received_at'],
    disclosed_at=None, historical_pit_eligible=False, fact_count=len(facts), independent_original_count=1,
    raw_output_sha256=run.get('candidate_output_sha256'), backup_export_verified=True, backup_id=backup_saved['backup_id'],
    next_validation_dates_source_known=False, live_source_calls=0, real_model_calls=1)
(out / 'real-receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: receipt[k] for k in ['status','fact_count','packet_sha256','snapshot_id','raw_output_sha256','backup_export_verified']}, ensure_ascii=False))

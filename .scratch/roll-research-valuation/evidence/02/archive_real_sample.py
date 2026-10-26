"""Archive a local issuer original through public research and recovery services.

This is a receipt script, not a source fetch or a valuation/model acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'backend' / 'src'))
from roll.accounts.ledger import Ledger
from roll.market.directory import MarketDirectory
from roll.market.evidence import EvidenceStore
from roll.research.company import CompanyResearch, CompanyCommand, MaterialCommand
from roll.runtime.backups import Backups

parser = argparse.ArgumentParser()
parser.add_argument('--source-pdf', required=True)
parser.add_argument('--data-directory', required=True)
parser.add_argument('--receipt', required=True)
args = parser.parse_args()
source = Path(args.source_pdf)
content = source.read_bytes()
expected = '4493c7646001766896e6d4e3b97c702e9ee69423a86f8932df79e29bb75d5303'
assert hashlib.sha256(content).hexdigest() == expected, 'SOURCE_SAMPLE_HASH_MISMATCH'
from pypdf import PdfReader
reader = PdfReader(source)
identity_text = reader.pages[1].extract_text()
assert '600362' in identity_text and '江西铜业' in identity_text
ledger = Ledger(Path(args.data_directory))
service = CompanyResearch(EvidenceStore(ledger, MarketDirectory(ledger)))
company = service.register(CompanyCommand(legal_name='江西铜业股份有限公司', aliases=['江西铜业'],
    jurisdiction='CN', accounting_standard='CAS', year_end='12-31', industry='NON_FINANCIAL',
    identity_basis='Issuer identity on PDF page 2 of archived HKEX repost 2026032700133_c.pdf; local original hash verified',
    listings=[dict(exchange='SSE', code='600362', share_class='A', currency='CNY'), dict(exchange='HKEX', code='00358', share_class='H', currency='HKD')]))
material = service.import_material(MaterialCommand(company_id=company['company_id'], source_id='issuer-hkex-2025-cas',
    origin_root_id='jiangxi-copper:2025:prc-gaap-annual', subject_name=company['legal_name'],
    source_url='https://www.hkexnews.hk/listedco/listconews/sehk/2026/0327/2026032700133_c.pdf', media_type='application/pdf',
    period_start='2025-01-01', period_end='2025-12-31', page='PDF page 2 (1-based)', table='Company identity',
    disclosed_at=None, unit=None, currency='CNY', scope=None,
    limitations=['USER_IMPORT_OF_EXISTING_LOCAL_ORIGINAL_NOT_FRESH_NETWORK_ACQUISITION',
        'LEGACY_ACQUISITION_DATE_2026-10-23_ONLY_PRECISE_RECEIPT_UNKNOWN',
        'PRC_GAAP_HKEX_REPOST_NOT_THE_SEPARATE_20260429_IFRS_REPORT',
        'DOCUMENT_CONTAINS_MULTIPLE_TABLE_SCOPES_NO_NUMERIC_FACTS_EXTRACTED',
        'PDF_PRODUCTION_METADATA_IS_NOT_DISCLOSURE_TIME']), content)
restored_service = CompanyResearch(EvidenceStore(Ledger(Path(args.data_directory)), MarketDirectory(ledger)))
assert restored_service.material(material['material_id']) == material
assert restored_service.material_bytes(material['material_id']) == content
backup = Backups(Path(args.data_directory))
saved = backup.create()
backup.export(saved['backup_id'])
receipt = {'receipt_kind': 'REAL_LOCAL_ISSUER_ORIGINAL_IMPORT', 'source_file': str(source.resolve()),
    'source_url': material['source_url'], 'sha256': expected, 'bytes': len(content), 'pdf_pages': len(reader.pages),
    'identity_pdf_page_checked': 2, 'company_id': company['company_id'], 'material_id': material['material_id'],
    'source_kind': material['source_kind'], 'disclosed_at': material['disclosed_at'],
    'received_at': material['received_at'], 'consumable_at': material['consumable_at'],
    'archive': material['archive'], 'data_directory': str(Path(args.data_directory).resolve()),
    'backup_id': saved['backup_id'], 'backup_export_verified': True, 'reopened_material_equal': True,
    'historical_pit_eligible': False, 'network_calls': 0, 'model_calls': 0,
    'limitations': material['limitations']}
Path(args.receipt).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k: receipt[k] for k in ['receipt_kind', 'sha256', 'bytes', 'received_at', 'reopened_material_equal', 'backup_export_verified', 'network_calls', 'model_calls']}, ensure_ascii=False))

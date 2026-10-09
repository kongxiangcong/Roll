"""Bind independently read disclosure fields to verified official original bytes."""
import argparse
import hashlib
import json
from pathlib import Path


# Read against the fourteen original PDFs, not a provider's dividend table.
DIVIDENDS = [
    ('2013-07-18', '62845175', '2013-07-23', '2013-07-24', '2013-07-30', '0.50', None),
    ('2014-07-24', '1200074589', '2014-07-30', '2014-07-31', '2014-07-31', '0.50', None),
    ('2015-07-10', '1201268396', '2015-07-16', '2015-07-17', '2015-07-17', '0.20', None),
    ('2016-08-05', '1202538463', '2016-08-11', '2016-08-12', '2016-08-12', '0.10', None),
    ('2017-07-06', '1203684386', '2017-07-11', '2017-07-12', '2017-07-12', '0.15', None),
    ('2018-07-19', '1205195306', '2018-07-24', '2018-07-25', '2018-07-25', '0.20', None),
    ('2019-07-22', '1206466159', '2019-07-25', '2019-07-26', '2019-07-26', '0.20', None),
    ('2020-07-09', '1208016044', '2020-07-15', '2020-07-16', '2020-07-16', '0.10', None),
    ('2021-07-13', '1210467038', '2021-07-19', '2021-07-20', '2021-07-20', '0.10', None),
    ('2022-07-15', '1214041661', '2022-07-22', '2022-07-25', '2022-07-25', '0.50', None),
    ('2023-07-14', '1217292605', '2023-07-20', '2023-07-21', '2023-07-21', '0.50', None),
    ('2024-07-18', '1220664065', '2024-07-23', '2024-07-24', '2024-07-24', '0.60', '0.5970'),
    ('2025-07-15', '1224163682', '2025-07-21', '2025-07-22', '2025-07-22', '0.70', '0.6965'),
    ('2025-11-21', '1224816852', '2025-11-27', '2025-11-28', '2025-11-28', '0.40', '0.3980'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    documents = {item['url']: item for item in manifest['documents']}
    def reference(url):
        item = documents[url]
        if item['status'] != 'OFFICIAL_PDF_ARCHIVED' or not item['extraction_complete']:
            raise ValueError('OFFICIAL_COMPLETE_DOCUMENT_REQUIRED')
        raw = args.manifest.parent / item['path']
        if hashlib.sha256(raw.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('ORIGINAL_BYTES_CHANGED')
        return {key: item[key] for key in ['url', 'title', 'publication_date', 'sha256', 'received_at', 'path', 'text_sha256']}
    rows = []
    for published, identifier, record, ex, payment, cash, adjustment in DIVIDENDS:
        source = reference(f'https://static.cninfo.com.cn/finalpage/{published}/{identifier}.PDF')
        rows.append({'instrument': 'SSE:600362', 'action_type': 'DECLARED_CASH_DISTRIBUTION',
                     'record_date': record, 'ex_date': ex, 'cash_payment_date': payment,
                     'gross_cash_yuan_per_eligible_share': cash,
                     'differentiated_ex_reference_deduction_yuan_per_listed_share': adjustment,
                     'cash_receipt_for_user_account': 'NOT_ESTABLISHED',
                     'final_net_dividend_for_simulated_lot': None,
                     'tax_basis': 'Original notice and calendar holding period required; not an assumption of zero tax',
                     'date_precision': 'DATE', 'source': source,
                     'authority': 'PUBLIC_DOCUMENT_RECONSTRUCTION_NOT_HOST_TRAINING_QUALIFICATION'})
    suspension = {
        'instrument': 'SSE:600362', 'state': 'DECLARED_FULL_DAY_SUSPENSION',
        'start_date_inclusive': '2016-02-16', 'resumption_date_exclusive': '2016-02-26',
        'sources': [reference('https://static.cninfo.com.cn/finalpage/2016-02-16/1201981143.PDF'),
                    reference('https://static.cninfo.com.cn/finalpage/2016-02-26/1202000598.PDF')],
        'other_dates': 'UNKNOWN_UNLESS_SEPARATELY_PROVEN; no zero-volume or no-hit inference'}
    result = {'instrument': 'SSE:600362', 'source_manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
              'cash_distributions': rows, 'suspension_interval': suspension,
              'all_actions_or_statuses_complete': False, 'historical_price_vintages_proven': False,
              'training_eligibility': 'NOT_GRANTED', 'account_write_authority': 'NONE',
              'scope': 'Known official declaration subset; proposal/termination and repurchase originals retained in source manifest'}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'cash_distributions': len(rows), 'original_hash_mismatches': 0, 'account_events_written': 0}))


if __name__ == '__main__':
    main()

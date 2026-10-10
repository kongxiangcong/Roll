"""Collect the fixed Jiangxi Copper public research dossier without credentials.

Actual receipt times never become historical availability times. No training,
label calculation, sealed-input access, account writes, or provider fallback.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import httpx


SOURCES = [
    ('sohu-raw-2013-2025', 'https://q.stock.sohu.com/hisHq?code=cn_600362&start=20130101&end=20251231&stat=1&order=D&period=d', 'JSON_GB18030'),
    ('sina-actions-index', 'https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/600362.phtml', 'HTML_GB18030'),
    ('cninfo-2025-interim-distribution', 'https://static.cninfo.com.cn/finalpage/2025-11-21/1224816852.PDF', 'PDF'),
    ('hkex-2014-distribution', 'https://www.hkexnews.hk/listedco/listconews/sehk/2015/0709/ltn201507091180_c.pdf', 'PDF'),
    ('hkex-2024-annual-report', 'https://www.hkexnews.hk/listedco/listconews/sehk/2025/0327/2025032702751_c.pdf', 'PDF'),
    ('sse-2024-distribution', 'https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2025-07-15/600362_20250715_NW0M.pdf', 'PDF'),
    ('sse-2023-rule', 'https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/10824490/files/dcbe58edb194451d93f19b1f7dd8fb4c.docx', 'DOCX'),
    ('sse-2023-deferred-provisions', 'https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/10824490/files/3f0cc77bae0543c795a42731398bc8e0.docx', 'DOCX'),
    ('sse-2023-transition', 'https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20230217_5716420.shtml', 'HTML_UTF8'),
    ('sse-2018-closing-mechanism', 'https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20180806_4607055.shtml', 'HTML_UTF8'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--sources', nargs='+', choices=[source[0] for source in SOURCES])
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    raw = directory / 'raw'
    raw.mkdir()
    report = {'instrument': 'SSE:600362', 'started_at': stamp(),
              'sources': [], 'network_retries': 0, 'credentials_used': False,
              'sealed_results_read': False, 'labels_computed': False,
              'historical_point_in_time_proven': False,
              'receipt_policy': 'Actual download time retained; publication date, ex-date, and trading date are separate facts',
              'training_eligibility': 'NOT_GRANTED', 'account_authority': 'NONE'}
    def save():
        (directory / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    total = 0
    # Fixed public URLs, no Authorization, cookies, local .env, or redirects.
    with httpx.Client(timeout=40, follow_redirects=False,
                      headers={'User-Agent': 'RollPublicResearch/1.0', 'Referer': 'https://finance.sina.com.cn/'}) as client:
        for identifier, url, expected in SOURCES:
            if args.sources and identifier not in args.sources:
                continue
            item = {'id': identifier, 'url': url, 'expected_format': expected, 'started_at': stamp()}
            report['sources'].append(item)
            try:
                content = bytearray()
                with client.stream('GET', url) as response:
                    item.update(http_status=response.status_code, content_type=response.headers.get('content-type'),
                                server_date=response.headers.get('date'))
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        total += len(chunk)
                        if len(content) > 32 * 1024 * 1024 or total > 96 * 1024 * 1024:
                            raise ValueError('PUBLIC_DOSSIER_BYTE_LIMIT')
                content = bytes(content)
                sha = hashlib.sha256(content).hexdigest()
                extension = 'pdf' if content.startswith(b'%PDF-') else 'docx' if expected == 'DOCX' and content.startswith(b'PK') else 'raw'
                target = raw / (sha + '.' + extension)
                if not target.exists():
                    target.write_bytes(content)
                item.update(received_at=stamp(), sha256=sha, bytes=len(content), path=target.relative_to(directory).as_posix())
                if item['http_status'] != 200:
                    item['status'] = 'HTTP_FAILURE_ARCHIVED'
                elif expected == 'PDF':
                    item['status'] = 'PDF_ARCHIVED' if extension == 'pdf' else 'NON_PDF_RESPONSE_ARCHIVED_NOT_DOCUMENT_EVIDENCE'
                elif expected == 'DOCX':
                    with ZipFile(BytesIO(content)) as package:
                        if 'word/document.xml' not in package.namelist() or sum(entry.file_size for entry in package.infolist()) > 16 * 1024 * 1024:
                            raise ValueError('INVALID_OR_EXCESSIVE_DOCX_PACKAGE')
                    item['status'] = 'DOCX_ARCHIVED_NOT_HISTORICAL_APPLICABILITY_CERTIFICATION'
                elif expected == 'JSON_GB18030':
                    value = json.loads(content.decode('gb18030'))
                    if not isinstance(value, list) or len(value) != 1 or value[0].get('code') != 'cn_600362' or value[0].get('status') != 0:
                        raise ValueError('SOHU_OBJECT_OR_BUSINESS_STATUS_MISMATCH')
                    rows = value[0]['hq']
                    dates = [r[0] for r in rows]
                    if not rows or any(len(r) != 10 for r in rows) or len(dates) != len(set(dates)):
                        raise ValueError('SOHU_ROW_SCHEMA_OR_DUPLICATE_DATE')
                    if not all('2013-01-01' <= day <= '2025-12-31' for day in dates):
                        raise ValueError('SOHU_REQUEST_WINDOW_MISMATCH')
                    item.update(status='PUBLIC_CURRENT_HISTORY_ARCHIVED', row_count=len(rows), first_date=min(dates), last_date=max(dates),
                                row_width=10, amount_and_volume_semantics='Requires supplier unit evidence before normalization',
                                historical_availability='UNKNOWN; retrieval of current history is not vintage proof')
                else:
                    item['status'] = ('PUBLIC_RULE_PAGE_ARCHIVED_NOT_HISTORICAL_SCOPE_CERTIFICATION' if expected == 'HTML_UTF8'
                                      else 'PUBLIC_INDEX_ARCHIVED_NOT_COMPLETE_ACTION_CERTIFICATION')
            except (httpx.HTTPError, ValueError, KeyError, UnicodeError, BadZipFile) as error:
                item.update(status='FAILED', failure_class=type(error).__name__)
            item['finished_at'] = stamp()
            save()
    report['finished_at'] = stamp()
    report['total_received_bytes'] = total
    report['archive_verification'] = {'checked': sum('path' in s for s in report['sources']),
        'mismatches': sum(hashlib.sha256((directory / s['path']).read_bytes()).hexdigest() != s['sha256'] for s in report['sources'] if 'path' in s)}
    save()
    print(json.dumps({k: report[k] for k in ['instrument', 'archive_verification', 'total_received_bytes', 'historical_point_in_time_proven']}, ensure_ascii=False))
    for item in report['sources']:
        print(item['id'], item['status'], item.get('row_count'), item.get('bytes'))


def stamp():
    return datetime.now(timezone.utc).isoformat()


if __name__ == '__main__':
    main()

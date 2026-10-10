"""Archive bounded, official CNINFO disclosure searches and their original PDFs.

The fixed historical window precedes 2026 and is not a final-test partition.
Keyword coverage is reported; absence of a hit never means normal/no actions.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re

import httpx
from pypdf import PdfReader
from pypdf.errors import PdfReadError


TERMS = ['实施公告', '停牌', '复牌', '风险警示', '配股', '股本变动', '非公开发行', '股份回购', '']
QUERY = 'https://www.cninfo.com.cn/new/hisAnnouncement/query'
BASE = 'https://static.cninfo.com.cn/'


def stamp():
    return datetime.now(timezone.utc).isoformat()


def collect(directory, reuse_directory=None):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / 'raw').mkdir()
    report = {'instrument': 'SSE:600362', 'window': ['2013-01-01', '2025-12-31'],
              'started_at': stamp(), 'searches': [], 'documents': [], 'network_retries': 0,
              'classification': 'OFFICIAL_DISCLOSURE_RECONSTRUCTION; NOT_COMPLETE_STATUS_OR_VINTAGE_CERTIFICATION',
              'historical_price_vintages_verified': False, 'seal_consumed': False,
              'account_authority': 'NONE', 'labels_computed': False, 'total_received_bytes': 0}
    def save():
        (directory / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    def archive(content):
        sha = hashlib.sha256(content).hexdigest()
        suffix = '.pdf' if content.startswith(b'%PDF-') else '.raw'
        path = directory / 'raw' / (sha + suffix)
        if not path.exists():
            path.write_bytes(content)
        return {'sha256': sha, 'bytes': len(content), 'path': path.relative_to(directory).as_posix(), 'received_at': stamp()}
    def body(response):
        result = bytearray()
        for part in response.iter_bytes():
            result.extend(part)
            report['total_received_bytes'] += len(part)
            if len(result) > 16 * 1024 * 1024 or report['total_received_bytes'] > 96 * 1024 * 1024:
                raise ValueError('DISCLOSURE_BYTE_LIMIT')
        return bytes(result)
    cached = {}
    if reuse_directory:
        previous = json.loads((reuse_directory / 'manifest.json').read_text(encoding='utf-8'))
        for item in previous['documents']:
            if item.get('status') == 'OFFICIAL_PDF_ARCHIVED':
                if not re.fullmatch(r'raw/[0-9a-f]{64}\.pdf', item['path']):
                    raise ValueError('INVALID_CACHED_ARCHIVE_PATH')
                content = (reuse_directory / item['path']).read_bytes()
                if hashlib.sha256(content).hexdigest() != item['sha256']:
                    raise ValueError('CORRUPT_CACHED_ORIGINAL')
                cached[item['url']] = (item, content)
    selected = {}
    with httpx.Client(timeout=30, follow_redirects=False,
                      headers={'User-Agent': 'RollPublicResearch/1.0', 'Referer': 'https://www.cninfo.com.cn/'}) as client:
        for term in TERMS:
            item = {'keyword': term, 'pages': [], 'query_url': QUERY, 'full_keyword_result_retrieved': False}
            report['searches'].append(item)
            try:
                returned = 0
                seen = set()
                for page in range(1, 41 if term == '' else 4):
                    form = {'stock': '600362,gssh0600362', 'column': 'sse', 'tabName': 'fulltext',
                            'seDate': '2013-01-01~2025-12-31', 'searchkey': term,
                            'sortName': 'time', 'sortType': 'asc', 'pageNum': str(page), 'pageSize': '30'}
                    with client.stream('POST', QUERY, data=form) as response:
                        content = body(response)
                        stored = archive(content)
                        item['pages'].append({'request_form': form, 'http_status': response.status_code, **stored})
                        response.raise_for_status()
                    value = json.loads(content)
                    rows = value.get('announcements') or []
                    count = value.get('totalAnnouncement')
                    if not isinstance(count, int) or count < 0 or not isinstance(rows, list):
                        raise ValueError('DISCLOSURE_METADATA_SCHEMA')
                    item['total_reported'] = count
                    for row in rows:
                        identifier = row.get('announcementId')
                        if not identifier:
                            raise ValueError('MISSING_DISCLOSURE_ID_IN_PAGINATION')
                        if identifier in seen:
                            item.setdefault('duplicate_ids', []).append({'page': page, 'announcement_id': identifier})
                        seen.add(identifier)
                        if row.get('secCode') != '600362':
                            raise ValueError('DISCLOSURE_OBJECT_MISMATCH')
                        # Full-index metadata is retained even for records which
                        # link to formats this PDF collector does not follow.
                        if term == '':
                            continue
                        adjunct_original = row.get('adjunctUrl', '')
                        adjunct = adjunct_original.strip()
                        if not re.fullmatch(r'finalpage/\d{4}-\d{2}-\d{2}/\d+\.PDF', adjunct):
                            raise ValueError('UNAPPROVED_DISCLOSURE_PATH')
                        if not '2013-01-01' <= adjunct.split('/')[1] <= '2025-12-31':
                            raise ValueError('DISCLOSURE_DATE_OUTSIDE_WINDOW')
                        title = row.get('announcementTitle', '')
                        title = re.sub('<[^>]*>', '', title)
                        useful = (term != '实施公告' or any(word in title for word in ['分派', '分红', '派息', '利润分配', '回购'])) and term != ''
                        if useful:
                            selected.setdefault(adjunct, {'title': title, 'publication_date': adjunct.split('/')[1],
                                                         'url': BASE + adjunct, 'keywords': []})['keywords'].append(term)
                    returned += len(rows)
                    if returned >= count:
                        item['all_reported_rows_paged'] = returned == count
                        item['full_keyword_result_retrieved'] = returned == count and len(seen) == count
                        if not item['full_keyword_result_retrieved']:
                            item['limitation'] = 'PAGINATION_DUPLICATES_OR_COUNT_MISMATCH; INDEX_COMPLETENESS_UNPROVEN'
                        break
                    if not rows:
                        break
                item['returned_rows'] = returned
                item['unique_announcement_ids'] = len(seen)
            except (httpx.HTTPError, ValueError, KeyError) as error:
                item.update(status='FAILED', failure_class=type(error).__name__)
            save()
        for item in selected.values():
            if len(report['documents']) >= 80:
                report['document_limit_reached'] = True
                break
            report['documents'].append(item)
            try:
                if item['url'] in cached:
                    previous, content = cached[item['url']]
                    item.update(http_status=previous['http_status'], **archive(content))
                    item.update(received_at=previous['received_at'], copied_from=str(reuse_directory / previous['path']))
                else:
                    with client.stream('GET', item['url']) as response:
                        content = body(response)
                        item.update(http_status=response.status_code, **archive(content))
                        response.raise_for_status()
                if not content.startswith(b'%PDF-'):
                    raise ValueError('NON_PDF_RESPONSE_ARCHIVED')
                reader = PdfReader(BytesIO(content))
                # Implementation notices are short. Keep an explicit bound and
                # never claim a partial extract is an entire long document.
                pages = min(12, len(reader.pages))
                text = '\n'.join(reader.pages[index].extract_text() or '' for index in range(pages))
                if '600362' not in text and '江西铜业' not in text:
                    raise ValueError('DISCLOSURE_DOCUMENT_IDENTITY_NOT_VERIFIED')
                text_path = directory / (item['sha256'] + '.txt')
                text_path.write_text(text, encoding='utf-8')
                item.update(status='OFFICIAL_PDF_ARCHIVED', pdf_pages=len(reader.pages), extracted_pages=pages,
                            extraction_complete=pages == len(reader.pages), text_path=text_path.name,
                            text_sha256=hashlib.sha256(text_path.read_bytes()).hexdigest(),
                            historical_available_at=None, publication_precision='DATE',
                            availability_basis='Actual receipt; original disclosure date is not a manufactured publication clock')
            except (httpx.HTTPError, ValueError, KeyError, PdfReadError) as error:
                item.update(status='FAILED_ARCHIVE_RETAINED', failure_class=type(error).__name__)
            save()
    report['finished_at'] = stamp()
    originals = [p for search in report['searches'] for p in search['pages']] + [d for d in report['documents'] if d.get('path')]
    report['archive_verification'] = {'checked': len(originals), 'mismatches': sum(
        hashlib.sha256((directory / item['path']).read_bytes()).hexdigest() != item['sha256'] for item in originals)}
    save()
    print(json.dumps({'searches': [(s['keyword'], s.get('total_reported'), s['full_keyword_result_retrieved']) for s in report['searches']],
                      'documents': len(report['documents']), 'passed_documents': sum(d.get('status') == 'OFFICIAL_PDF_ARCHIVED' for d in report['documents']),
                      'archive_verification': report['archive_verification']}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--reuse-directory', type=Path)
    args = parser.parse_args()
    collect(args.directory.resolve(), args.reuse_directory.resolve() if args.reuse_directory else None)

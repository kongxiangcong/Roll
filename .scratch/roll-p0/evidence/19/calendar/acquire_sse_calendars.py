"""Archive exact official SSE annual closure notices and known corrections.

No prices, outcomes, credentials or trading status inference is involved.
"""
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[5]
REFERENCE = ROOT / 'backend/src/roll/market/reference'
SOURCES = [
    ('2013', '2012-12-26', 'aboutus/mediacenter/hotandd/c/c_20150912_3988635.shtml'),
    ('2014', '2013-12-25', 'aboutus/mediacenter/hotandd/c/c_20150912_3988725.shtml'),
    ('2015', '2014-12-24', 'disclosure/dealinstruc/closed/list/c/c_20160104_3979217.shtml'),
    ('2016', '2015-12-24', 'disclosure/dealinstruc/closed/list/c/c_20160104_4028872.shtml'),
    ('2017', '2016-12-22', 'disclosure/announcement/general/c/c_20161222_4218613.shtml'),
    ('2018', '2017-12-22', 'disclosure/announcement/general/c/c_20171222_4438363.shtml'),
    ('2019', '2018-12-20', 'disclosure/announcement/general/c/c_20181220_4696473.shtml'),
    ('2020', '2019-12-20', 'disclosure/announcement/general/c/c_20191220_4969627.shtml'),
    ('2021', '2020-12-24', 'disclosure/announcement/general/c/c_20201224_5286949.shtml'),
    ('2022', '2021-12-20', 'disclosure/announcement/general/c/c_20211220_5662606.shtml'),
    ('2023', '2022-12-27', 'disclosure/announcement/general/c/c_20221227_5714458.shtml'),
    ('2024', '2023-12-26', 'disclosure/dealinstruc/closed/c/c_20231226_5733941.shtml'),
    ('2025', '2024-12-23', 'disclosure/dealinstruc/closed/c/c_20241223_10767110.shtml'),
    ('2015-memorial', '2015-07-21', 'disclosure/dealinstruc/closed/list/c/c_20160104_3979337.shtml'),
    ('2019-labor-revision', '2019-04-18', 'disclosure/announcement/general/c/c_20190418_4771364.shtml'),
    ('2020-spring-extension', '2020-01-27', 'disclosure/announcement/general/c/c_20200127_4991582.shtml'),
]


def acquire():
    registry = json.loads((REFERENCE / 'sources.json').read_text(encoding='utf-8'))
    extraction = []
    for suffix, published, path in SOURCES:
        source_id = 'sse-calendar-' + suffix
        url = 'https://www.sse.com.cn/' + path
        with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=40) as response:
            content = response.read()
            if response.status != 200 or response.url != url:
                raise RuntimeError(f'Unexpected response: {source_id} {response.status} {response.url}')
        text = content.decode('utf-8')
        title = html.unescape(re.search(r'<title>(.*?)</title>', text, re.S).group(1)).strip()
        if '休市' not in title or (suffix.isdigit() and suffix not in title) or published not in text:
            raise RuntimeError(f'Not the expected official notice: {source_id} {title}')
        if '上海证券交易所' not in text or '开市' not in text or (suffix.isdigit() and '周末' not in text):
            raise RuntimeError(f'Missing exchange calendar clauses: {source_id}')
        filename = source_id + '.html'
        (REFERENCE / filename).write_bytes(content)
        metadata = {'id': source_id, 'url': url, 'fetched_at': datetime.now(timezone.utc).isoformat(),
                    'published_date': published, 'sha256': hashlib.sha256(content).hexdigest(),
                    'file': filename, 'bytes': len(content), 'attachments': [], 'title': title,
                    'purpose': 'ANNUAL_EXCHANGE_CALENDAR' if suffix.isdigit() else 'EXCHANGE_CALENDAR_CORRECTION'}
        registry = [item for item in registry if item['id'] != source_id] + [metadata]
        # The notices use paragraphs, BR-delimited text and table cells.
        body = re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', text, flags=re.S)
        paragraphs = [html.unescape(p).strip() for p in re.sub('<[^>]+>', '\n', body).splitlines()]
        extraction.append({'id': source_id, 'title': title, 'published_date': published,
                           'paragraphs': [p for p in paragraphs if '休市' in p or '开市' in p]})
        print(source_id, len(content), metadata['sha256'])
    (REFERENCE / 'sources.json').write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    (Path(__file__).parent / 'official-notice-extract.json').write_text(
        json.dumps(extraction, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    acquire()

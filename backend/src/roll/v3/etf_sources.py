"""Bounded ETF share and unit NAV acquisition from the exchanges and Fuyao."""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
from io import BytesIO
import json
import os
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

import httpx

from roll.config import load_runtime_environment
from roll.v3.etf import freeze_etf_snapshot, previous_etf_session
from roll.v3.etf_observations import ETF_UNITS, etf_symbol, exchange_source
from roll.v3.market import LIVE_RUN, append_observations, available_dates
from roll.v3.market_sources import FUYAO, _get as get_fuyao
from roll.market.calendar import extended_sessions
from roll.v3.storage import database, SHANGHAI, sessions


SSE_URL = 'https://query.sse.com.cn/commonQuery.do'
SSE_QUERY = 'COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L'
SZSE_URL = 'https://www.szse.cn/api/report/ShowReport'
SZSE_PAGE = 'https://www.szse.cn/market/fund/volume/etf/index.html'
NAV_PATH = '/api/fund/performance/nav'
NAV_RANGES = ((6, 'week'), (28, 'month'), (86, 'tmonth'), (175, 'hyear'),
              (360, 'year'), (725, 'twoyear'), (1090, 'tyear'), (1820, 'fyear'))
BROWSER = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
           '(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36')
EXCEL_NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def _observation(*, source, series, symbol, day, raw_date, raw_value, raw_unit,
                 source_ref, evidence, received, multiplier=1):
    payload = {'raw_value': str(raw_value) if raw_value is not None else None,
               'raw_unit': raw_unit, 'raw_date': str(raw_date), 'source_date': day, 'verified': True}
    quality = 'usable'
    try:
        amount = Decimal(str(raw_value).replace(',', ''))
        with localcontext() as context:
            context.prec = max(context.prec, len(amount.as_tuple().digits) + 4)
            payload['value'] = format(amount * multiplier, 'f') if amount.is_finite() else None
        if not amount.is_finite() or amount < 0 or (amount == 0 and series == 'etf_nav'):
            quality = 'invalid_value'
    except InvalidOperation:
        quality = 'invalid_value'
    return {'source': source, 'series': series, 'symbol': symbol, 'trade_date': day,
            'unit': ETF_UNITS[series], 'source_ref': source_ref, 'available_evidence': evidence,
            'received_at': received, 'quality': quality, 'payload': payload}


def _sse_shares(client, day, symbols):
    response = client.get(SSE_URL, params={'isPagination': 'false', 'sqlId': SSE_QUERY, 'STAT_DATE': day},
                          headers={'Referer': 'https://www.sse.com.cn/', 'User-Agent': BROWSER},
                          timeout=20)
    response.raise_for_status()
    received = datetime.now(timezone.utc)
    payload = json.loads(response.content, parse_float=Decimal)
    if payload.get('actionErrors') or not isinstance(payload.get('result'), list):
        raise ValueError('上交所基金规模表响应异常')
    for item in payload['result']:
        symbol = item['SEC_CODE'] + '.SH'
        if symbol not in symbols:
            continue
        observed_day = str(date.fromisoformat(item['STAT_DATE']))
        row = _observation(source='sse', series='etf_shares', symbol=symbol, day=day,
                           raw_date=item['STAT_DATE'], raw_value=item['TOT_VOL'], raw_unit='万份',
                           source_ref=str(response.request.url), received=received, multiplier=10_000,
                           evidence='上交所日终清算后基金规模表，STAT_DATE / TOT_VOL（万份）')
        if observed_day != day:
            row['quality'] = 'date_mismatch'
            row['payload']['source_date'] = observed_day
        yield row


def _excel_text(node):
    return ''.join(part.text or '' for part in node.findall('.//m:t', EXCEL_NS))


def _szse_table(content):
    # Preserve cell text so fund shares never pass through a binary float.
    with ZipFile(BytesIO(content)) as workbook:
        def xml(name):
            if workbook.getinfo(name).file_size > 24 * 1024 * 1024:
                raise ValueError('深交所基金规模表超出预期大小')
            return ElementTree.fromstring(workbook.read(name))

        shared_strings = []
        if 'xl/sharedStrings.xml' in workbook.namelist():
            shared_strings = [_excel_text(item)
                              for item in xml('xl/sharedStrings.xml').findall('m:si', EXCEL_NS)]
        sheet = xml('xl/worksheets/sheet1.xml')
        header = {}
        for row in sheet.findall('m:sheetData/m:row', EXCEL_NS):
            cells = {}
            for cell in row.findall('m:c', EXCEL_NS):
                column = cell.get('r').rstrip('0123456789')
                kind = cell.get('t')
                value = cell.findtext('m:v', default='', namespaces=EXCEL_NS)
                if kind == 'inlineStr':
                    value = _excel_text(cell)
                elif kind == 's':
                    value = shared_strings[int(value)]
                cells[column] = value
            if not header:
                header = {value: column for column, value in cells.items()}
                if not {'日期', '基金代码', '基金规模(份)'} <= header.keys():
                    raise ValueError('深交所基金规模表缺少日期、基金代码或份额列')
                continue
            if any(cells.values()):
                yield tuple(cells.get(header[field], '') for field in ('日期', '基金代码', '基金规模(份)'))
        if not header:
            raise ValueError('深交所基金规模表缺少表头')


def _szse_shares(client, missing):
    days = sorted(set().union(*missing.values()))
    params = {'SHOWTYPE': 'xlsx', 'CATALOGID': 'scsj_fund_jjgm', 'TABKEY': 'tab1',
              'txtStart': days[0], 'txtEnd': days[-1], 'jjlb': 'ETF'}
    response = client.get(SZSE_URL, params=params, headers={'Referer': SZSE_PAGE, 'User-Agent': BROWSER},
                          timeout=20)
    response.raise_for_status()
    received = datetime.now(timezone.utc)
    for raw_date, code, raw_value in _szse_table(response.content):
        symbol = code.zfill(6) + '.SZ'
        if symbol not in missing:
            continue
        day = str(date.fromisoformat(raw_date))
        if day not in missing[symbol]:
            continue
        yield _observation(source='szse', series='etf_shares', symbol=symbol, day=day,
                           raw_date=raw_date, raw_value=raw_value, raw_unit='份',
                           source_ref=str(response.request.url), received=received,
                           evidence='深交所 ETF 基金规模日频原表，日期 / 基金规模(份)')


def _fuyao_nav(client, token, symbol, days, today):
    age = (today - date.fromisoformat(min(days))).days
    period = next((period for limit, period in NAV_RANGES if age <= limit), None)
    if not period:
        raise ValueError('请求日期超出扶摇单位净值可查询期限')
    if not token:
        raise ValueError('FUYAO_API_KEY 未配置')
    params = {'range': period, 'nav_type': 'unit'}
    data = get_fuyao(client, token, NAV_PATH, symbol, params)
    received = datetime.now(timezone.utc)
    ref = httpx.URL(FUYAO + NAV_PATH, params={'thscode': symbol, **params})
    for item in data['item']:
        raw_date = item['nav_date']
        day = str(datetime.fromtimestamp(int(raw_date) / 1000, SHANGHAI).date())
        if day not in days:
            continue
        yield _observation(source='fuyao', series='etf_nav', symbol=symbol, day=day,
                           raw_date=raw_date, raw_value=item.get('unit_nav'), raw_unit='元/份',
                           source_ref=str(ref), received=received,
                           evidence='扶摇历史单位净值，nav_date / unit_nav（元/份）')


def _record_result(data_dir, rows, expected, error=None):
    by_key = defaultdict(list)
    for row in rows:
        by_key[row['symbol'], row['trade_date']].append(row)
    observations = []
    gaps = []
    for symbol, day in expected:
        items = by_key[symbol, day]
        if not items:
            gaps.append({'symbol': symbol, 'trade_date': day, 'error': error or '来源未返回该日'})
            continue
        row = items[0]
        if any(item['payload'] != row['payload'] for item in items[1:]):
            row['quality'] = 'conflict'
            row['payload']['source_records'] = [dict(item['payload']) for item in items]
        if row['quality'] != 'usable':
            gaps.append({'symbol': symbol, 'trade_date': day, 'error': row['quality']})
        observations.append(row)
    return append_observations(data_dir, observations)['appended'], gaps


def sync_etf_market(data_dir, *, symbols, start, end, refresh=False, on_progress=None):
    """Acquire missing observations and freeze even when a requested field is late."""
    now = datetime.now(SHANGHAI)
    left, right = date.fromisoformat(start), date.fromisoformat(end)
    if right > now.date() or (right - left).days > 31:
        raise ValueError('ETF 同步须选择截至今日且不超过 32 个自然日的区间')
    with database(data_dir) as db:
        extension = extended_sessions(db)
    days = list(sessions(start, end, extension))
    symbols = tuple(dict.fromkeys(map(etf_symbol, symbols)))
    if not days or not symbols:
        raise ValueError('ETF 同步须指定基金和含交易日的区间')
    previous = previous_etf_session(days[0], extension)
    share_days = [previous, *days] if previous else days
    missing = {}
    for series, expected_days in (('etf_shares', share_days), ('etf_nav', days)):
        missing[series] = {}
        for symbol in symbols:
            available = set() if refresh else available_dates(
                data_dir, series=series, symbol=symbol, start=expected_days[0], end=expected_days[-1],
                as_of=now, use_mode=LIVE_RUN,
            )
            missing[series][symbol] = set(expected_days) - available

    shares = missing['etf_shares']
    nav = missing['etf_nav']
    sse = {day: sorted(symbol for symbol in symbols if exchange_source(symbol) == 'sse' and day in shares[symbol])
           for day in share_days}
    szse = {symbol: days for symbol, days in shares.items() if exchange_source(symbol) == 'szse' and days}
    failures = []
    appended = 0
    fields = {}
    for series, expected_days in (('etf_shares', share_days), ('etf_nav', days)):
        expected = len(symbols) * len(expected_days)
        cached = expected - sum(len(pending) for pending in missing[series].values())
        fields[series] = {'expected': expected, 'completed': cached, 'failed': 0, 'succeeded': cached}

    def progress():
        return {'appended': appended, 'failures': list(failures),
                'fields': {series: dict(status) for series, status in fields.items()}}

    def publish():
        if on_progress:
            on_progress(progress())

    def record_progress(source, series, size, gaps):
        status = fields[series]
        status['completed'] += size
        status['failed'] += len(gaps)
        status['succeeded'] += size - len(gaps)
        failures.extend({'series': series, 'source': source, **gap} for gap in gaps)
        publish()

    publish()
    if any(sse.values()) or szse or any(nav.values()):
        token = None
        token_error = None
        if any(nav.values()):
            try:
                load_runtime_environment()
                token = os.environ.get('FUYAO_API_KEY')
            except ValueError as error:
                token_error = str(error)
        with httpx.Client() as client:
            operations = []
            for day, codes in sse.items():
                if codes:
                    operations.append(('sse', 'etf_shares', _sse_shares(client, day, codes),
                                       [(symbol, day) for symbol in codes]))
            if szse:
                operations.append(('szse', 'etf_shares', _szse_shares(client, szse),
                                   [(symbol, day) for symbol, dates in szse.items() for day in sorted(dates)]))
            for symbol, dates in nav.items():
                if not dates:
                    continue
                if token_error:
                    record_progress('fuyao', 'etf_nav', len(dates), [
                        {'symbol': symbol, 'trade_date': day, 'error': token_error} for day in sorted(dates)
                    ])
                    continue
                operations.append(('fuyao', 'etf_nav', _fuyao_nav(client, token, symbol, dates, now.date()),
                                   [(symbol, day) for day in sorted(dates)]))
            for source, series, rows, expected in operations:
                acquired = []
                failure = None
                try:
                    acquired.extend(rows)
                except (ValueError, KeyError, TypeError, IndexError, httpx.HTTPError, BadZipFile,
                        ElementTree.ParseError) as error:
                    failure = str(error)
                stored, gaps = _record_result(data_dir, acquired, expected, failure)
                appended += stored
                record_progress(source, series, len(expected), gaps)

    return {'snapshot': freeze_etf_snapshot(data_dir, symbols=symbols, start=start, end=end),
            **progress(), 'paid_budget': 0, 'paid_requests': 0}

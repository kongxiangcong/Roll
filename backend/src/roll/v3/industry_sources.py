"""Normalize the publisher's industrial-metals index and membership captures."""

from datetime import datetime, time
import json
import ssl
from urllib.parse import urlencode

import httpx

from roll.v3.market import SHANGHAI


STOCK = '600362.SH'
INDUSTRIAL_METALS = '801055.SI'
SHENWAN = 'https://www.swsresearch.com/institute-sw/api/index_publish'
CLASSIFICATION = '申万行业分类（2021版）'
CLASSIFICATION_REF = 'https://wxweb.swsresearch.com/swsreport/2021_08/328340.pdf'
METALS_ETF = {
    'symbol': '512400.SH',
    'name': '南方中证申万有色金属ETF',
    'tracked_index': '中证申万有色金属指数',
    'source_ref': 'https://www.sse.com.cn/assortment/fund/list/etfinfo/basic/index.shtml?FUNDID=512400',
}
MEMBERSHIP_FIELDS = (
    'index_symbol', 'index_name', 'classification', 'classification_ref',
    'effective_start', 'effective_end', 'member_name', 'membership_basis',
)


def fetch_shenwan(ca_file=None):
    """Fetch the publisher's separate quote and membership datasets."""
    verification = ssl.create_default_context(cafile=ca_file) if ca_file else True
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
    with httpx.Client(headers=headers, verify=verification, timeout=20) as client:
        def capture(route, **params):
            response = client.get(f"{SHENWAN}/{route}/", params={"swindexcode": "801055", **params})
            response.raise_for_status()
            return {"received_at": datetime.now(SHANGHAI).isoformat(),
                    "data": json.loads(response.content, parse_float=str)}

        return capture("trend", period="DAY"), capture("details/component_stocks", page=1, page_size=10000)


def _public_data(capture):
    response = capture['data']
    if str(response['code']) != '200':
        raise ValueError(f"申万指数接口业务码 {response['code']}")
    return response['data']


def shenwan_observations(trend_capture, members_capture, *, start, end):
    """Produce observations for published 801055 trends and the 600362 membership evidence."""
    index_code = INDUSTRIAL_METALS.split('.')[0]
    trend_ref = f"{SHENWAN}/trend/?" + urlencode({'swindexcode': index_code, 'period': 'DAY'})
    bar_fields = {'open': 'openindex', 'high': 'maxindex', 'low': 'minindex', 'close': 'closeindex',
                  'volume': 'bargainamount', 'amount': 'bargainsum'}
    for item in _public_data(trend_capture):
        day = item['bargaindate']
        if item['swindexcode'] != index_code:
            raise ValueError('申万历史行情中的指数代码应为 801055')
        if start <= day <= end:
            yield {
                'series': 'daily_bar', 'symbol': INDUSTRIAL_METALS, 'trade_date': day,
                'source': 'shenwan', 'source_ref': trend_ref, 'received_at': trend_capture['received_at'],
                'assumed_available_at': datetime.combine(datetime.fromisoformat(day).date(), time(15, 5), SHANGHAI),
                'availability_assumption': '申万历史日线按所属交易日 15:05 完成重建',
                'unit': {'price': 'index_point', 'volume': 'Shenwan bargainamount',
                         'amount': 'Shenwan bargainsum'},
                'payload': {key: item[field] for key, field in bar_fields.items()},
            }

    members_ref = f"{SHENWAN}/details/component_stocks/?" + urlencode(
        {'swindexcode': index_code, 'page': 1, 'page_size': 10000})
    received_at = members_capture['received_at']
    observed_through = datetime.fromisoformat(received_at).astimezone(SHANGHAI).date().isoformat()
    for member in _public_data(members_capture)['results']:
        if member['stockcode'] != STOCK.split('.')[0]:
            continue
        effective_start = datetime.fromisoformat(member['beginningdate']).date().isoformat()
        yield {
            'series': 'industry_membership', 'symbol': STOCK, 'trade_date': effective_start,
            'source': 'shenwan', 'source_ref': members_ref, 'received_at': received_at,
            'payload': {
                'index_symbol': INDUSTRIAL_METALS, 'index_name': '工业金属',
                'classification': CLASSIFICATION, 'classification_ref': CLASSIFICATION_REF,
                'effective_start': effective_start, 'effective_end': observed_through,
                'member_name': member['stockname'],
                'membership_basis': '申万工业金属现行成分表所列纳入日期，连续归属重建截至成分表采集日',
            },
        }

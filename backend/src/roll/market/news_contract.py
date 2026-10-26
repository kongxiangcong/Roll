"""Fixed public targets shared by the news capture and archive validators."""
import json,re
from urllib.parse import urlsplit

SDK_VERSION='1.19.1'
SDK_SOURCE_SHA='fbda1c9a6f5b96552bcd61baa80afb6697fae3ab44ddf659a592b7bcbd1c0ca0'
EXTRACTOR_VERSION='2.3.1'
SOURCE='akshare-news-em'


def body_url(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or p.netloc!='finance.eastmoney.com' or p.query or p.fragment or not re.fullmatch(r'/a/[0-9]{8,30}\.html',p.path):
        raise ValueError('NEWS_BODY_TARGET_NOT_ALLOWED')
    return 'https://finance.eastmoney.com'+p.path


def list_rows(raw):
    text=raw.decode('utf-8-sig').strip()
    if not text.startswith('{'):
        callback='jQuery35101792940631092459_1764599530165('
        if not text.startswith(callback) or not text.rstrip(';').endswith(')'):raise ValueError('NEWS_LIST_JSONP_SCHEMA')
        text=text[len(callback):].rstrip(';')[:-1]
    rows=json.loads(text)['result']['cmsArticleWebOld']
    if not isinstance(rows,list) or len(rows)>10:raise ValueError('NEWS_LIST_PAGE_BUDGET')
    return rows

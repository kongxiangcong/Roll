"""Frozen company-object projection for fresh material only; no sentiment labels."""
import html
import re

VERSION = 'sentiment-object-v2-fresh'
ALIASES = ('江西铜业股份有限公司', '江西铜业股份', '江西铜业')
PREDICATES = ('增','降','涨','跌','亏','盈','利润','营收','收入','产量','投产','停产','收购','出售','签','发','公告','召开','董事','股东','聘','辞','更正','修订','澄清','减持','回购','完成','未','不','否认','资金')
SHARED = ('均','双双','集体','全部')


def clean(value):
    return html.unescape(re.sub(r'<[^>]*>', '', value or '')).strip()


def project(title, summary):
    title, summary = clean(title), clean(summary)
    chunks = re.split(r'[。！？!?；;\n，,]', title+'\n'+summary)
    selected = []
    incidental = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk or not any(alias in chunk for alias in ALIASES):
            continue
        # A shared predicate can apply to multiple explicitly named companies.
        # A bare constituent/fund-flow list is not an object-specific assertion.
        after = chunk.split('江西铜业',1)[1]
        if '分别' in chunk and ('、' in chunk or '及' in chunk):
            incidental.append(chunk)
            continue
        if ('、' in chunk or '等' in after) and not any(word in chunk for word in SHARED):
            incidental.append(chunk)
            continue
        if not any(word in after for word in PREDICATES):
            incidental.append(chunk)
            continue
        selected.append(chunk)
    selected = list(dict.fromkeys(selected))
    text = '；'.join(selected)[:800]
    return {'version':VERSION, 'text':text, 'association':'COMPANY_OBJECT' if text else 'INCIDENTAL_OR_UNCERTAIN',
            'reject_reason':None if text else 'ABSTAIN_NO_COMPANY_OBJECT', 'selected_clauses':selected,
            'incidental_clauses':incidental}

"""Frozen reject rules for the limited Chinese sentiment research component."""
VERSION='sentiment-reject-v1'
CONFIDENCE_FLOOR=0.65
COMPANY_ALIASES=('江西铜业',)
MARKET_INDEX_MARKERS=('ETF','指数','收评','午评')
FUND_FLOW_MARKERS=('资金流入','资金流出','资金流向','主力资金')
DIRECTIONAL_CUES=('涨','跌','增','减','盈','亏','风险','停牌','减持','增持','回购','中标','投产','业绩','利润','收入','净利','突破','新高','走强','走弱','重挫','涨停','跌停','扭亏','翻倍','下降','上涨','下跌')


def pre_reject(title,text,association):
    """Return the first deterministic reject reason, or None when the binary model may run."""
    title=title or '';text=text or ''
    company_in_title=any(alias in title for alias in COMPANY_ALIASES)
    if not company_in_title and any(marker in title for marker in MARKET_INDEX_MARKERS):return 'ABSTAIN_MARKET_INDEX'
    if not company_in_title and any(marker in title for marker in FUND_FLOW_MARKERS):return 'ABSTAIN_FUND_FLOW'
    if not any(cue in text for cue in DIRECTIONAL_CUES):return 'ABSTAIN_NO_DIRECTIONAL_CUE'
    if association in ('INDUSTRY_BACKGROUND','UNRELATED'):return 'ABSTAIN_RELEVANCE'
    return None


def final_label(prob_positive,prob_negative,pre_reason):
    if pre_reason:return None,None,pre_reason
    confidence=max(prob_positive,prob_negative)
    if confidence<CONFIDENCE_FLOOR:return None,confidence,'ABSTAIN_LOW_CONFIDENCE'
    return ('POSITIVE' if prob_positive>=prob_negative else 'NEGATIVE'),confidence,None

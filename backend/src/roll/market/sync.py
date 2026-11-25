"""On-demand synchronization shared by the local CLI and HTTP server."""

from datetime import date

from roll.config import active_watchlist, load_watchlist
from roll.market.daily import sync_market
from roll.market.financials import sync_financials
from roll.market.inputs import BACKFILL_GROUPS, sync_inputs


def sync_workbench(
    data_dir, start=None, end=None, *, scope="all", watchlist=None, groups=None
):
    if scope == "backfill":
        if not start or not end or not 0 <= (date.fromisoformat(end) - date.fromisoformat(start)).days < 93:
            raise ValueError("历史补库须指定起止日期，每次最多 93 个自然日")
        if groups and "breadth" in groups:
            raise ValueError("当前市场广度来源仅提供当日快照，不支持历史补库")
        return {
            "daily": sync_market(data_dir, start, end, index_only=True),
            "market_inputs": sync_inputs(data_dir, start, end, groups=groups or BACKFILL_GROUPS,
                                         missing_only=True),
        }
    if scope in {"financials", "inputs"}:
        items = load_watchlist(watchlist) if watchlist else active_watchlist(data_dir)
        if scope == "financials":
            return sync_financials(data_dir, [item["code"] for item in items])
        return sync_inputs(
            data_dir,
            start,
            end,
            groups=groups,
            sector_etfs=[item["sector_etf"] for item in items],
        )
    daily = sync_market(data_dir, start, end, watchlist=watchlist, recent_only=scope == "all")
    if scope == "daily":
        return daily
    items = active_watchlist(data_dir)
    return {
        "daily": daily,
        "market_inputs": sync_inputs(
            data_dir,
            start,
            end,
            groups=groups,
            sector_etfs=[item["sector_etf"] for item in items],
        ),
        "financials": sync_financials(data_dir, [item["code"] for item in items]),
    }

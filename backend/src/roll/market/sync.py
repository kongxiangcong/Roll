"""On-demand synchronization shared by the local CLI and HTTP server."""

from roll.config import active_watchlist, load_watchlist
from roll.market.daily import sync_market
from roll.market.financials import sync_financials
from roll.market.inputs import sync_inputs


def sync_workbench(
    data_dir, start=None, end=None, *, scope="all", watchlist=None, groups=None
):
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
    daily = sync_market(data_dir, start, end, watchlist=watchlist)
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

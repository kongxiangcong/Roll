import { useState } from "react";
import {
  api,
  fmt,
  pct,
  stamp,
  Panel,
  Message,
  Metric,
  useRead,
  post,
} from "../ui";
import type { Numeric } from "../ui";

type Quote = {
  symbol: string;
  kind: string;
  close: Numeric;
  first_date: string | null;
  last_date: string | null;
  count: number;
  error: string | null;
  gaps: { start: string; end: string; error: string }[];
};
type MarketData = {
  barometer: {
    score: Numeric;
    coverage: number;
    position_cap: Numeric;
    regime: string | null;
    dimensions: Record<string, number | null>;
    missing: string[];
  };
  market: Quote[];
  inputs: {
    series: string;
    symbol: string;
    first_date: string;
    last_date: string;
    count: number;
    last_error: string | null;
  }[];
  calibration: { mature_sample_count: number; probability: number | null };
};
type Receipt = {
  error?: string;
  last_error?: string;
  symbol?: string;
  series?: string;
};
const dimensions: Record<string, string> = {
  trend: "趋势与波动",
  funding: "资金",
  breadth: "全市场广度",
  valuation: "估值",
};
const seriesNames: Record<string, string> = {
  etf_bars: "ETF 日线",
  etf_shares: "ETF 份额",
  etf_nav: "单位净值",
  margin: "两融余额",
  breadth: "全市场广度",
  turnover: "成交额",
  valuation: "指数估值",
  calendar: "交易日历",
};
const names: Record<string, string> = {
  "600362.SH": "江西铜业",
  "000300.SH": "沪深 300",
  "600150.SH": "中国船舶",
  "603083.SH": "剑桥科技",
};
export default function Market({ day }: { day: string }) {
  const [revision, refresh] = useState(0),
    { data, error } = useRead<MarketData>("/api/market?day=" + day, revision);
  const [scope, setScope] = useState("all"),
    [start, setStart] = useState(""),
    [busy, setBusy] = useState("");
  const [note, setNote] = useState(""),
    [fault, setFault] = useState(""),
    [frozen, setFrozen] = useState("");
  const b = data?.barometer;
  async function sync() {
    setBusy("sync");
    setFault("");
    setNote("");
    try {
      const result = await post<Receipt[] | Record<string, Receipt[]>>(
        "/api/sync",
        { scope, start: start || null, end: day },
      );
      const rows = Array.isArray(result)
        ? result
        : Object.values(result).flat();
      const failed = rows.filter((r) => r.error || r.last_error);
      setNote(
        `同步完成 · ${rows.length - failed.length} 项成功，${failed.length} 项失败` +
          (failed.length
            ? "。" +
              failed
                .slice(0, 4)
                .map((r) =>
                  [r.symbol, r.series, r.error || r.last_error]
                    .filter(Boolean)
                    .join(" "),
                )
                .join("；")
            : ""),
      );
      refresh((n) => n + 1);
    } catch (e) {
      setFault((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function report(read: boolean) {
    setBusy("report");
    setFault("");
    setNote("");
    try {
      const result = await api<{ cutoff_at: string }>(
        read ? `/api/reports/${day}/export?format=json` : `/api/reports/${day}`,
        { method: read ? "GET" : "POST" },
      );
      setFrozen(result.cutoff_at);
    } catch (e) {
      setFault((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  return (
    <>
      <Message error={fault || error} text={note} />
      {!data && !error && <Message text="读取盘后行情…" />}
      {b && (
        <>
          <section className="hero">
            <div>
              <span className="smallcap">市场总分</span>
              <div className="score">
                {fmt(b.score, 1)}
                <small>/ 100</small>
              </div>
              <div className="hero-state">
                {b.regime ? b.regime + "档" : "今日晴雨表不可用"}
              </div>
            </div>
            <div className="hero-detail">
              <Metric label="总仓位上限" value={pct(b.position_cap)} />
              <Metric label="数据覆盖率" value={pct(b.coverage)} />
            </div>
          </section>
          <div className="two">
            <Panel title="四维得分">
              <div className="bars">
                {Object.entries(dimensions).map(([key, label]) => (
                  <div key={key}>
                    <span>{label}</span>
                    <div className="track">
                      <i style={{ width: (b.dimensions[key] || 0) + "%" }} />
                    </div>
                    <b>{fmt(b.dimensions[key], 1)}</b>
                  </div>
                ))}
              </div>
              {b.missing.length > 0 && (
                <details>
                  <summary>查看 {b.missing.length} 项缺失输入</summary>
                  <ul>
                    {b.missing.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ul>
                </details>
              )}
            </Panel>
            <Panel title="同档历史校准">
              <div className="stats">
                <Metric
                  label="20 日上涨频率"
                  value={pct(data!.calibration.probability)}
                />
                <Metric
                  label="已成熟样本"
                  value={data!.calibration.mature_sample_count}
                />
              </div>
              <a href={"/validation?day=" + day}>查看回测与校准 →</a>
            </Panel>
          </div>
          <Panel
            title="收盘行情"
            action={<span className="muted">原始口径</span>}
          >
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th>标的</th>
                    <th>收盘价 / 点位</th>
                    <th>最近交易日</th>
                    <th>历史覆盖</th>
                  </tr>
                </thead>
                <tbody>
                  {data!.market.map((q) => (
                    <tr key={q.symbol}>
                      <td>
                        <b>{names[q.symbol] || q.symbol}</b>
                        <small>{q.symbol}</small>
                      </td>
                      <td>{fmt(q.close)}</td>
                      <td>{q.last_date || "暂无"}</td>
                      <td>
                        {q.first_date || "—"} · {q.count} 日
                        {q.error && <small className="warn">{q.error}</small>}
                        {q.gaps?.map((g) => (
                          <small key={g.start} className="warn">
                            {g.start} 至 {g.end} · {g.error}
                          </small>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      )}
      <div className="two">
        <Panel title="同步数据">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void sync();
            }}
          >
            <div className="fields">
              <label>
                数据范围
                <select
                  value={scope}
                  onChange={(e) => setScope(e.target.value)}
                >
                  <option value="all">全部盘后数据</option>
                  <option value="daily">股票与指数日线</option>
                  <option value="inputs">ETF 与市场输入</option>
                  <option value="financials">跟踪股财报</option>
                </select>
              </label>
              <label>
                起始日（留空增量）
                <input
                  type="date"
                  value={start}
                  max={day}
                  onChange={(e) => setStart(e.target.value)}
                />
              </label>
            </div>
            <button disabled={!!busy}>
              {busy === "sync" ? "同步中…" : "同步数据"}
            </button>
          </form>
          {!!data?.inputs.length && (
            <details>
              <summary>市场输入覆盖</summary>
              {data.inputs.map((r) => (
                <p key={r.series + r.symbol}>
                  {seriesNames[r.series] || r.series} · {r.symbol} ·{" "}
                  {r.first_date || "—"} 至 {r.last_date || "—"} · {r.count} 条{" "}
                  {r.last_error}
                </p>
              ))}
            </details>
          )}
        </Panel>
        <Panel title="冻结日报">
          <p className="muted">
            {frozen
              ? "冻结截止 " + stamp(frozen)
              : "首次生成后固定当日内容和截止时间。"}
          </p>
          <div className="actions">
            <button disabled={!!busy} onClick={() => report(false)}>
              冻结日报
            </button>
            <button
              className="ghost"
              disabled={!!busy}
              onClick={() => report(true)}
            >
              重读日报
            </button>
          </div>
          {frozen && (
            <div className="exports">
              <a href={`/api/reports/${day}/export?format=json`}>下载 JSON</a>
              <a href={`/api/reports/${day}/export?format=markdown`}>
                下载 Markdown
              </a>
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}

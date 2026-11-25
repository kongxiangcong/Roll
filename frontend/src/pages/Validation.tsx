import { useEffect, useRef, useState } from "react";
import { api, fmt, pct, Panel, Message, Metric } from "../ui";
import type { Numeric } from "../ui";

type Line = { trade_date: string; net_value: number | null };
type Leg = {
  status: string;
  metrics: Record<string, number | null>;
  curve: Line[];
  trades: {
    trade_date: string;
    side: string;
    shares: number;
    price: string;
    fee_yuan: string;
  }[];
};
type Period = {
  period: string;
  start: string;
  end: string;
  sessions: number;
  valid_signals: number;
  missing_signals: number;
  missing_prices: { trade_date: string; fields: string[] }[];
  strategy: Leg;
  buy_hold: Leg;
};
type Result = {
  status: string;
  fees: Record<string, string>;
  periods: Period[];
  basis: string;
};
type Calibration = {
  by_regime: Record<
    string,
    {
      brier: Numeric;
      brier_count: number;
      mature_count: number;
      up_frequency: Numeric;
    }
  >;
  forward: {
    trading_days: number;
    registered_count: number;
    mature_count: number;
    brier: Numeric;
    brier_count: number;
  };
};

function Curve({ period }: { period: Period }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    function draw() {
      if (!el) return;
      const rect = el.getBoundingClientRect(),
        ratio = window.devicePixelRatio || 1;
      el.width = Math.max(1, rect.width * ratio);
      el.height = Math.max(1, rect.height * ratio);
      const ctx = el.getContext("2d");
      if (!ctx) return;
      ctx.scale(ratio, ratio);
      const lines = [period.strategy.curve, period.buy_hold.curve],
        vals = lines.flatMap((l) =>
          l.flatMap((p) => (p.net_value == null ? [] : [p.net_value])),
        );
      if (!vals.length) return;
      let min = Math.min(1, ...vals),
        max = Math.max(1, ...vals);
      if (max === min) {
        min -= 0.01;
        max += 0.01;
      }
      const left = 45,
        w = rect.width - left - 6,
        h = rect.height - 26;
      ctx.font = "11px system-ui";
      ctx.fillStyle = "#67716c";
      for (let i = 0; i <= 3; i++) {
        const y = 5 + (h * i) / 3;
        ctx.strokeStyle = "#dbe4df";
        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(left + w, y);
        ctx.stroke();
        ctx.fillText((max - ((max - min) * i) / 3).toFixed(2), 2, y + 4);
      }
      lines.forEach((line, index) => {
        let last = false;
        ctx.beginPath();
        ctx.lineWidth = 2;
        ctx.strokeStyle = index ? "#c88745" : "#177d68";
        line.forEach((r, i) => {
          if (r.net_value == null) {
            last = false;
            return;
          }
          const x = left + (i * w) / Math.max(1, line.length - 1),
            y = 5 + ((max - r.net_value) * h) / (max - min);
          if (last) ctx.lineTo(x, y);
          else ctx.moveTo(x, y);
          last = true;
        });
        ctx.stroke();
      });
    }
    const observer = new ResizeObserver(draw);
    observer.observe(el);
    draw();
    return () => observer.disconnect();
  }, [period]);
  return (
    <div className="plot">
      <span>
        <i />
        晴雨表控仓 <i />
        买入持有
      </span>
      <canvas ref={canvas} aria-label={period.period + "扣费净值曲线"} />
      <small>
        {period.start} — {period.end}
      </small>
    </div>
  );
}

export default function Validation({ day }: { day: string }) {
  const [start, setStart] = useState(
      day < "2024-01-01" ? "2020-01-01" : "2024-01-01",
    ),
    [end, setEnd] = useState(day);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [result, setResult] = useState<Result>(),
    [cal, setCal] = useState<Calibration>();
  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setResult(undefined);
    setCal(undefined);
    try {
      const args = "?start=" + start + "&end=" + end;
      const [r, c] = await Promise.all([
        api<Result>("/api/backtest" + args),
        api<Calibration>("/api/calibration" + args),
      ]);
      setResult(r);
      setCal(c);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Panel title="510300.SH · 沪深 300 ETF">
        <form onSubmit={run} className="range">
          <label>
            回测起始日
            <input
              type="date"
              value={start}
              max={end}
              required
              onChange={(e) => setStart(e.target.value)}
            />
          </label>
          <label>
            回测截止日
            <input
              type="date"
              value={end}
              min={start}
              max={day}
              required
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
          <button disabled={busy}>
            {busy ? "正在计算…" : "运行回测与校准"}
          </button>
        </form>
        <p className="muted">
          以同一只 ETF 的买入持有为对照，比较扣费后净值。2024 年起为样本外区间。
        </p>
      </Panel>
      <Message error={error} text={result?.status} />
      {result?.periods.map((p) => (
        <Panel
          key={p.period}
          title={p.period + " · 扣费净值"}
          action={
            <span className="muted">
              {p.valid_signals} / {p.sessions} 日有档位
            </span>
          }
        >
          <Curve period={p} />
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>组合</th>
                  <th>期末净值</th>
                  <th>年化收益</th>
                  <th>最大回撤</th>
                  <th>卡玛</th>
                  <th>换手</th>
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ["晴雨表控仓", p.strategy],
                    ["买入持有", p.buy_hold],
                  ] as const
                ).map(([label, l]) => (
                  <tr key={label}>
                    <td>
                      <b>{label}</b>
                      <small>{l.status}</small>
                    </td>
                    <td>{fmt(l.metrics.net_value, 4)}</td>
                    <td>{pct(l.metrics.annual_return)}</td>
                    <td>{pct(l.metrics.maximum_drawdown)}</td>
                    <td>{fmt(l.metrics.calmar)}</td>
                    <td>{pct(l.metrics.turnover)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <details>
            <summary>
              行情缺口 {p.missing_prices.length} 日 · 信号缺失{" "}
              {p.missing_signals} 日
            </summary>
            {p.missing_prices.length ? (
              p.missing_prices.map((r) => (
                <p key={r.trade_date}>
                  {r.trade_date} · {r.fields.join(" / ")}
                </p>
              ))
            ) : (
              <p>该段原始开盘价与收盘价完整。</p>
            )}
          </details>
        </Panel>
      ))}
      {result && (
        <Panel title="成交与费用口径">
          <p>{result.basis}</p>
          <p>
            佣金 {pct(result.fees.commission_rate)}，每笔最低 ¥
            {result.fees.minimum_commission_yuan}；过户费{" "}
            {pct(result.fees.transfer_rate)}，卖出税率{" "}
            {pct(result.fees.sell_tax_rate)}，单边滑点{" "}
            {pct(result.fees.slippage_rate)}。
          </p>
        </Panel>
      )}
      {cal && (
        <>
          <Panel title="历史四档校准">
            <div className="scroll">
              <table>
                <thead>
                  <tr>
                    <th>档位</th>
                    <th>成熟样本</th>
                    <th>20 日上涨频率</th>
                    <th>Brier</th>
                    <th>Brier 分母</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(cal.by_regime).map(([k, r]) => (
                    <tr key={k}>
                      <td>{k}</td>
                      <td>{r.mature_count}</td>
                      <td>{pct(r.up_frequency)}</td>
                      <td>{fmt(r.brier, 4)}</td>
                      <td>{r.brier_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel title="实际冻结的前向预测">
            <div className="stats">
              <Metric label="交易日数" value={cal.forward.trading_days} />
              <Metric label="登记预测" value={cal.forward.registered_count} />
              <Metric label="已成熟" value={cal.forward.mature_count} />
              <Metric
                label="Brier / 分母"
                value={
                  fmt(cal.forward.brier, 4) + " / " + cal.forward.brier_count
                }
              />
            </div>
          </Panel>
        </>
      )}
    </>
  );
}

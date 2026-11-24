import { useState, useEffect } from "react";
import {
  api,
  post,
  useRead,
  pct,
  fmt,
  stamp,
  Info,
  Metric,
  Panel,
  Message,
} from "../ui";
import type { Numeric } from "../ui";

type Account = {
  version: number;
  cash_balance: string | null;
  confirmed_at: string | null;
};
type Card = {
  symbol: string;
  name: string | null;
  quantity: string;
  trade_date: string | null;
  close: Numeric;
  price_stale: boolean;
  account_stale: boolean;
  position_cap: Numeric;
  position_fraction: Numeric;
  sector_etf: string | null;
  sector_excess_return20: Numeric;
  sector_net_flow5_yuan: Numeric;
  atr14: Numeric;
  atr_stop_multiplier: Numeric;
  atr_stop_price: Numeric;
  atr_stop_breached: boolean | null;
  previous_low20: Numeric;
  below_low20: boolean | null;
  single_overage: Numeric;
  reference_shares: number | null;
  sellable_quantity: Numeric;
  missing: string[];
  account_effective_at: string | null;
  financial_light: {
    unverified_versions?: { period: string; source: string; missing: string }[];
    status: string;
    report_period: string | null;
    announce_date: string | null;
    reasons: string[];
    missing: string[];
  };
};
type Risk = {
  portfolio: {
    assets: Numeric;
    market_value: Numeric;
    position_fraction: Numeric;
    position_cap: Numeric;
    overage_amount: Numeric;
    overage_percentage_points: Numeric;
    missing: string[];
  };
  cards: Card[];
  account_confirmed_at: string | null;
  market_cutoff_at: string;
};
type Draft = {
  draft_id: string;
  status: string;
  preview: Record<string, { before: unknown; after: unknown }>;
  issues: unknown[];
};
type Reconciled = {
  receipt_id: string;
  account_version: number;
  cash_balance: string;
  positions: { instrument: string; quantity: string }[];
};

function LedgerForm({
  day,
  account,
  done,
}: {
  day: string;
  account: Account;
  done: () => void;
}) {
  const [kind, pick] = useState(account.version === 0 ? "BASELINE" : "CASH_IN");
  const [pending, stage] = useState<Draft>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [receipt, setReceipt] = useState<Reconciled>();
  async function preview(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setReceipt(undefined);
    const form = new FormData(event.currentTarget),
      get = (k: string) => String(form.get(k) || "").trim();
    try {
      let draft: Draft;
      if (kind === "CSV") {
        const file = form.get("file") as File;
        draft = await api<Draft>(
          `/api/account/import?filename=${encodeURIComponent(file.name)}&version=${account.version}&encoding=${get("encoding")}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/octet-stream" },
            body: file,
          },
        );
      } else {
        const base = {
          source: get("source"),
          effective_at: get("time") + ":00+08:00",
        };
        let payload: Record<string, unknown>;
        if (kind === "BASELINE")
          payload = {
            ...base,
            cash_balance: get("amount"),
            positions: [],
            permission_profile: [],
            broker_available: null,
            broker_frozen: null,
            withdrawable: null,
          };
        else if (kind === "FILL") {
          const [code, exchange] = get("symbol").toUpperCase().split(".");
          const exchanges: Record<string, string> = {
            SH: "SSE",
            SZ: "SZSE",
            BJ: "BSE",
          };
          if (!/^\d{6}$/.test(code) || !exchanges[exchange])
            throw Error("证券代码请填写 600362.SH 这样的格式");
          payload = {
            ...base,
            record_id: crypto.randomUUID(),
            instrument: exchanges[exchange] + ":" + code,
            direction: get("direction"),
            quantity: get("qty"),
            price: get("price"),
            behavior_context: "OFFLINE",
            fee: {
              status: "KNOWN",
              amount: get("fee"),
              reserve_amount: null,
              basis: get("source"),
            },
            fill_id: get("fill") || null,
            order_id: null,
            broker_available_after: null,
          };
        } else
          payload = {
            ...base,
            record_id: crypto.randomUUID(),
            amount: get("amount"),
            basis: get("source"),
            instrument: null,
            broker_available_after: null,
          };
        draft = await post<Draft>("/api/account/drafts", {
          kind,
          expected_account_version: account.version,
          payload,
        });
      }
      stage(draft);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function confirm() {
    if (!pending) return;
    setBusy(true);
    setError("");
    try {
      const r = await post<{ receipt_id: string }>("/api/account/confirm", {
        draft_id: pending.draft_id,
        idempotency_key: pending.draft_id,
      });
      const checked = await api<Reconciled>(
        "/api/account/receipts/" + r.receipt_id,
      );
      stage(undefined);
      setReceipt(checked);
      pick("CASH_IN");
      done();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Panel title="账户记账">
      <Message error={error} />
      {receipt && (
        <div className="message" role="status">
          已确认入账 · 回执版本 {receipt.account_version} · 现金 ¥
          {fmt(receipt.cash_balance)}{" "}
          {receipt.positions.map((p) => (
            <small key={p.instrument}>
              {p.instrument} {p.quantity} 股
            </small>
          ))}
        </div>
      )}
      {!pending ? (
        <form onSubmit={preview}>
          <div className="fields">
            <label>
              记录类型
              <select value={kind} onChange={(e) => pick(e.target.value)}>
                {account.version === 0 ? (
                  <option value="BASELINE">建立账户基线</option>
                ) : (
                  <>
                    <option value="CASH_IN">资金转入</option>
                    <option value="CASH_OUT">资金转出</option>
                    <option value="FILL">记录实际成交</option>
                  </>
                )}
                <option value="CSV">导入成交 CSV</option>
              </select>
            </label>
            {kind === "CSV" ? (
              <>
                <label>
                  CSV 文件
                  <input type="file" name="file" accept=".csv" required />
                </label>
                <label>
                  文件编码
                  <select name="encoding">
                    <option>utf-8-sig</option>
                    <option>gb18030</option>
                  </select>
                </label>
                <a href="/api/account/template">下载 CSV 模板</a>
              </>
            ) : (
              <>
                <label>
                  发生时间（上海）
                  <input
                    type="datetime-local"
                    key={day}
                    name="time"
                    defaultValue={day + "T14:55"}
                    required
                  />
                </label>
                {kind === "FILL" ? (
                  <>
                    <label>
                      证券代码
                      <input name="symbol" required placeholder="600362.SH" />
                    </label>
                    <label>
                      成交方向
                      <select name="direction">
                        <option value="BUY">买入</option>
                        <option value="SELL">卖出</option>
                      </select>
                    </label>
                    <label>
                      成交数量（股）
                      <input
                        name="qty"
                        type="number"
                        min="0.00000001"
                        step="any"
                        required
                      />
                    </label>
                    <label>
                      成交价格（元）
                      <input
                        name="price"
                        type="number"
                        min="0.00000001"
                        step="any"
                        required
                      />
                    </label>
                    <label>
                      实际费用（元）
                      <input
                        name="fee"
                        type="number"
                        min="0"
                        step=".01"
                        required
                      />
                    </label>
                    <label>
                      成交编号（选填）
                      <input name="fill" />
                    </label>
                  </>
                ) : (
                  <label>
                    {kind === "BASELINE" ? "初始现金（元）" : "金额（元）"}
                    <input
                      name="amount"
                      type="number"
                      min={kind === "BASELINE" ? "0" : ".01"}
                      step=".01"
                      required
                    />
                  </label>
                )}
                <label>
                  凭据来源
                  <input
                    name="source"
                    placeholder="券商交割单或银行流水"
                    required
                  />
                </label>
              </>
            )}
          </div>
          {kind === "BASELINE" && (
            <p className="muted">
              此表建立空持仓基线。已有持仓可使用 CSV 同时导入。
            </p>
          )}
          <button disabled={busy}>预览记账</button>
        </form>
      ) : (
        <div className="preview">
          <strong>记账预览</strong>
          <Info
            rows={Object.entries(pending.preview)
              .filter(([, x]) => typeof x.after !== "object")
              .slice(0, 8)
              .map(([k, x]) => [
                (
                  {
                    cash_balance: "现金余额",
                    version: "版本",
                    effective_at: "生效时间",
                  } as Record<string, string>
                )[k] || k,
                String(x.after),
              ])}
          />
          {!!pending.issues?.length && (
            <pre>{JSON.stringify(pending.issues, null, 2)}</pre>
          )}
          <details>
            <summary>完整变更</summary>
            <pre>{JSON.stringify(pending.preview, null, 2)}</pre>
          </details>
          <div className="actions">
            <button
              onClick={confirm}
              disabled={busy || pending.status !== "READY"}
            >
              确认入账
            </button>
            <button
              className="ghost"
              disabled={busy}
              onClick={() => stage(undefined)}
            >
              返回修改
            </button>
          </div>
        </div>
      )}
    </Panel>
  );
}
export default function Holdings({ day }: { day: string }) {
  const [revision, refresh] = useState(0),
    [account, setAccount] = useState<Account>();
  const risk = useRead<Risk>("/api/risk?day=" + day, revision);
  const [error, setError] = useState("");
  // Preserve the form and its confirmation receipt while balances reload.
  useEffect(() => {
    api<Account>("/api/account")
      .then(setAccount)
      .catch((e) => setError(e.message));
  }, []);
  function done() {
    api<Account>("/api/account")
      .then(setAccount)
      .catch((e) => setError(e.message));
    refresh((x) => x + 1);
  }
  const p = risk.data?.portfolio;
  return (
    <>
      <Message error={error || risk.error} />
      <div className="stats strip">
        <Metric label="账户资产" value={"¥ " + fmt(p?.assets)} />
        <Metric
          label="当前账本现金"
          value={"¥ " + fmt(account?.cash_balance)}
        />
        <Metric label="实际仓位" value={pct(p?.position_fraction)} />
        <Metric label="晴雨表上限" value={pct(p?.position_cap)} />
      </div>
      {p?.overage_amount != null && (
        <Message
          text={`总仓位超限 ${fmt(p.overage_percentage_points)} 个百分点，合计 ¥${fmt(p.overage_amount)}`}
        />
      )}
      {!!p?.missing.length && <p className="muted">{p.missing.join(" · ")}</p>}
      {account && <LedgerForm day={day} account={account} done={done} />}
      <Panel
        title="持仓与跟踪池"
        action={<span className="muted">YAML 配置 · 只读</span>}
      >
        <p className="muted">
          账户确认 {stamp(risk.data?.account_confirmed_at)}　行情截止{" "}
          {stamp(risk.data?.market_cutoff_at)}
        </p>
        {risk.data?.cards.length === 0 && (
          <p>暂无持仓或生效跟踪池。同步后读取 YAML 中的标的与参数。</p>
        )}
        <div className="cards">
          {risk.data?.cards.map((c) => (
            <article className="stock" key={c.symbol}>
              <h3>
                {c.name || c.symbol}
                <small>{c.symbol}</small>
              </h3>
              <Info
                rows={[
                  [
                    "收盘 / 日期",
                    fmt(c.close) +
                      " · " +
                      (c.trade_date || "暂无") +
                      (c.price_stale ? " · 行情过期" : ""),
                  ],
                  [
                    "账户有效时点",
                    stamp(c.account_effective_at) +
                      (c.account_stale ? " · 待复核" : ""),
                  ],
                  [
                    "持仓 / 可卖",
                    fmt(c.quantity) + " / " + fmt(c.sellable_quantity) + " 股",
                  ],
                  [
                    "仓位 / 单票上限",
                    pct(c.position_fraction) + " / " + pct(c.position_cap),
                  ],
                  ["行业 ETF", c.sector_etf || "—"],
                  ["行业 20 日超额收益", pct(c.sector_excess_return20)],
                  [
                    "行业 ETF 近 5 日净流入（元）",
                    fmt(c.sector_net_flow5_yuan),
                  ],
                  [
                    "ATR14 / 止损倍数",
                    fmt(c.atr14, 3) + " / " + fmt(c.atr_stop_multiplier),
                  ],
                  [
                    "移动止损价",
                    fmt(c.atr_stop_price) +
                      (c.atr_stop_breached ? " · 已跌破" : ""),
                  ],
                  [
                    "前 20 日最低收盘",
                    fmt(c.previous_low20) + (c.below_low20 ? " · 已跌破" : ""),
                  ],
                  [
                    "财报灯",
                    (
                      {
                        red: "红灯",
                        green: "绿灯",
                        unknown: "资料不足",
                      } as Record<string, string>
                    )[c.financial_light.status],
                  ],
                ]}
              />
              {c.single_overage != null && (
                <p className="warn">
                  单票超限 ¥{fmt(c.single_overage)} · 参考{" "}
                  {fmt(c.reference_shares)} 股
                </p>
              )}
              <details>
                <summary>财报与数据缺项</summary>
                <p>
                  报告期 {c.financial_light.report_period || "—"} · 披露{" "}
                  {c.financial_light.announce_date || "—"}
                </p>
                {[
                  ...c.financial_light.reasons,
                  ...c.financial_light.missing,
                  ...(c.financial_light.unverified_versions || []).map(
                    (v) => v.period + " · " + v.source + " · " + v.missing,
                  ),
                  ...c.missing,
                ].map((v, i) => (
                  <p key={i}>{v}</p>
                ))}
              </details>
            </article>
          ))}
        </div>
      </Panel>
    </>
  );
}

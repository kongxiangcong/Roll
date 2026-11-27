/* Roll v3 Spatial Workbench — Zero evidence, zero audit, layout-driven UI */
const app = document.querySelector("#app");
const tradeDatePill = document.querySelector("#trade-date-pill");
const bookSelect = document.querySelector("#book-select");
const syncBtn = document.querySelector("#sync-btn");
const drawerBackdrop = document.querySelector("#drawer-backdrop");
const drawerBody = document.querySelector("#drawer-body");
const drawerClose = document.querySelector("#drawer-close");
const toastEl = document.querySelector("#toast");

const state = {
  view: "overview",
  symbol: "600362.SH",
  bookId: "real",
  labTab: "research",
  selectedTaskId: null,
  selectedDevTaskId: null,
  overview: null,
  pollTimer: null,
  syncTimer: null,
};

const LABELS = {
  WATCH: "观察", HOLD: "持有", BUY: "买入", SELL: "卖出", RISK_EXIT_PENDING: "待退出",
  uptrend: "多头", downtrend: "空头", range: "震荡", unknown: "—",
  pass: "通过", fail: "未通过", active: "有效", expired: "已过期", missing: "未建档",
  intact: "有效", watch: "观察", broken: "已证伪",
  admitted: "已准入", accepted: "历史通过", frozen: "已冻结", none: "未配置",
  pending: "排队中", running: "运行中", cancelling: "取消中",
  draft_ready: "待发布", report_ready: "已出结果", blocked: "缺项阻塞",
  cancelled: "已取消", interrupted: "已中断", failed: "失败", timed_out: "超时",
  FILLED: "已成交", UNFILLED: "未成交", PARTIAL: "部分成交", PENDING: "待确认",
  OBSERVED: "已观察", UNREPORTED: "待录入", DEVIATION: "执行偏差",
  CONFIRMED: "已确认", REJECTED: "已拒绝", NOT_EXECUTED: "未执行",
  actions_identical: "动作一致", single_segment: "集中于单段",
  evidence_insufficient: "样本不足", multiple_segments: "多段存在差异",
  stop: "停止扩展", continue: "继续研究",
};

const fmtNum = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 });
const el = (tag, attrs = {}, ...children) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") node.className = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v === true ? "" : String(v));
  }
  node.append(...children.flat().filter(c => c !== null && c !== undefined && c !== false));
  return node;
};

const label = v => LABELS[v] ?? (v ?? "—");
const money = v => v == null ? "—" : `¥${fmtNum.format(Number(v))}`;
const price = v => v == null ? "—" : Number(v).toFixed(2);
const pct = (v, signed = false) => {
  if (v == null) return "—";
  const n = Number(v) * 100;
  return `${signed && n > 0 ? "+" : ""}${n.toFixed(2)}%`;
};
const deltaClass = v => v == null || Number(v) === 0 ? "muted" : Number(v) > 0 ? "up" : "down";
const actionPillClass = a => a === "BUY" ? "pill pill-up" : a === "SELL" ? "pill pill-down" : a === "HOLD" ? "pill pill-primary" : "pill";
const gatePillClass = g => g === "pass" ? "pill pill-down" : g === "fail" ? "pill pill-up" : "pill pill-warn";
const thesisPillClass = t => t === "intact" ? "pill pill-down" : t === "broken" ? "pill pill-up" : "pill pill-warn";

let toastTimer = null;
function showToast(msg, isError = false) {
  toastEl.textContent = msg;
  toastEl.className = isError ? "toast error" : "toast";
  toastEl.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastEl.hidden = true; }, 3200);
}

async function api(path, { method = "GET", params, body } = {}) {
  const url = new URL(path, location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== "") url.searchParams.set(k, v);
    }
  }
  const opts = { method };
  if (body !== undefined) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(i => i.msg).join("，") : data.detail;
    throw new Error(detail || `请求失败 (${res.status})`);
  }
  return data;
}

function go(view, symbol = state.symbol, labTab = state.labTab) {
  state.view = view;
  if (symbol) state.symbol = symbol;
  if (labTab) state.labTab = labTab;
  const hash = view === "overview" ? "#overview" : `#${view}/${encodeURIComponent(state.symbol)}`;
  if (location.hash === hash) render();
  else location.hash = hash;
}

function parseHash() {
  const raw = location.hash.slice(1) || "overview";
  const [view, encodedSymbol] = raw.split("/");
  if (["overview", "decision", "lab"].includes(view)) state.view = view;
  else state.view = "overview";
  if (encodedSymbol) state.symbol = decodeURIComponent(encodedSymbol).toUpperCase();
}

function updateNav() {
  for (const a of document.querySelectorAll(".seg-nav a")) {
    if (a.dataset.view === state.view) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
}

/* ---------- Account Detail Drawer ---------- */
function openAccountDrawer(acct) {
  drawerBody.replaceChildren(
    el("div", { class: "kpi-grid-2" },
      kpi("总资产", money(acct.total_nav)),
      kpi("可用现金", money(acct.available_cash)),
      kpi("持仓市值", money(acct.holdings_value)),
      kpi("在途权益", money(acct.receivables_value)),
    ),
    acct.risk_budget ? el("div", { class: "stack" },
      el("div", { class: "strip-label" }, "风险预算"),
      el("div", { class: "kpi-grid-2" },
        kpi("现金保留", money(acct.risk_budget.cash_reserve)),
        kpi("总仓上限", pct(acct.risk_budget.max_total_exposure)),
        kpi("单票上限", pct(acct.risk_budget.max_symbol_exposure)),
        kpi("行业上限", pct(acct.risk_budget.max_industry_exposure)),
      ),
    ) : null,
    el("div", { class: "stack" },
      el("div", { class: "strip-label" }, "持仓批次"),
      acct.lots.length ? el("div", { class: "table-wrap" }, el("table", { class: "clean" },
        el("thead", {}, el("tr", {}, el("th", {}, "标的"), el("th", {}, "股数"), el("th", {}, "可卖"), el("th", {}, "市值"))),
        el("tbody", {}, acct.lots.map(lot => el("tr", {},
          el("td", {}, el("strong", {}, lot.name), el("div", { class: "watch-code" }, lot.symbol)),
          el("td", {}, String(lot.quantity)),
          el("td", {}, lot.sellable_quantity ?? "—"),
          el("td", {}, money(lot.market_value)),
        ))),
      )) : el("div", { class: "empty-state" }, "暂无持仓"),
    ),
    acct.receivables.length ? el("div", { class: "stack" },
      el("div", { class: "strip-label" }, "在途分红与送股"),
      el("div", { class: "table-wrap" }, el("table", { class: "clean" },
        el("thead", {}, el("tr", {}, el("th", {}, "标的"), el("th", {}, "金额"), el("th", {}, "股数"), el("th", {}, "结转日"))),
        el("tbody", {}, acct.receivables.map(r => el("tr", {},
          el("td", {}, r.name), el("td", {}, money(r.amount)), el("td", {}, r.quantity || "—"), el("td", {}, r.due_date || "—"),
        ))),
      )),
    ) : null,
  );
  drawerBackdrop.hidden = false;
}

drawerClose.addEventListener("click", () => { drawerBackdrop.hidden = true; });
drawerBackdrop.addEventListener("click", e => { if (e.target === drawerBackdrop) drawerBackdrop.hidden = true; });

function kpi(title, value, sub, subClass = "") {
  return el("div", { class: "kpi" },
    el("span", { class: "kpi-label" }, title),
    el("span", { class: `kpi-value ${subClass}` }, value ?? "—"),
    sub ? el("span", { class: `kpi-sub ${subClass}` }, sub) : null,
  );
}

/* ---------- Daily Sync ---------- */
async function pollSyncStatus() {
  clearTimeout(state.syncTimer);
  try {
    const st = await api("/api/market/sync/status");
    if (st.status === "running") {
      syncBtn.disabled = true;
      syncBtn.textContent = "同步中…";
      state.syncTimer = setTimeout(pollSyncStatus, 800);
    } else {
      syncBtn.disabled = false;
      syncBtn.textContent = "同步数据";
      if (st.status === "done") {
        showToast(st.error ? `同步完成（${st.error}）` : `已同步最新行情（新增 ${st.appended} 条）`);
        if (state.view === "overview") render();
      } else if (st.status === "error") {
        showToast(st.error || "行情同步失败", true);
      }
    }
  } catch {
    syncBtn.disabled = false;
    syncBtn.textContent = "同步数据";
  }
}

syncBtn.addEventListener("click", async () => {
  syncBtn.disabled = true;
  syncBtn.textContent = "同步中…";
  try {
    await api("/api/market/sync", { method: "POST", body: {} });
    pollSyncStatus();
  } catch (err) {
    syncBtn.disabled = false;
    syncBtn.textContent = "同步数据";
    showToast(err.message, true);
  }
});

bookSelect.addEventListener("change", () => {
  state.bookId = bookSelect.value;
  render();
});

/* ---------- View 1: Overview Cockpit ---------- */
async function renderOverview() {
  const ov = await api("/api/overview", { params: { book_id: state.bookId } });
  state.overview = ov;
  tradeDatePill.textContent = ov.trade_date || "暂无行情";
  if (ov.watchlist.length && !ov.watchlist.some(i => i.symbol === state.symbol)) {
    state.symbol = ov.watchlist[0].symbol;
  }

  const env = ov.market_env;
  const acct = ov.account_summary;
  const bench = env.benchmark;
  const etf = env.sector_etf;

  // Top Row: Market & ETF Card + Account Summary Card
  const marketCard = el("section", { class: "card" },
    el("div", { class: "card-head" },
      el("span", { class: "card-title" }, "市场与 ETF"),
      el("span", { class: bench.trend_state === "uptrend" ? "pill pill-up" : bench.trend_state === "downtrend" ? "pill pill-down" : "pill" },
        `沪深 300 · ${label(bench.trend_state)}`),
    ),
    el("div", { class: "kpi-grid-2" },
      kpi("沪深 300", price(bench.close), pct(bench.change_pct, true), deltaClass(bench.change_pct)),
      kpi(etf.name, price(etf.close), `20日 ${pct(etf.return_20d, true)}`, deltaClass(etf.return_20d)),
      kpi("大盘情绪", env.sentiment ?? "—"),
      kpi("宽基 ETF 流向", env.broad_etf_flow ?? "—"),
    ),
  );

  const posPct = acct.position_ratio != null ? Math.min(100, Math.max(0, acct.position_ratio * 100)) : 0;
  const accountCard = el("section", { class: "card" },
    el("div", { class: "card-head" },
      el("span", { class: "card-title" }, "个人账户"),
      el("button", { type: "button", class: "btn btn-ghost btn-sm", onclick: () => openAccountDrawer(acct) }, "明细"),
    ),
    el("div", { class: "hero-row" },
      el("div", { class: "hero-value" }, money(acct.total_nav)),
      acct.unrealized_pnl != null
        ? el("span", { class: `pill ${acct.unrealized_pnl >= 0 ? "pill-up" : "pill-down"}` },
            `${acct.unrealized_pnl >= 0 ? "+" : ""}${money(acct.unrealized_pnl)} (${pct(acct.unrealized_pnl_pct, true)})`)
        : el("span", { class: "pill" }, acct.initialized ? "已建账" : "未建账"),
    ),
    el("div", { class: "bar-track" }, el("div", { class: "bar-fill", style: `width:${posPct.toFixed(1)}%` })),
    el("div", { class: "kpi-grid-3" },
      kpi("总仓位", pct(acct.position_ratio)),
      kpi("可用现金", money(acct.available_cash)),
      kpi("仓位上限", acct.risk_budget ? pct(acct.risk_budget.max_total_exposure) : "—"),
    ),
  );

  // Middle Row: Watchlist Master + Linked Stock Focus Snapshot
  const addInput = el("input", { placeholder: "代码如 600150.SH", "aria-label": "新增自选股" });
  const addForm = el("form", {
    class: "inline-add",
    onsubmit: async e => {
      e.preventDefault();
      const code = addInput.value.trim();
      if (!code) return;
      try {
        await api("/api/watchlist", { method: "POST", body: { symbol: code } });
        state.symbol = code.toUpperCase();
        addInput.value = "";
        showToast(`已加入 ${state.symbol}`);
        render();
      } catch (err) { showToast(err.message, true); }
    },
  }, addInput, el("button", { type: "submit", class: "btn btn-sm" }, "+"));

  const focusContainer = el("section", { class: "card" });
  const listContainer = el("div", { class: "watch-list" });

  function paintMasterDetail() {
    const selected = ov.watchlist.find(item => item.symbol === state.symbol) || ov.watchlist[0];
    listContainer.replaceChildren(
      ...ov.watchlist.map(item => el("div", {
        class: `watch-row ${selected && item.symbol === selected.symbol ? "active" : ""}`,
        onclick: () => { state.symbol = item.symbol; paintMasterDetail(); },
      },
        el("div", {},
          el("div", { class: "watch-name" }, item.name),
          el("div", { class: "watch-code" }, `${item.symbol}${item.holding_shares ? ` · 持仓 ${pct(item.position_ratio)}` : ""}`),
        ),
        el("div", { class: "watch-price" },
          el("strong", {}, price(item.close)),
          el("span", { class: deltaClass(item.change_pct) }, pct(item.change_pct, true)),
        ),
        el("span", { class: actionPillClass(item.latest_plan?.action) }, label(item.latest_plan?.action || "WATCH")),
        el("div", { class: "watch-actions" },
          el("button", {
            type: "button", class: "btn btn-ghost btn-xs",
            onclick: e => { e.stopPropagation(); go("lab", item.symbol, "research"); },
          }, "研究"),
          el("button", {
            type: "button", class: "btn btn-ghost btn-xs",
            onclick: e => { e.stopPropagation(); go("decision", item.symbol); },
          }, "复盘"),
          item.in_watchlist && ov.watchlist.length > 1 ? el("button", {
            type: "button", class: "icon-btn", "aria-label": "移除",
            onclick: async e => {
              e.stopPropagation();
              await api(`/api/watchlist/${encodeURIComponent(item.symbol)}`, { method: "DELETE" });
              render();
            },
          }, "×") : null,
        ),
      )),
    );

    if (!selected) {
      focusContainer.replaceChildren(el("div", { class: "empty-state" }, "暂无自选标的"));
      return;
    }
    const m = selected.metrics;
    const d = selected.dossier;
    focusContainer.replaceChildren(
      el("div", { class: "strip-group" },
        el("div", { class: "focus-header" },
          el("div", { class: "focus-id" },
            el("h2", {}, selected.name),
            el("span", { class: "muted num" }, selected.symbol),
          ),
          el("div", { class: "focus-pills" },
            el("span", { class: gatePillClass(d.fundamental_gate) }, `基本面 · ${label(d.fundamental_gate)}`),
            el("span", { class: thesisPillClass(d.thesis_status) }, `逻辑 · ${label(d.thesis_status)}`),
          ),
        ),
        el("div", { class: "strip" },
          el("div", { class: "strip-label" }, "量价关系"),
          el("div", { class: "kpi-grid" },
            kpi("5 日", pct(m.return_5d, true), null, deltaClass(m.return_5d)),
            kpi("20 日", pct(m.return_20d, true), null, deltaClass(m.return_20d)),
            kpi("60 日", pct(m.return_60d, true), null, deltaClass(m.return_60d)),
            kpi("波动 / 回撤", pct(m.volatility_20d), `回撤 ${pct(m.max_drawdown_60d)}`),
          ),
        ),
        el("div", { class: "strip" },
          el("div", { class: "strip-label" }, "相对强弱与趋势"),
          el("div", { class: "kpi-grid-3" },
            kpi("对沪深 300 (20日)", pct(m.rel_benchmark_20d, true), null, deltaClass(m.rel_benchmark_20d)),
            kpi("对行业 (20日)", pct(m.rel_industry_20d, true), null, deltaClass(m.rel_industry_20d)),
            kpi("趋势结构", label(m.trend_state)),
          ),
        ),
        el("div", { class: "strip" },
          el("div", { class: "strip-label" }, "策略 · 概率 · 决策"),
          el("div", { class: "kpi-grid-3" },
            kpi("策略状态", label(selected.strategy.status)),
            kpi("决策概率", selected.probability ?? "—"),
            kpi("明日动作", label(selected.latest_plan?.action || "WATCH"), selected.latest_plan?.summary || ""),
          ),
        ),
        el("div", { class: "actions" },
          el("button", { type: "button", class: "btn btn-primary btn-sm", onclick: () => go("decision", selected.symbol) }, "进入决策与复盘"),
          el("button", { type: "button", class: "btn btn-sm", onclick: () => go("lab", selected.symbol, "research") }, "个股研究"),
          el("button", { type: "button", class: "btn btn-sm", onclick: () => go("lab", selected.symbol, "experiment") }, "策略实验"),
        ),
      ),
    );
  }

  paintMasterDetail();

  const watchlistCard = el("section", { class: "card" },
    el("div", { class: "card-head" }, el("span", { class: "card-title" }, "自选与持仓"), addForm),
    listContainer,
  );

  // Bottom Slim Review Todo Bar
  const todoBar = el("section", { class: "todo-bar" },
    el("span", { class: "card-title" }, "复盘中心"),
    el("div", { class: "todo-items" },
      ov.review_todos.map(t => el("button", {
        type: "button", class: "todo-chip",
        onclick: () => go("decision", t.symbol),
      },
        el("span", { class: "dot", style: "color:var(--warn)" }),
        el("strong", {}, t.name),
        el("span", { class: "muted" }, t.label),
      )),
    ),
  );

  app.replaceChildren(
    el("div", { class: "grid-2" }, marketCard, accountCard),
    el("div", { class: "grid-master" }, watchlistCard, focusContainer),
    todoBar,
  );
}

/* ---------- Symbol Switcher Bar ---------- */
function symbolBar(watchlist, targetView) {
  const items = watchlist?.length ? watchlist : [{ symbol: state.symbol, name: state.symbol }];
  return el("div", { class: "symbol-chips" },
    items.map(item => el("button", {
      type: "button",
      class: `chip ${item.symbol === state.symbol ? "active" : ""}`,
      onclick: () => go(targetView, item.symbol),
    }, item.name)),
  );
}

/* ---------- View 2: Stock Decision & Review ---------- */
function gateStatus(codes) {
  if (!codes || !codes.length) return { cls: "pass", text: "通过" };
  if (codes.some(c => /FAIL|BROKEN|SUSPENDED|FIRED/.test(c))) return { cls: "fail", text: "受阻" };
  if (codes.some(c => /MISSING|EXPIRED|UNKNOWN|WATCH|NOT_ADMITTED|NO_FEASIBLE|LIMIT|RESERVE/.test(c))) {
    return { cls: "block", text: "限制" };
  }
  return { cls: "pass", text: "通过" };
}

async function renderDecision() {
  const [watchlist, plans, reviews, strategies, followups] = await Promise.all([
    api("/api/watchlist"),
    api("/api/plans", { params: { book_id: state.bookId } }),
    api("/api/reviews", { params: { book_id: state.bookId } }),
    api(`/api/strategies/${encodeURIComponent(state.symbol)}`),
    api(`/api/research/${encodeURIComponent(state.symbol)}/followups`, { params: { mode: state.bookId === "real" ? "live" : "rehearsal" } }).catch(() => []),
  ]);

  const matchingPlans = plans.filter(p => p.symbol === state.symbol);
  let activePlan = matchingPlans.at(-1) || null;
  const latestReview = reviews.at(-1) || null;
  const reviewEntry = latestReview?.plans?.find(p => p.symbol === state.symbol) || null;

  const planBody = el("div", { class: "stack" });
  function paintPlan(plan) {
    if (!plan) {
      planBody.replaceChildren(el("div", { class: "empty-state" }, "暂无已登记计划"));
      return;
    }
    const gates = [
      ["可执行性", gateStatus(plan.reasons?.P0)],
      ["账户风控", gateStatus(plan.reasons?.P1)],
      ["投资逻辑", gateStatus(plan.reasons?.P2)],
      ["策略准入", gateStatus(plan.reasons?.P3)],
      ["策略信号", gateStatus(plan.reasons?.P4)],
    ];
    planBody.replaceChildren(
      el("div", { class: "hero-row" },
        el("span", { class: `${actionPillClass(plan.action)} pill-lg` }, label(plan.action)),
        el("span", { class: "muted num" }, plan.session || ""),
      ),
      el("div", { class: "kpi-grid" },
        kpi("计划股数", String(plan.quantity ?? 0)),
        kpi("当前持仓", String(plan.current_quantity ?? 0)),
        kpi("可卖股数", plan.sellable_quantity ?? "—"),
        kpi("资金预留", money(plan.cash_reserved)),
      ),
      el("div", { class: "gate-row" },
        gates.map(([name, g]) => el("div", { class: `gate-cell ${g.cls}` },
          el("span", {}, name), el("strong", {}, g.text),
        )),
      ),
    );
  }
  paintPlan(activePlan);

  const strategyOpts = strategies.filter(s => s.simulation_eligible).map(s => s.strategy.version);
  const modeSel = el("select", {},
    el("option", { value: "live" }, "真实前向"),
    el("option", { value: "rehearsal" }, "演练"),
  );
  if (state.bookId !== "real") modeSel.value = "rehearsal";

  const planCard = el("section", { class: "card stack" },
    el("div", { class: "card-head" },
      el("span", { class: "card-title" }, "明日交易计划"),
      el("div", { class: "actions" },
        el("button", {
          type: "button", class: "btn btn-sm",
          onclick: async () => {
            try {
              const res = await api("/api/plans/preview", {
                method: "POST", body: { book_id: state.bookId, symbols: [state.symbol] },
              });
              if (res.plans?.length) paintPlan(res.plans[0]);
              showToast("已刷新裁决预览");
            } catch (err) { showToast(err.message, true); }
          },
        }, "预览裁决"),
        modeSel,
        el("button", {
          type: "button", class: "btn btn-primary btn-sm",
          onclick: async () => {
            try {
              await api("/api/reviews", {
                method: "POST",
                body: {
                  book_id: state.bookId, symbols: [state.symbol],
                  mode: modeSel.value,
                  strategy_versions: strategyOpts.length ? [strategyOpts[0]] : [],
                },
              });
              showToast("已冻结并登记盘后计划");
              render();
            } catch (err) { showToast(err.message, true); }
          },
        }, "冻结登记"),
      ),
    ),
    planBody,
  );

  // Right Card: Execution & Review + Followup Launch
  const outcomeStatus = el("select", {},
    el("option", { value: "confirmed" }, "已确认"),
    el("option", { value: "not_executed" }, "未执行"),
    el("option", { value: "rejected" }, "已拒绝"),
  );
  const outcomeReason = el("input", { placeholder: "说明（未执行/拒绝必填）" });

  const reviewCard = el("section", { class: "card stack" },
    el("div", { class: "card-head" },
      el("span", { class: "card-title" }, "执行与复盘"),
      latestReview ? el("button", {
        type: "button", class: "btn btn-sm",
        onclick: async () => {
          try {
            await api(`/api/reviews/${encodeURIComponent(latestReview.registration_id)}/settle`, { method: "POST", body: {} });
            showToast("影子结算已更新");
            render();
          } catch (err) { showToast(err.message, true); }
        },
      }, "结算影子") : null,
    ),
    reviewEntry ? el("div", { class: "kpi-grid-3" },
      kpi("正式计划", label(reviewEntry.real_plan.action), `${reviewEntry.real_plan.quantity} 股`),
      kpi("影子模拟", reviewEntry.shadow ? label(reviewEntry.shadow.status) : "待结算", label(reviewEntry.shadow_plan.action)),
      kpi("实际执行", label(reviewEntry.actual.status)),
    ) : el("div", { class: "empty-state" }, "暂无复盘记录"),
    latestReview && reviewEntry ? el("form", {
      class: "form-grid",
      onsubmit: async e => {
        e.preventDefault();
        try {
          await api(`/api/reviews/${encodeURIComponent(latestReview.registration_id)}/outcomes`, {
            method: "POST",
            body: { symbol: state.symbol, status: outcomeStatus.value, reason: outcomeReason.value.trim() || null },
          });
          showToast("已记录实际结果");
          render();
        } catch (err) { showToast(err.message, true); }
      },
    },
      el("div", { class: "field-row" },
        el("div", { class: "field" }, el("label", {}, "执行状态"), outcomeStatus),
        el("div", { class: "field" }, el("label", {}, "执行备注"), outcomeReason),
      ),
      el("div", { class: "actions" }, el("button", { type: "submit", class: "btn btn-sm" }, "保存结果")),
    ) : null,
    followups.length ? el("div", { class: "strip" },
      el("div", { class: "strip-label" }, "待跟进线索"),
      el("div", { class: "stack" }, followups.map(f => el("div", { class: "task-item" },
        el("div", { class: "task-top" },
          el("span", { class: "task-q" }, f.hypothesis || f.trigger_id),
          el("button", {
            type: "button", class: "btn btn-primary btn-xs",
            onclick: async () => {
              try {
                const res = await api("/api/research/tasks/from-followup", {
                  method: "POST", body: { followup_id: f.followup_id },
                });
                state.selectedTaskId = res.task_id;
                showToast("已发起跟进研究");
                go("lab", state.symbol, "research");
              } catch (err) { showToast(err.message, true); }
            },
          }, "发起跟进研究"),
        ),
      ))),
    ) : null,
  );

  app.replaceChildren(
    el("div", { class: "view-bar" }, symbolBar(watchlist, "decision")),
    el("div", { class: "grid-split" }, planCard, reviewCard),
  );
}

/* ---------- View 3: Research & Strategy Lab ---------- */
function stripFrontmatter(md) {
  if (!md) return "";
  const lines = md.replace(/^\ufeff/, "").split("\n");
  if (lines[0] === "---") {
    const end = lines.indexOf("---", 1);
    if (end > 0) return lines.slice(end + 1).join("\n").trim();
  }
  return md.trim();
}

async function renderLab() {
  clearTimeout(state.pollTimer);
  const [watchlist, dossier, tasks, devTasks, strategies, experiments] = await Promise.all([
    api("/api/watchlist"),
    api(`/api/research/${encodeURIComponent(state.symbol)}/dossiers`).catch(() => null),
    api("/api/research/tasks", { params: { symbol: state.symbol, kind: "dossier" } }),
    api("/api/research/tasks", { params: { kind: "development_experiment" } }),
    api(`/api/strategies/${encodeURIComponent(state.symbol)}`),
    api("/api/experiments", { params: { symbol: state.symbol } }),
  ]);

  const seg = el("div", { class: "seg-switch" },
    el("button", {
      type: "button", class: state.labTab === "research" ? "active" : "",
      onclick: () => { state.labTab = "research"; renderLab(); },
    }, "个股逻辑研究"),
    el("button", {
      type: "button", class: state.labTab === "experiment" ? "active" : "",
      onclick: () => { state.labTab = "experiment"; renderLab(); },
    }, "策略对照实验"),
  );

  const hasActive = [...tasks, ...devTasks].some(t => ["pending", "running", "cancelling"].includes(t.latest_attempt?.status));
  if (hasActive && state.view === "lab") {
    state.pollTimer = setTimeout(() => { if (state.view === "lab") renderLab(); }, 1500);
  }

  let content;
  if (state.labTab === "research") {
    content = await buildResearchTab(dossier, tasks);
  } else {
    content = await buildExperimentTab(devTasks, strategies, experiments);
  }

  app.replaceChildren(
    el("div", { class: "view-bar" }, symbolBar(watchlist, "lab"), seg),
    content,
  );
}

async function buildResearchTab(dossier, tasks) {
  if (tasks.length && !tasks.some(t => t.task_id === state.selectedTaskId)) {
    state.selectedTaskId = tasks[0].task_id;
  }
  const selected = tasks.find(t => t.task_id === state.selectedTaskId) || null;
  const latestAttempt = selected?.latest_attempt || null;
  let draftData = null;
  if (latestAttempt?.draft_version) {
    draftData = await api(`/api/research/${encodeURIComponent(state.symbol)}/drafts`, {
      params: { version: latestAttempt.draft_version },
    }).catch(() => null);
  }

  const thesisCard = el("section", { class: "card stack" },
    el("div", { class: "card-head" },
      el("span", { class: "card-title" }, "当前生效逻辑"),
      dossier ? el("span", { class: "muted num" }, `有效至 ${String(dossier.valid_until || "").slice(0, 10)}`) : null,
    ),
    dossier ? el("div", { class: "stack" },
      el("div", { class: "focus-pills" },
        el("span", { class: gatePillClass(dossier.fundamental_gate) }, `基本面 · ${label(dossier.fundamental_gate)}`),
        el("span", { class: thesisPillClass(dossier.thesis_status) }, `逻辑 · ${label(dossier.thesis_status)}`),
      ),
      dossier.hypothesis ? el("p", {}, dossier.hypothesis) : null,
    ) : el("div", { class: "empty-state" }, "尚未发布研究档案"),
  );

  const taskListCard = el("section", { class: "card stack" },
    el("div", { class: "card-head" }, el("span", { class: "card-title" }, "研究任务")),
    tasks.length ? el("div", { class: "stack" }, tasks.map(t => {
      const att = t.latest_attempt || {};
      const running = ["pending", "running", "cancelling"].includes(att.status);
      return el("div", {
        class: `task-item ${selected && t.task_id === selected.task_id ? "active" : ""}`,
        onclick: () => { state.selectedTaskId = t.task_id; renderLab(); },
      },
        el("div", { class: "task-top" },
          el("span", { class: "task-q" }, t.question),
          el("span", { class: running ? "pill pill-primary" : att.status === "draft_ready" ? "pill pill-down" : att.status === "blocked" ? "pill pill-warn" : "pill" },
            running ? el("span", { class: "dot dot-pulse" }) : null,
            label(att.status),
          ),
        ),
        el("div", { class: "actions" },
          running ? el("button", {
            type: "button", class: "btn btn-danger btn-xs",
            onclick: async e => {
              e.stopPropagation();
              await api(`/api/research/attempts/${encodeURIComponent(att.attempt_id)}/cancel`, { method: "POST" });
              showToast("已请求取消");
              renderLab();
            },
          }, "取消") : null,
          !running ? el("button", {
            type: "button", class: "btn btn-xs",
            onclick: async e => {
              e.stopPropagation();
              await api(`/api/research/tasks/${encodeURIComponent(t.task_id)}/retry`, { method: "POST", body: {} });
              showToast("已发起重试");
              renderLab();
            },
          }, "重试") : null,
        ),
      );
    })) : el("div", { class: "empty-state" }, "暂无研究任务"),
  );

  // Right Column: New Task Form + Selected Draft Review & Publish (ZERO evidence/source lists!)
  const qInput = el("input", { placeholder: "研究问题", required: true });
  const basisSel = el("select", {},
    el("option", { value: "stock-close" }, "收盘量价"),
    el("option", { value: "industry-comparison" }, "行业相对强弱"),
    el("option", { value: "announcement" }, "公开材料"),
  );
  const newTaskCard = el("section", { class: "card stack" },
    el("div", { class: "card-head" }, el("span", { class: "card-title" }, "发起研究")),
    el("form", {
      class: "form-grid",
      onsubmit: async e => {
        e.preventDefault();
        try {
          const res = await api("/api/research/tasks", {
            method: "POST",
            body: { symbol: state.symbol, question: qInput.value.trim(), basis: basisSel.value },
          });
          state.selectedTaskId = res.task_id;
          qInput.value = "";
          showToast("研究任务已启动");
          renderLab();
        } catch (err) { showToast(err.message, true); }
      },
    },
      el("div", { class: "field" }, el("label", {}, "问题"), qInput),
      el("div", { class: "field" }, el("label", {}, "研究维度"), basisSel),
      el("div", { class: "actions" }, el("button", { type: "submit", class: "btn btn-primary btn-sm" }, "发起研究")),
    ),
  );

  const reviewerInput = el("input", { placeholder: "确认人", required: true });
  const draftCard = draftData ? el("section", { class: "card stack" },
    el("div", { class: "card-head" },
      el("span", { class: "card-title" }, "草稿审阅与发布"),
      el("div", { class: "focus-pills" },
        el("span", { class: gatePillClass(draftData.fundamental_gate) }, label(draftData.fundamental_gate || "unknown")),
        el("span", { class: thesisPillClass(draftData.thesis_status) }, label(draftData.thesis_status || "unknown")),
      ),
    ),
    el("div", { class: "draft-body" }, stripFrontmatter(draftData.markdown)),
    el("form", {
      class: "inline-add",
      onsubmit: async e => {
        e.preventDefault();
        try {
          await api(`/api/research/${encodeURIComponent(state.symbol)}/dossiers`, {
            method: "POST",
            body: { version: draftData.version, reviewer: reviewerInput.value.trim() },
          });
          showToast("已发布新版本研究档案");
          renderLab();
        } catch (err) { showToast(err.message, true); }
      },
    }, reviewerInput, el("button", { type: "submit", class: "btn btn-primary btn-sm" }, "确认发布")),
  ) : null;

  return el("div", { class: "grid-split" },
    el("div", { class: "stack" }, thesisCard, taskListCard),
    el("div", { class: "stack" }, newTaskCard, draftCard),
  );
}

async function buildExperimentTab(devTasks, strategies, experiments) {
  if (devTasks.length && !devTasks.some(t => t.task_id === state.selectedDevTaskId)) {
    state.selectedDevTaskId = devTasks[0].task_id;
  }
  const selectedDev = devTasks.find(t => t.task_id === state.selectedDevTaskId) || null;
  let devDetail = null;
  if (selectedDev) {
    devDetail = await api(`/api/development/tasks/${encodeURIComponent(selectedDev.task_id)}`).catch(() => null);
  }
  let formalReport = null;
  if (experiments.length) {
    formalReport = await api(`/api/experiments/${encodeURIComponent(experiments[0].run_id)}`).catch(() => null);
  }

  // Top Card: Strategy Registry & Formal Backtest Comparison
  const registryCard = el("section", { class: "card stack" },
    el("div", { class: "card-head" },
      el("span", { class: "card-title" }, "策略准入与双基准回测"),
      strategies.length
        ? el("span", { class: strategies[0].production_eligible ? "pill pill-down" : "pill pill-warn" },
            strategies[0].production_eligible ? "生产可用" : label(strategies[0].status))
        : el("span", { class: "pill" }, "暂无策略"),
    ),
    formalReport?.windows?.acceptance ? el("div", { class: "table-wrap" }, el("table", { class: "clean" },
      el("thead", {}, el("tr", {}, el("th", {}, "策略路径"), el("th", {}, "净收益"), el("th", {}, "最大回撤"), el("th", {}, "成交笔数"))),
      el("tbody", {}, [
        ["trend", "冻结趋势"], ["buy_and_hold", "买入持有"], ["no_active_trading", "不主动交易"],
      ].map(([key, title]) => {
        const m = formalReport.windows.acceptance.paths[key];
        return el("tr", {},
          el("td", {}, el("strong", {}, title)),
          el("td", { class: deltaClass(m.total_return) }, pct(m.total_return, true)),
          el("td", {}, pct(m.max_drawdown)),
          el("td", {}, String(m.fills)),
        );
      })),
    )) : el("div", { class: "empty-state" }, "暂无正式回测"),
  );

  // Main Card: E0 / E1 Development Comparison & Archive
  const receipt = devDetail?.development_receipt;
  const devAttempt = devDetail?.attempts?.at(-1);
  const archives = selectedDev?.archives || [];

  const conclusionSel = el("select", {},
    el("option", { value: "actions_identical" }, "动作一致"),
    el("option", { value: "single_segment" }, "集中于单段"),
    el("option", { value: "evidence_insufficient" }, "样本不足"),
    el("option", { value: "multiple_segments" }, "多段存在差异"),
  );
  const decisionSel = el("select", {},
    el("option", { value: "stop" }, "停止扩展"),
    el("option", { value: "continue" }, "继续研究"),
  );
  const revInput = el("input", { placeholder: "审阅人", required: true });
  const reasonInput = el("input", { placeholder: "停止或继续理由", required: true });

  const devCard = el("section", { class: "card stack" },
    el("div", { class: "card-head" },
      el("span", { class: "card-title" }, "开发对照实验（E0 / E1）"),
      el("button", {
        type: "button", class: "btn btn-primary btn-sm",
        onclick: async () => {
          try {
            const res = await api("/api/development/tasks", { method: "POST", body: {} });
            state.selectedDevTaskId = res.task_id;
            showToast("已发起 E0/E1 对照实验");
            renderLab();
          } catch (err) { showToast(err.message, true); }
        },
      }, "运行 E0/E1 对照"),
    ),
    devTasks.length > 1 ? el("div", { class: "symbol-chips" }, devTasks.slice(0, 6).map((t, idx) =>
      el("button", {
        type: "button",
        class: `chip ${selectedDev && t.task_id === selectedDev.task_id ? "active" : ""}`,
        onclick: () => { state.selectedDevTaskId = t.task_id; renderLab(); },
      }, `对照 #${devTasks.length - idx} · ${label(t.latest_attempt?.status)}`),
    )) : null,
    receipt?.metrics ? el("div", { class: "stack" },
      el("div", { class: "kpi-grid" },
        kpi("E0 净收益", pct(receipt.metrics.e0.total_return, true), `回撤 ${pct(receipt.metrics.e0.max_drawdown)}`, deltaClass(receipt.metrics.e0.total_return)),
        kpi("E1 净收益", pct(receipt.metrics.e1.total_return, true), `回撤 ${pct(receipt.metrics.e1.max_drawdown)}`, deltaClass(receipt.metrics.e1.total_return)),
        kpi("拦截买入", String(receipt.opportunities?.market_filter?.blocked_buy_count ?? 0), `候选 ${receipt.opportunities?.market_filter?.eligible_e1_buy_candidates ?? 0}`),
        kpi("成交对比", `${receipt.metrics.e0.fills} / ${receipt.metrics.e1.fills}`, "E0 / E1"),
      ),
      receipt.attribution?.segments?.length ? el("div", { class: "table-wrap" }, el("table", { class: "clean" },
        el("thead", {}, el("tr", {}, el("th", {}, "持仓区段"), el("th", {}, "净值差异"), el("th", {}, "费用差"))),
        el("tbody", {}, receipt.attribution.segments.slice(0, 8).map(seg => el("tr", {},
          el("td", {}, `${seg.start} — ${seg.end}`),
          el("td", { class: deltaClass(seg.net_difference) }, money(seg.net_difference)),
          el("td", {}, money(seg.cost_difference)),
        ))),
      )) : null,
      archives.length ? el("div", { class: "focus-pills" },
        el("span", { class: "pill pill-primary" }, `已归档 · ${label(archives.at(-1).conclusion)} · ${label(archives.at(-1).decision)}`),
        el("span", { class: "muted" }, archives.at(-1).reason),
      ) : null,
      devAttempt?.status === "report_ready" ? el("form", {
        class: "form-grid strip",
        onsubmit: async e => {
          e.preventDefault();
          try {
            const segRefs = conclusionSel.value === "multiple_segments"
              ? (receipt.attribution?.segments || []).filter(s => s.net_difference && Number(s.net_difference) !== 0).slice(0, 2).map(s => s.ref)
              : [];
            await api(`/api/development/tasks/${encodeURIComponent(selectedDev.task_id)}/archive`, {
              method: "POST",
              body: {
                attempt_id: devAttempt.attempt_id,
                report_version: devAttempt.report_version,
                conclusion: conclusionSel.value,
                decision: decisionSel.value,
                reviewer: revInput.value.trim(),
                reason: reasonInput.value.trim(),
                segment_refs: segRefs,
                sizing_rule: decisionSel.value === "continue" ? "固定 50% 仓位上限" : null,
                measurement: decisionSel.value === "continue" ? "共同起点逐日净值与分段贡献" : null,
              },
            });
            showToast("实验结论已归档");
            renderLab();
          } catch (err) { showToast(err.message, true); }
        },
      },
        el("div", { class: "field-row" },
          el("div", { class: "field" }, el("label", {}, "结论类别"), conclusionSel),
          el("div", { class: "field" }, el("label", {}, "下一步"), decisionSel),
        ),
        el("div", { class: "field-row" },
          el("div", { class: "field" }, el("label", {}, "审阅人"), revInput),
          el("div", { class: "field" }, el("label", {}, "理由"), reasonInput),
        ),
        el("div", { class: "actions" }, el("button", { type: "submit", class: "btn btn-primary btn-sm" }, "归档实验结论")),
      ) : null,
    ) : el("div", { class: "empty-state" }, "暂无开发对照记录"),
  );

  return el("div", { class: "stack" }, registryCard, devCard);
}

/* ---------- Router ---------- */
async function render() {
  parseHash();
  updateNav();
  try {
    if (state.view === "overview") await renderOverview();
    else if (state.view === "decision") await renderDecision();
    else await renderLab();
  } catch (err) {
    app.replaceChildren(el("div", { class: "card empty-state" }, err.message));
  }
}

window.addEventListener("hashchange", render);
render();

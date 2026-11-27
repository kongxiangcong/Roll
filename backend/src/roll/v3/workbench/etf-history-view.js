import { el, marketTable } from "./market-view.js";

const WINDOW_NAMES = {
  "1": "当日", "5": "5 个交易日", "21": "21 个交易日", "120": "120 个交易日",
  "242": "242 个交易日", ytd: "年初以来",
};
const FLOW_STATUS = {
  complete: "完整", partial: "部分累计", missing: "暂无可算金额", not_applicable: "无适用基金日",
};
const AXIS_NUMBER = new Intl.NumberFormat("zh-CN", { maximumSignificantDigits: 4 });
const valueText = value => value ?? "—";
const amountColor = value => value?.startsWith("-") ? "down" : value?.startsWith("+") ? "up" : "";

function coverage(day, asset = false) {
  return `${asset ? day.assets_valid_count : day.valid_count}/${day.expected_count}`;
}

function dateButton(date, selected, onSelect) {
  return el("button", {
    type: "button", class: "market-row-label market-date-cell", "aria-current": selected ? "date" : null,
    onclick: () => onSelect(date),
  }, date);
}

function renderWindows(windows, active, selectWindow) {
  return el("div", { class: "etf-history-windows", "aria-label": "净申赎累计窗口" },
    windows.map(window => {
      const range = window.start_date ? `${window.start_date} 至 ${window.end_date}` : "暂无可用期";
      const short = window.insufficient_history
        ? ` · 不足期 ${window.session_count}/${window.requested_session_count} 日` : "";
      const status = window.start_date ? FLOW_STATUS[window.flow_status] : "暂无数据";
      return el("button", {
        type: "button", class: "etf-history-window", "aria-pressed": active === window.key ? "true" : "false",
        onclick: () => selectWindow(window.key),
      },
      el("strong", {}, WINDOW_NAMES[window.key]),
      el("span", { class: `num etf-history-window-value ${amountColor(window.flow_display_yi)}` },
        valueText(window.flow_display_yi)),
      el("span", { class: "card-sub" }, `${coverage(window)} 基金日 · ${status}`),
      el("span", { class: "card-sub" }, `${range}${short}`));
    }),
  );
}

function chartScale(values, includeZero) {
  const present = values.filter(value => value != null).map(Number).filter(Number.isFinite);
  if (!present.length) return null;
  let low = Math.min(...present);
  let high = Math.max(...present);
  if (includeZero) {
    low = Math.min(0, low);
    high = Math.max(0, high);
  }
  if (low === high) {
    const padding = Math.abs(low) * 0.02 || 1;
    low -= padding;
    high += padding;
  }
  return { low, high };
}

function drawCandles(days, { ink, x, y, width, colors }) {
  days.forEach((day, index) => {
    const bar = day.index_ohlc;
    if (!bar) return;
    const center = x(index);
    const price = y(bar.open);
    const close = y(bar.close);
    ink.fillStyle = Number(bar.close) >= Number(bar.open) ? colors.up : colors.down;
    ink.fillRect(center - 1, y(bar.high), 2, Math.max(2, y(bar.low) - y(bar.high)));
    ink.fillRect(center - width / 2, Math.min(price, close), width, Math.max(2, Math.abs(price - close)));
  });
}

function drawFlows(days, { ink, x, y, width, colors }) {
  const zero = y(0);
  ink.globalAlpha = 0.5;
  ink.fillStyle = colors.muted;
  ink.fillRect(0, zero, ink.canvas.width, 1);
  ink.globalAlpha = 1;
  days.forEach((day, index) => {
    if (day.flow_yi == null) return;
    const amount = Number(day.flow_yi);
    const target = y(amount);
    ink.globalAlpha = day.flow_status === "partial" ? 0.55 : 1;
    ink.fillStyle = amount > 0 ? colors.up : amount < 0 ? colors.down : colors.muted;
    const height = Math.max(2, Math.abs(target - zero));
    ink.fillRect(x(index) - width / 2, amount >= 0 ? zero - height : zero, width, height);
    ink.globalAlpha = 1;
  });
}

function drawAssets(days, { ink, x, y, colors }) {
  let previous = null;
  ink.strokeStyle = ink.fillStyle = colors.primary;
  ink.lineWidth = 2;
  days.forEach((day, index) => {
    const value = day.complete_assets_yi;
    if (value == null) {
      previous = null;
      return;
    }
    const point = [x(index), y(value)];
    ink.beginPath();
    if (previous) {
      ink.moveTo(...previous);
      ink.lineTo(...point);
      ink.stroke();
    }
    ink.beginPath();
    ink.arc(...point, 2.75, 0, Math.PI * 2);
    ink.fill();
    previous = point;
  });
}

function plot({ title, days, scale, draw, preview, select, tall = false, empty }) {
  const width = 1024;
  const height = tall ? 168 : 110;
  const canvas = el("canvas", { width, height, "aria-hidden": "true" });
  const x = index => (index + 0.5) * width / days.length;
  const y = value => scale ? 8 + (scale.high - Number(value)) * (height - 16) / (scale.high - scale.low) : height / 2;
  const findDate = event => {
    const box = canvas.getBoundingClientRect();
    const index = Math.floor((event.clientX - box.left) * days.length / box.width);
    return Math.min(days.length - 1, Math.max(0, index));
  };
  canvas.addEventListener("pointermove", event => {
    if (event.pointerType === "mouse") preview(findDate(event));
  });
  canvas.addEventListener("click", event => select(days[findDate(event)].trade_date));
  const labels = scale ? [scale.high, (scale.high + scale.low) / 2, scale.low].map(value =>
    el("span", {}, AXIS_NUMBER.format(value))) : [el("span", {}, "—")];
  const node = el("div", { class: "etf-history-plot" },
    el("h3", {}, title),
    el("div", { class: "etf-history-plot-body" },
      el("div", { class: "etf-history-plot-axis", "aria-hidden": "true" }, labels),
      el("div", { class: "etf-history-plot-canvas" }, canvas,
        !scale ? el("span", { class: "etf-history-plot-empty" }, empty) : null),
    ),
  );
  const ink = canvas.getContext("2d");

  function paint(active) {
    if (!ink) return;
    const styles = getComputedStyle(document.documentElement);
    const colors = {
      up: styles.getPropertyValue("--up"), down: styles.getPropertyValue("--down"),
      primary: styles.getPropertyValue("--primary"), muted: styles.getPropertyValue("--ink-muted") || "#64748b",
      grid: styles.getPropertyValue("--border"), selection: styles.getPropertyValue("--primary-soft"),
    };
    ink.clearRect(0, 0, width, height);
    const band = width / days.length;
    if (days.length > 1) {
      ink.fillStyle = colors.selection;
      ink.fillRect(x(active) - band / 2, 0, band, height);
    }
    ink.fillStyle = colors.grid;
    for (const level of [8, height / 2, height - 8]) ink.fillRect(0, level, width, 1);
    if (scale) draw(days, { ink, x, y, width: Math.max(2, Math.min(18, band * 0.62)), colors });
    ink.fillStyle = colors.primary;
    ink.fillRect(x(active), 0, 1, height);
  }

  return { node, paint };
}

function assetLabel(day) {
  if (day.assets_yi == null) return "暂无规模";
  return day.complete_assets_yi == null ? "部分规模" : "完整规模";
}

function dateFacts(day, indexName) {
  const bar = day.index_ohlc;
  return [
    el("span", {}, `估算净申赎 ${valueText(day.flow_display_yi)} 亿元 · ${coverage(day)} 只`),
    el("span", {}, `${assetLabel(day)} ${valueText(day.assets_yi)} 亿元 · ${coverage(day, true)} 只`),
    el("span", {}, bar
      ? `${indexName} 开 ${bar.open} · 高 ${bar.high} · 低 ${bar.low} · 收 ${bar.close}`
      : "指数行情缺口"),
  ];
}

function dailyTable(days, selected, select, hasIndex, themeState) {
  return el("details", {
    class: "etf-history-day-table", open: themeState.historyDaysOpen,
    ontoggle: event => { themeState.historyDaysOpen = event.currentTarget.open; },
  },
  el("summary", {}, "逐日明细"),
  marketTable({
    label: "ETF 历史逐日明细",
    columns: [
      { label: "交易日" }, { label: "估算净申赎（亿元）", numeric: true }, { label: "可算 / 应有", numeric: true },
      { label: "资产规模（亿元）", numeric: true }, { label: "规模覆盖", numeric: true },
      ...(hasIndex ? [{ label: "指数开 / 高 / 低 / 收（点）", numeric: true }] : []),
    ],
    rows: [...days].reverse().map(day => {
      const bar = day.index_ohlc;
      return el("tr", { class: day.trade_date === selected ? "market-selected" : null },
        el("td", {}, dateButton(day.trade_date, day.trade_date === selected, select)),
        el("td", { class: `num ${amountColor(day.flow_display_yi)}` }, valueText(day.flow_display_yi)),
        el("td", { class: "num" }, coverage(day)),
        el("td", { class: "num" }, valueText(day.assets_yi)),
        el("td", { class: "num" }, `${coverage(day, true)} · ${assetLabel(day)}`),
        hasIndex ? el("td", { class: "num" }, bar
          ? `${bar.open} / ${bar.high} / ${bar.low} / ${bar.close}` : "—") : null,
      );
    }),
  }));
}

function renderTimeline(report, days, themeState, select) {
  let active = days.findIndex(day => day.trade_date === report.trade_date);
  const stats = el("div", { class: "etf-history-date-facts card-sub" });
  const date = el("select", {
    "aria-label": "图表交易日", onchange: event => preview(Number(event.currentTarget.value)),
  }, days.map((day, index) => el("option", { value: index }, day.trade_date)));
  const indexName = report.index_name || report.index_code || "指数";
  const selectedDate = el("button", {
    class: "btn btn-sm", type: "button", onclick: () => select(days[active].trade_date),
  }, "查看当日基金");

  const scale = chartScale(days.flatMap(day => [day.index_ohlc?.low, day.index_ohlc?.high]), false);
  const chartOptions = { days, preview, select };
  const charts = [
    plot({ ...chartOptions, title: `${indexName}${report.index_code ? "" : " 基准"} K 线（点）`, scale,
      draw: drawCandles, tall: true, empty: report.index_symbol ? "区间暂无指数行情" : "暂无可核验的本地指数行情" }),
    plot({ ...chartOptions, title: "估算净申赎（亿元）", scale: chartScale(days.map(day => day.flow_yi), true),
      draw: drawFlows, empty: "区间暂无可算金额" }),
    plot({ ...chartOptions, title: "资产规模（亿元）", scale: chartScale(days.map(day => day.complete_assets_yi), false),
      draw: drawAssets, empty: "区间暂无完整规模" }),
  ];

  function preview(index, force = false) {
    if (active === index && !force) return;
    active = index;
    date.value = String(index);
    stats.replaceChildren(...dateFacts(days[index], indexName));
    for (const chart of charts) chart.paint(index);
  }

  preview(active, true);
  return el("div", { class: "stack etf-history-timeline" },
    el("div", { class: "etf-history-date-controls" }, date, selectedDate, stats),
    el("div", { class: "etf-history-plots" },
      charts.map(chart => chart.node),
      el("div", { class: "etf-history-plot-range card-sub" },
        el("span", {}, days[0].trade_date), el("span", {}, days.at(-1).trade_date)),
    ),
    dailyTable(days, report.trade_date, select, Boolean(report.index_symbol), themeState),
  );
}

export function createEtfHistory(report, { api, themeState, selectTradeDate }) {
  const node = el("section", { class: "card stack etf-history", "aria-label": "ETF 历史报表" });
  let request = 0;
  let selectedScope;

  function showStatus(message) {
    node.replaceChildren(el("h2", { class: "card-title" }, "历史报表"),
      el("p", { class: "card-sub", role: "status" }, message));
  }

  function show(history, focusWindow) {
    const key = themeState.historyWindow || "21";
    const window = history.windows.find(item => item.key === key);
    const days = history.days.filter(day => day.trade_date >= window.window_start_date);
    const scope = history.symbol ? `${history.fund_name}（${history.symbol}）` : history.group_name || "全部指数";
    const listing = history.listing_date ? (history.trade_date < history.listing_date
      ? ` · 尚未上市（${history.listing_date} 起）` : ` · ${history.listing_date} 上市`) : "";
    node.replaceChildren(
      el("div", { class: "stack etf-history-heading" },
        el("h2", { class: "card-title" }, "历史报表"),
        el("p", { class: "card-sub" },
          `${scope} · ${history.basket.version} · ${history.basket.history_label || "按固定名单回看"}${listing}`),
        el("p", { class: "card-sub" }, "累计估算净申赎（亿元） · 覆盖按可算 / 应有基金日"),
      ),
      renderWindows(history.windows, key, selected => {
        themeState.historyWindow = selected;
        show(history, true);
      }),
      renderTimeline(history, days, themeState, day => {
        themeState.historyShowDaily = true;
        selectTradeDate(day);
      }),
    );
    if (focusWindow) node.querySelector('.etf-history-window[aria-pressed="true"]')?.focus({ preventScroll: true });
  }

  async function setScope(indexCode, symbol) {
    const scope = `${indexCode || ""}:${symbol || ""}`;
    if (scope === selectedScope) return;
    selectedScope = scope;
    const ticket = ++request;
    showStatus("正在读取本地历史…");
    try {
      const history = await api("/api/market/etf/history", { params: {
        trade_date: report.trade_date, basket_version: report.basket.version,
        index_code: indexCode, symbol, as_of: report.as_of, max_seq: report.snapshot.max_seq,
      } });
      if (ticket === request) show(history, false);
    } catch (error) {
      if (ticket === request) showStatus(error.message);
    }
  }

  return { node, setScope };
}

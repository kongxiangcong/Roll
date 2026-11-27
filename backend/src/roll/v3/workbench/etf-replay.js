import { el } from "./market-view.js";

const LIVE_MODE = "LIVE_RUN";
const RECONSTRUCTED_MODE = "RECONSTRUCTED_RESEARCH";
const shanghaiTime = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Asia/Shanghai", dateStyle: "short", timeStyle: "medium", hour12: false,
});
const displayTime = value => shanghaiTime.format(new Date(value));

function reportPath(id) {
  return `/api/market/etf/reports/${encodeURIComponent(id)}`;
}

export function etfReplayQuery(themeState) {
  return { as_of: themeState.asOf, use_mode: themeState.useMode };
}

export function readFrozenEtfReport(api, reportId) {
  return api(reportPath(reportId));
}

export function renderEtfReplay({ api, themeState, refresh, selectTradeDate }, report, error) {
  const shownAsOf = report?.report_id ? report.as_of : themeState.asOf;
  const clock = el("input", {
    id: "etf-cutoff", type: "datetime-local", step: "1",
    value: shownAsOf ? displayTime(shownAsOf).replace(" ", "T") : "",
  });
  const mode = el("select", { id: "etf-use-mode" },
    el("option", { value: LIVE_MODE }, "按 Roll 实际取得回放"),
    el("option", { value: RECONSTRUCTED_MODE }, "按披露时点重建"),
  );
  mode.value = report?.use_mode || themeState.useMode || LIVE_MODE;
  const reportId = el("input", {
    id: "etf-report-reference", type: "text", value: themeState.reportId || "", required: true,
    autocomplete: "off", spellcheck: "false", class: "num",
  });
  const status = el("div", { role: "status", class: "card-sub" }, error);
  const node = el("section", { class: "card stack etf-replay", "aria-label": "ETF 历史时点和报表快照" });

  function applyCutoff(event) {
    event.preventDefault();
    themeState.asOf = clock.value ? `${clock.value}+08:00` : undefined;
    themeState.useMode = mode.value;
    themeState.reportId = undefined;
    refresh();
  }

  function resetCutoff() {
    themeState.asOf = undefined;
    themeState.useMode = undefined;
    themeState.reportId = undefined;
    refresh();
  }

  async function openReport(action, button) {
    button.disabled = true;
    status.textContent = "";
    try {
      const opened = await action();
      if (!node.isConnected) return;
      themeState.reportId = opened.report_id;
      selectTradeDate(opened.trade_date, { preserveEtfReport: true });
    } catch (err) {
      status.textContent = err.message;
    } finally {
      button.disabled = false;
    }
  }

  const apply = el("button", { type: "submit", class: "btn btn-sm" }, "查看时点");
  const load = el("button", { type: "submit", class: "btn btn-sm" }, "打开快照");
  const freeze = el("button", {
    type: "button", class: "btn btn-sm",
    onclick: () => openReport(() => api("/api/market/etf/reports", {
      method: "POST",
      body: {
        trade_date: report.trade_date, basket_version: report.basket.version,
        as_of: report.as_of, use_mode: report.use_mode,
        max_seq: report.snapshot.max_seq, captured_at: report.snapshot.as_of,
      },
    }), freeze),
  }, "冻结当前报表");
  node.append(
    el("form", { class: "etf-replay-form", onsubmit: applyCutoff },
      el("label", { for: "etf-cutoff" }, "ETF 截止时刻（上海时间）"), clock,
      el("label", { for: "etf-use-mode" }, "时间口径"), mode, apply,
      themeState.asOf || themeState.useMode === RECONSTRUCTED_MODE || themeState.reportId
        ? el("button", { type: "button", class: "btn btn-sm", onclick: resetCutoff }, "恢复当前时点") : null,
    ),
    el("form", { class: "etf-replay-form", onsubmit: event => {
      event.preventDefault();
      openReport(() => readFrozenEtfReport(api, reportId.value.trim()), load);
    } }, el("label", { for: "etf-report-reference" }, "报表引用"), reportId, load,
    report && !report.report_id ? freeze : null),
    report ? el("p", { class: "card-sub" }, [
      report.report_id ? "已冻结" : null,
      report.use_mode === RECONSTRUCTED_MODE ? "披露时点重建" : "按实际取得",
      `截止 ${displayTime(report.as_of)}`,
      report.availability_assumption,
    ].filter(Boolean).join(" · ")) : null,
    status,
  );
  return node;
}

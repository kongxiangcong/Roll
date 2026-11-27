import { el, marketMasterDetail, marketTable } from "./market-view.js";
import { createEtfHistory } from "./etf-history-view.js";
import { etfReplayQuery, readFrozenEtfReport, renderEtfReplay } from "./etf-replay.js";

const number = value => value == null ? "—" : value;
const signClass = value => value?.startsWith("+") ? "up" : value?.startsWith("-") ? "down" : "muted";
const timeFormat = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai", dateStyle: "short", timeStyle: "short", hour12: false,
});
const disclosureTimeFormat = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai", dateStyle: "short", timeStyle: "medium", hour12: false,
});
const FIELD_NAMES = {
  shares: "当日份额", previous_shares: "前交易日份额", nav: "当日单位净值", split: "份额折算",
  membership: "适用区间", etf_shares: "交易所份额", etf_nav: "单位净值",
};
const STATUS_NAMES = {
  missing: "缺少数据", not_visible: "截止时刻尚未可见", withdrawn: "已撤回",
  conflict: "来源冲突", date_mismatch: "所属日不符", unverified: "来源或口径待核验",
  invalid_value: "原始数值无效", conversion_basis_unverified: "折算依据待核验",
  not_listed: "尚未上市", outside_membership: "不在篮子生效区间",
};
const SOURCES = { sse: "上交所", szse: "深交所", fuyao: "扶摇", fund_manager: "基金管理人", eastmoney: "东方财富" };

function coverage(summary) {
  return `${summary.valid_count}/${summary.expected_count}`;
}

function flowStatus(summary) {
  if (summary.flow_status === "complete") return summary.flow_cny === "0" ? "完整 · 净额为零" : "完整";
  if (summary.flow_status === "partial") return "部分合计";
  if (summary.flow_status === "not_applicable") return "当日无适用基金";
  return "暂无可算金额";
}

function fundStatus(fund) {
  if (fund.flow_cny != null) return fund.flow_yi === "0" ? "净额为零" : "可算";
  return Object.entries(fund.missing).map(([field, status]) =>
    field === "membership" ? STATUS_NAMES[status] : `${FIELD_NAMES[field]} ${STATUS_NAMES[status] || status}`,
  ).join(" · ");
}

function evidenceLink(ref, label = "原始来源") {
  try {
    const url = new URL(ref);
    if (url.protocol === "https:" || url.protocol === "http:") {
      return el("a", { href: url.href, target: "_blank", rel: "noopener", class: "text-link" }, label);
    }
  } catch {
    // Imported sources may use a local evidence reference.
  }
  return ref ? el("span", { class: "card-sub" }, ref) : null;
}

function renderDisclosureSource(record) {
  return el("div", { class: "stack" },
    el("div", { class: "etf-report-meta muted" },
      el("span", {}, `披露日 ${record.disclosed_date || "未知"}`),
      el("span", {}, `公开时刻 ${record.disclosed_at ? disclosureTimeFormat.format(new Date(record.disclosed_at)) : "未知"}`),
      el("span", {}, `Roll 取得 ${disclosureTimeFormat.format(new Date(record.received_at))}`),
      el("span", {}, `本口径可见 ${disclosureTimeFormat.format(new Date(record.selected_available_at))}`),
    ),
    el("div", { class: "etf-evidence-line" }, evidenceLink(record.source_ref, record.title),
      el("span", { class: "card-sub" }, record.source_locator)),
  );
}

function renderDisclosureEvent(event) {
  const scopes = {
    etf_category: event.scope_label || "ETF 类别", index: `指数 ${event.index_code}`, fund: `基金 ${event.symbol}`,
  };
  return el("div", { class: "stack" },
    el("strong", {}, `${event.holder} · 公告范围 ${scopes[event.scope]}`),
    event.summary ? el("p", {}, event.summary) : null,
    el("div", { class: "etf-report-meta muted" },
      el("span", {}, `交易日 ${event.event_trade_date || "未披露"}`),
      el("span", {}, `金额 ${event.amount_cny == null ? "未披露" : `${event.amount_cny} 元`}`),
      el("span", {}, `份额 ${event.shares == null ? "未披露" : `${event.shares} 份`}`)),
    renderDisclosureSource(event),
  );
}

function renderDisclosureEvents(disclosures) {
  if (!disclosures) return null;
  return el("section", { class: "card stack", "aria-label": "已核实增持公告" },
    el("h2", { class: "card-title" }, "已核实增持公告"),
    disclosures.events.length ? disclosures.events.map(renderDisclosureEvent)
      : el("p", { class: "card-sub" }, "截至所选时点，暂无已核实增持公告。"),
  );
}

function renderFundDisclosures(disclosure) {
  if (!disclosure) return null;
  const { latest_report: latest, basis_report: basis, holders, events } = disclosure;
  const status = { listed: "已列示", not_listed_in_report: "本期未列示", no_comparable_report: "暂无可比披露" };
  return el("div", { class: "stack" },
    el("h4", {}, "报告期机构持仓"),
    latest && latest.report_id !== basis?.report_id ? el("div", { class: "stack" },
      el("p", {}, `${latest.report_period_end} 期末报告无可比实名名单${basis ? `，沿用 ${basis.report_period_end} 期末披露。` : "。"}`),
      renderDisclosureSource(latest),
    ) : null,
    basis ? el("div", { class: "stack" },
      el("p", {}, `持仓披露期末 ${basis.report_period_end}`),
      holders.map(holder => el("div", { class: "etf-evidence-line" },
        el("strong", {}, holder.holder),
        el("span", {}, status[holder.status]),
        holder.status === "listed" ? el("span", { class: "num" },
          `${holder.shares == null ? "份额未披露" : `${holder.shares} 份`} · ${holder.listed_shares_pct == null ? "占比未披露" : `占上市总份额 ${holder.listed_shares_pct}%`}`) : null,
      )),
      renderDisclosureSource(basis),
    ) : el("p", { class: "card-sub" }, "暂无可比实名持仓披露。"),
    el("h4", {}, "该基金的已核实增持公告"),
    events.length ? events.map(renderDisclosureEvent)
      : el("p", { class: "card-sub" }, "截至所选时点，暂无指向该基金的已核实增持公告。"),
  );
}

function metric(label, value, description, valueClass = "") {
  return el("div", { class: "kpi" },
    el("span", { class: "kpi-label" }, label),
    el("span", { class: `kpi-value num ${valueClass}` }, value),
    description ? el("span", { class: "kpi-sub" }, description) : null,
  );
}

function latestField(label, field) {
  return el("span", {}, field
    ? `${label} ${field.trade_date} · ${coverage(field)} 只`
    : `${label}暂无可用日期`);
}

export function renderEtfSummary(report, { selectTradeDate }) {
  const { basket, summary } = report;
  const disclosed = Boolean(basket.eligibility_catalog_version);
  return el("section", { class: "card stack", "aria-label": "篮子日报" },
    el("div", { class: "etf-report-header" },
      el("div", {},
        el("h1", {}, basket.name),
        el("p", { class: "card-sub" }, `版本 ${basket.version} · ${disclosed ? "按所选时点的实名披露" : "按固定名单回看"}`),
      ),
      evidenceLink(basket.basket_sample_ref, "对照名单"),
    ),
    el("div", { class: "etf-report-meta muted" },
      el("span", {}, `观察交易日 ${report.trade_date}`),
      el("span", {}, `数据日 ${report.data_date || "暂无"}`),
      el("span", {}, `查看日期 ${report.view_date}`),
      report.updated_at ? el("span", {}, `本地取得 ${timeFormat.format(new Date(report.updated_at))}`) : null,
    ),
    el("div", { class: "etf-report-metrics" },
      metric("估算净申赎（亿元）", number(summary.flow_display_yi), flowStatus(summary), signClass(summary.flow_display_yi)),
      metric("可算 / 应有", coverage(summary), "只基金"),
      disclosed ? null : metric("最近完整日报", report.latest_complete_date || "—",
        !report.report_id && report.latest_complete_date && report.latest_complete_date !== report.trade_date
          ? el("button", { type: "button", class: "btn btn-sm", onclick: () => selectTradeDate(report.latest_complete_date) }, "查看最近完整日报")
          : null),
    ),
    disclosed ? null : el("div", { class: "etf-report-meta muted" },
      latestField("最近可用份额", report.latest_fields.shares),
      latestField("最近可用净值", report.latest_fields.nav),
    ),
    el("p", { class: "card-sub" }, "全体持有人估算净申赎＝（当日份额－上一交易日可比份额）× 当日单位净值。"),
  );
}

function renderEtfSync(report, { api, refresh }, initial) {
  const node = el("section", { class: "card etf-sync", "aria-label": "ETF 同步" });
  const controls = el("div", { class: "etf-sync-controls" });
  const statusArea = el("div", { class: "stack", role: "status", "aria-live": "polite" });
  const recheck = el("input", { type: "checkbox" });
  const button = el("button", { type: "button", class: "btn btn-primary btn-sm", onclick: start }, "同步所选日 ETF");
  controls.append(button, el("label", {}, recheck, "复查已有输入"));
  node.append(controls, statusArea);

  function paint(status) {
    const busy = status.status === "running";
    button.disabled = busy || !report.summary.expected_count;
    recheck.disabled = busy;
    const labels = {
      running: "后台同步中", done: "同步完成", partial: "部分同步完成", error: "同步失败", idle: "尚未同步 ETF",
    };
    statusArea.replaceChildren(...[
      el("div", { class: "etf-report-meta" },
        el("strong", {}, labels[status.status] || "同步状态不可用"),
        status.trade_date ? el("span", {}, status.trade_date) : null,
        status.last_synced_at ? el("span", { class: "muted" }, timeFormat.format(new Date(status.last_synced_at))) : null,
        status.error ? el("span", { class: "muted" }, status.error) : null,
      ),
      status.fields && Object.keys(status.fields).length ? el("div", { class: "etf-report-meta muted" },
        Object.entries(status.fields).map(([field, value]) => el("span", {},
          `${FIELD_NAMES[field]} ${value.completed}/${value.expected} 项 · 可用 ${value.succeeded} · 缺 ${value.failed}`,
        )),
      ) : null,
      status.failures?.length ? el("details", {},
        el("summary", {}, `同步缺项（${status.failures.length}）`),
        el("ul", { class: "etf-sync-gaps" }, status.failures.map(row => el("li", {},
          `${row.trade_date} · ${row.symbol} · ${SOURCES[row.source] || row.source} ${FIELD_NAMES[row.series]} · ${STATUS_NAMES[row.error] || row.error}`,
        ))),
      ) : null,
    ].filter(Boolean));
  }

  async function start() {
    button.disabled = true;
    try {
      const status = await api("/api/market/etf/sync", {
        method: "POST", body: { trade_date: report.trade_date, basket_version: report.basket.version, refresh: recheck.checked },
      });
      paint(status);
      schedule();
    } catch (error) {
      paint({ status: "error", error: error.message });
    }
  }

  function schedule() {
    setTimeout(async () => {
      if (!node.isConnected) return;
      try {
        const status = await api("/api/market/etf/sync/status");
        if (!node.isConnected) return;
        if (status.status === "running") {
          paint(status);
          schedule();
        } else {
          refresh();
        }
      } catch (error) {
        paint({ status: "unknown", error: error.message });
      }
    }, 800);
  }

  paint(initial);
  if (initial.status === "running") schedule();
  return node;
}

function renderInputEvidence(label, day, field) {
  return el("div", { class: "etf-input-evidence" },
    el("strong", {}, `${label} · ${day}`),
    field.selected ? el("div", { class: "etf-evidence-line" },
      el("span", {}, SOURCES[field.selected.source] || field.selected.source),
      el("span", { class: "num" }, `${field.selected.payload.raw_value ?? field.selected.payload.value} ${field.selected.payload.raw_unit ?? field.selected.unit}`),
      evidenceLink(field.selected.source_ref),
      el("span", { class: "card-sub" }, `实际取得 ${timeFormat.format(new Date(field.selected.received_at))}`),
      field.selected.payload.disclosed_date ? el("span", { class: "card-sub" },
        `披露日 ${field.selected.payload.disclosed_date}`) : null,
    ) : el("span", { class: "muted" }, STATUS_NAMES[field.status] || field.status),
    field.candidates.filter(candidate => candidate.seq !== field.selected?.seq).map(candidate =>
      el("div", { class: "etf-evidence-line muted" },
        el("span", {}, SOURCES[candidate.source] || candidate.source),
        el("span", {}, [
          STATUS_NAMES[candidate.selection_quality],
          candidate.difference === "value_mismatch" ? "数值有差异" : null,
          candidate.payload.source_date || candidate.payload.raw_date,
        ].filter(Boolean).join(" · ")),
        el("span", { class: "num" }, `${candidate.payload.raw_value ?? candidate.payload.value ?? "—"} ${candidate.payload.raw_unit ?? candidate.unit}`),
        evidenceLink(candidate.source_ref),
      ),
    ),
  );
}

export function renderEtfFundDetail(fund, disclosure) {
  if (!fund) return el("div", { class: "empty-state" }, "选择一只基金核对份额、净值和来源。");
  const { inputs } = fund;
  const previousDate = fund.previous_trade_date || "暂无可核实前交易日";
  return el("div", { class: "stack" },
    el("div", { class: "etf-report-header" },
      el("div", {},
        el("h3", {}, fund.name),
        el("p", { class: "card-sub" }, `${fund.symbol} · ${fund.index_name}（${fund.index_code}）`),
      ),
      evidenceLink(fund.fund_tracking_source_ref, "跟踪依据"),
    ),
    el("dl", { class: "etf-fund-values" },
      el("dt", {}, `前交易日份额（份） · ${previousDate}`), el("dd", { class: "num" }, number(fund.previous_shares)),
      el("dt", {}, `当日份额（份） · ${fund.trade_date}`), el("dd", { class: "num" }, number(fund.shares)),
      el("dt", {}, "当日单位净值（元/份）"), el("dd", { class: "num" }, number(fund.nav)),
      fund.split_ratio != null ? [
        el("dt", {}, `折算后前日份额（份） · 折算比例 ${fund.split_ratio}`),
        el("dd", { class: "num" }, number(fund.comparable_previous_shares)),
      ] : null,
      el("dt", {}, "全体持有人估算净申赎贡献（亿元）"), el("dd", { class: `num ${signClass(fund.flow_display_yi)}` }, number(fund.flow_yi)),
    ),
    el("p", { class: "card-sub" }, fundStatus(fund)),
    fund.applicable ? el("details", { class: "etf-evidence" },
      el("summary", {}, "核对输入来源"),
      renderInputEvidence(FIELD_NAMES.previous_shares, previousDate, inputs.previous_shares),
      renderInputEvidence(FIELD_NAMES.shares, fund.trade_date, inputs.shares),
      renderInputEvidence(FIELD_NAMES.nav, fund.trade_date, inputs.nav),
      inputs.split.candidates.length || fund.missing.split
        ? renderInputEvidence(FIELD_NAMES.split, fund.trade_date, inputs.split) : null,
    ) : evidenceLink(fund.listing_source_ref, `上市日期 ${fund.listing_date}`),
    renderFundDisclosures(disclosure),
  );
}

export function renderEtfDailyReport(report, { themeState, onHistoryScope }) {
  const groupCard = el("section", { class: "card stack", "aria-label": "跟踪指数" });
  const fundCard = el("section", { class: "card stack", "aria-label": "基金贡献", tabindex: -1 });
  const detail = el("section", { class: "card stack", "aria-label": "基金详情", tabindex: -1 });

  function draw(preserveFundScroll = false) {
    const previousScroll = preserveFundScroll ? fundCard.querySelector(".market-table")?.scrollTop : 0;
    const selectedGroup = report.groups.find(group => group.index_code === themeState.indexCode);
    const funds = selectedGroup ? report.funds.filter(fund => fund.index_code === selectedGroup.index_code) : report.funds;
    const selectedFund = funds.find(fund => fund.symbol === themeState.selectedSymbol);
    const groupRows = [{ group_name: "全部指数", index_code: null, summary: report.summary }, ...report.groups];
    groupCard.replaceChildren(
      el("h2", { class: "card-title" }, "跟踪指数"),
      marketTable({
        label: "按指数汇总",
        columns: [
          { label: "指数" }, { label: "可算 / 应有", numeric: true }, { label: "净申赎（亿元）", numeric: true },
        ],
        rows: groupRows.map(group => {
          const selected = group.index_code === (selectedGroup?.index_code ?? null);
          return el("tr", { class: selected ? "market-selected" : null },
            el("td", {}, el("button", {
              type: "button", class: "market-row-label", "aria-pressed": selected ? "true" : "false",
              onclick: () => {
                themeState.indexCode = group.index_code;
                draw();
                groupCard.querySelector('button[aria-pressed="true"]')?.focus({ preventScroll: true });
              },
            }, el("strong", {}, group.group_name), group.index_code ? el("span", { class: "watch-code" }, group.index_code) : null)),
            el("td", { class: "num" }, coverage(group.summary)),
            el("td", { class: `num ${signClass(group.summary.flow_display_yi)}` },
              number(group.summary.flow_display_yi), el("div", { class: "card-sub" }, flowStatus(group.summary))),
          );
        }),
      }),
    );

    fundCard.replaceChildren(
      el("div", { class: "etf-report-header" }, el("h2", { class: "card-title" }, "基金贡献"),
        el("span", { class: "card-sub" }, selectedGroup?.group_name || "全部指数")),
      marketTable({
        label: "逐只基金贡献",
        columns: [{ label: "基金" }, { label: "净申赎（亿元）", numeric: true }, { label: "可算状态" }],
        rows: funds.map(fund => {
          const selected = fund.symbol === selectedFund?.symbol;
          return el("tr", { class: selected ? "market-selected" : null },
            el("td", {}, el("button", {
              type: "button", class: "market-row-label", "aria-pressed": selected ? "true" : "false",
              onclick: () => {
                themeState.selectedSymbol = fund.symbol;
                draw(true);
                detail.focus({ preventScroll: true });
                detail.scrollIntoView({ block: "nearest" });
              },
            }, el("strong", {}, fund.name), el("span", { class: "watch-code" }, fund.symbol))),
            el("td", { class: `num ${signClass(fund.flow_display_yi)}` }, number(fund.flow_display_yi)),
            el("td", {}, fundStatus(fund)),
          );
        }),
      }),
    );
    fundCard.querySelector(".market-table").scrollTop = previousScroll || 0;
    const disclosure = report.disclosures?.funds[selectedFund?.symbol];
    detail.replaceChildren(
      el("div", { class: "etf-report-header" }, el("h2", { class: "card-title" }, "基金详情"),
        selectedFund ? el("button", { class: "btn btn-sm", type: "button", onclick: () => {
          const fundButtonIndex = funds.indexOf(selectedFund);
          themeState.selectedSymbol = null;
          draw(true);
          fundCard.querySelectorAll(".market-row-label")[fundButtonIndex]?.focus();
        } }, "返回基金贡献") : null),
      renderEtfFundDetail(selectedFund, disclosure),
    );
    onHistoryScope?.(selectedGroup?.index_code, selectedFund?.symbol);
  }

  draw();
  if (themeState.historyShowDaily) {
    themeState.historyShowDaily = false;
    requestAnimationFrame(() => {
      const target = detail.querySelector(".etf-report-header button") ? detail : fundCard;
      if (!target.isConnected) return;
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: "nearest" });
    });
  }
  return marketMasterDetail(groupCard, el("div", { class: "stack etf-funds" }, fundCard, detail));
}

export function readEtfReport(api, tradeDate, themeState) {
  if (themeState.reportId) return readFrozenEtfReport(api, themeState.reportId, tradeDate);
  return api("/api/market/etf", { params: {
    trade_date: tradeDate, basket_version: themeState.basketVersion, ...etfReplayQuery(themeState),
  } });
}

export function renderEtfBasketReports(report, context, status) {
  const { themeState } = context;
  const display = el("div", { class: "stack" });
  const controls = new Map();
  const comparisons = report.comparison_baskets;

  function draw() {
    const membership = themeState.membership === "disclosed" && comparisons ? "disclosed" : "fixed";
    const selected = membership === "disclosed" ? { ...report, ...comparisons.disclosed } : report;
    for (const [key, button] of controls) button.setAttribute("aria-pressed", String(key === membership));
    const history = createEtfHistory(selected, context, membership);
    display.replaceChildren(renderEtfSummary(selected, context),
      renderEtfDailyReport(selected, { ...context, onHistoryScope: history.setScope }), history.node);
  }

  const selector = comparisons ? el("section", { class: "card stack", "aria-label": "篮子口径" },
    el("h2", { class: "card-title" }, "篮子口径"),
    marketTable({
      label: "固定与披露规则口径对照",
      columns: [{ label: "篮子" }, { label: "可算 / 应有", numeric: true }, { label: "净申赎（亿元）", numeric: true }],
      rows: Object.entries(comparisons).map(([key, { basket, summary }]) => {
        const button = el("button", { type: "button", class: "market-row-label", onclick: () => {
          themeState.membership = key;
          draw();
        } }, basket.name);
        controls.set(key, button);
        return el("tr", {}, el("td", {}, button), el("td", { class: "num" }, coverage(summary)),
          el("td", { class: `num ${signClass(summary.flow_display_yi)}` }, number(summary.flow_display_yi)));
      }),
    }),
    el("p", { class: "card-sub" }, `披露规则池截止 ${disclosureTimeFormat.format(new Date(report.disclosures.cutoff))}`,
      report.disclosures.availability_assumption === "date_only_next_day_shanghai_and_catalog_listing_period"
        ? " · 披露时点重建，只有披露日的原件自上海时间次日零点可见" : null),
  ) : null;
  draw();
  return el("div", { class: "stack" }, selector, report.report_id ? null : renderEtfSync(report, context, status), display,
    renderDisclosureEvents(report.disclosures));
}

export async function renderMarketEtf(context) {
  const { api, tradeDate, themeState } = context;
  const [report, status] = await Promise.all([
    readEtfReport(api, tradeDate, themeState).catch(error => ({ error: error.message })),
    api("/api/market/etf/sync/status").catch(() => ({ status: "unknown" })),
  ]);
  if (report.error) return renderEtfReplay(context, null, report.error);
  return el("div", { class: "stack" }, renderEtfReplay(context, report), renderEtfBasketReports(report, context, status));
}

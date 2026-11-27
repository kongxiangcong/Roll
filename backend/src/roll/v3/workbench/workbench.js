const main = document.querySelector("main");
const context = document.querySelector("#context");
const symbolNames = {
  "600362.SH": "江西铜业",
  "000300.SH": "沪深 300",
  "801055.SI": "申万工业金属",
  "512400.SH": "有色金属 ETF",
};
const labels = {
  WATCH: "观察", HOLD: "持有", BUY: "买入", SELL: "卖出", RISK_EXIT_PENDING: "退出待执行",
  FILLED: "已成交", UNFILLED: "未成交", PARTIAL: "部分成交", PENDING: "待核对",
  OBSERVED: "已观察", UNREPORTED: "待录入", DEVIATION: "执行偏差", CONFIRMED: "已确认",
  REJECTED: "已拒绝", NOT_EXECUTED: "未执行", HISTORICAL_RECONSTRUCTION: "历史重建",
  pass: "通过", fail: "未通过", inconclusive: "证据不足", usable: "可用", unknown: "未知",
  downtrend: "下行趋势", uptrend: "上行趋势", range: "区间震荡",
  active: "有效", expired: "已过期", missing: "缺失", not_effective: "尚未生效",
  intact: "有效", watch: "观察", broken: "已证伪", trading: "交易", suspended: "已暂停",
  admitted: "已准入", accepted: "已通过历史验收", retired: "已退役", frozen: "已冻结",
  live: "真实前向", rehearsal: "演练", reconstructed: "历史重建",
  LIVE_RUN: "实际取得时间", STRICT_HISTORICAL_AS_OF: "严格历史时点", RECONSTRUCTED_RESEARCH: "重建研究",
  research_hypothesis: "研究假设", data_quality: "数据质量",
  execution_deviation: "执行偏差", user_deviation: "用户偏差",
  strategy_applicability: "策略适用性", normal_variation: "正常波动",
};
const reasons = {
  CLOSE_UNAVAILABLE: "缺少可用收盘价",
  TRADING_STATUS_UNKNOWN: "交易状态未知",
  CONFIRM_OPENING_STATUS_AND_PRICE_BANDS: "次日须核查开盘状态与涨跌停边界",
  SUSPENDED_AT_CUTOFF: "裁决时证券停牌",
  RISK_BUDGET_WITHIN_LIMITS: "账户符合风险预算",
  RISK_BUDGET_MISSING: "风险预算缺失",
  DOSSIER_MISSING: "缺少已发布研究档案",
  DOSSIER_EXPIRED: "研究档案已过期",
  FUNDAMENTAL_FAIL: "基本面门禁未通过",
  FUNDAMENTAL_UNKNOWN: "基本面门禁未知",
  THESIS_WATCH: "投资逻辑处于观察状态",
  THESIS_BROKEN: "投资逻辑已证伪",
  TRIGGER_UNKNOWN: "证伪条件缺少可观测值",
  TRIGGER_FIRED: "已命中证伪条件",
  PRICE_ONLY_SIMULATION: "影子采用独立量价口径",
  STRATEGY_NOT_ADMITTED: "策略尚未准入",
  STRATEGY_NOT_WHITELISTED: "策略不在研究白名单内",
  NO_READY_SIGNAL: "缺少可用策略信号",
  NO_FEASIBLE_STRATEGY: "没有符合约束的主动方案",
  BUY_WITHIN_SHARED_LIMITS: "买入符合账户共享限额",
};
const priorities = ["交易可执行性", "账户风险", "投资逻辑与证据", "策略准入及适用性", "策略信号"];
const timeFormat = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai", dateStyle: "medium", timeStyle: "medium",
});
const fmtNumber = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 });

function node(tag, attributes = {}, ...children) {
  const element = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
  element.append(...children.filter(child => child !== null && child !== undefined));
  return element;
}

function add(parent, ...children) {
  parent.append(...children.filter(child => child !== null && child !== undefined));
  return parent;
}

const panel = (title, ...children) => node("section", { class: "panel" },
  title && node("h3", { class: "panel-title" }, title), ...children);
const text = value => value == null || value === "" ? "—" : String(value);
const label = value => labels[value] ?? text(value);
const amount = value => value == null ? "未知" : `¥${fmtNumber.format(value)}`;
const pct = value => value == null ? "—" : `${(Number(value) * 100).toFixed(2)}%`;
const when = value => value ? `${timeFormat.format(new Date(value))}（北京时间）` : "—";
const empty = message => node("p", { class: "empty" }, message);
const note = message => node("p", { class: "note" }, message);
const shorten = value => value.length > 30 ? `${value.slice(0, 22)}…` : value;
const id = value => node("code", { class: "id" }, text(value));
const action = value => node("span", { class: value === "SELL" ? "action alert" : "action" }, label(value));
const route = (section, reference) => `#${section}/${encodeURIComponent(reference)}`;
const link = (section, reference, title = reference) => node("a", { href: route(section, reference) }, title);

function details(title, child) {
  return node("details", {}, node("summary", {}, title), child);
}

function raw(title, content) {
  const body = typeof content === "string" ? content : JSON.stringify(content, null, 2);
  return details(title, node("pre", { class: "raw" }, text(body)));
}

function definition(pairs, className = "facts") {
  return node("dl", { class: className }, ...pairs.map(([key, value]) => node("div", {},
    node("dt", {}, key), node("dd", {}, value ?? "—"),
  )));
}

function table(columns, rows) {
  return node("div", { class: "table-scroll" }, node("table", {},
    node("thead", {}, node("tr", {}, ...columns.map(name => node("th", { scope: "col" }, name)))),
    node("tbody", {}, ...rows.map(row => node("tr", {}, ...row.map(value => node("td", {}, value ?? "—"))))),
  ));
}

function reasonText(code) {
  const key = code.split(":").find(part => reasons[part]);
  return node("div", {}, reasons[key] && node("span", {}, reasons[key]), node("code", {}, code));
}

function input(title, name, options = {}) {
  return node("label", {}, title, node("input", { name, autocomplete: "off", ...options }));
}

function area(title, name, options = {}) {
  return node("label", {}, title, node("textarea", { name, ...options }));
}

function select(title, name, choices, selected) {
  const menu = node("select", { name }, ...choices.map(([value, title]) =>
    node("option", { value }, title)));
  if (selected != null) menu.value = selected;
  return node("label", {}, title, menu);
}

function reading(form) {
  return Object.fromEntries([...new FormData(form)].map(([key, value]) => [key, value.trim() || null]));
}

function query(path, params = {}) {
  const args = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value != null && value !== "") args.set(key, value);
  }
  return args.size ? `${path}?${args}` : path;
}

async function api(path, params = {}, body) {
  const options = body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
  const response = await fetch(query(path, params), options);
  const result = await response.json();
  if (!response.ok) {
    const detail = Array.isArray(result.detail) ? result.detail.map(item => item.msg).join("，") : result.detail;
    throw new Error(detail || `请求失败（${response.status}）`);
  }
  return result;
}

function form(button, run, ...fields) {
  const submit = node("button", {}, button);
  const status = node("p", { class: "status", role: "status" });
  const element = node("form", { class: "fields" }, ...fields, node("div", {}, submit), status);
  element.addEventListener("submit", async event => {
    event.preventDefault();
    submit.disabled = true;
    status.className = "status";
    status.textContent = "处理中…";
    try {
      const message = await run(reading(element), element);
      status.textContent = message ?? "";
    } catch (error) {
      status.className = "status error";
      status.textContent = error.message;
    } finally {
      submit.disabled = false;
    }
  });
  return element;
}

const names = {
  plans: "盘后计划", research: "个股研究", experiments: "策略实验", account: "账户镜像", reviews: "复盘登记",
};
let scope = reading(context);
let generation = 0;

function afterClose() {
  return { book_id: scope.book_id, as_of: scope.as_of, symbols: [scope.symbol] };
}

function lookup(title, name, section, placeholder = "") {
  return form("读取", fields => {
    location.hash = route(section, fields[name]);
  }, input(title, name, { required: "", placeholder }));
}

function openReview(result) {
  const hash = route("reviews", result.registration_id);
  reviewClocks.set(result.registration_id, result.registered_at);
  if (location.hash === hash) showPage();
  else location.hash = hash;
}

function registrationForm(strategies) {
  return form("冻结并登记", async fields => {
    const result = await api("/api/reviews", {}, {
      ...afterClose(),
      mode: fields.mode,
      now: fields.now,
      price_only: fields.price_only === null ? null : fields.price_only === "true",
      strategy_versions: fields.version ? [fields.version] : [],
    });
    openReview(result);
  }, select("登记用途", "mode", [["live", "真实前向"], ["rehearsal", "演练"], ["reconstructed", "历史重建"]]),
  select("候选影子策略", "version", [["", "沿用上次登记"], ...strategies.filter(item => item.simulation_eligible)
    .map(item => [item.strategy.version, item.strategy.version])]),
  details("影子口径和演练时钟", node("div", { class: "fields" },
    select("量价口径", "price_only", [["", "沿用上次登记"], ["true", "独立量价"], ["false", "应用研究约束"]]),
    input("演练或重建时钟", "now", { placeholder: "ISO 8601 时间，含时区" }),
  )));
}

function planView(plan) {
  const hero = node("section", { class: "panel hero" },
    node("h3", { class: "panel-title" }, plan.simulated ? "影子计划" : plan.plan_id ? "生效交易计划" : "裁决预览"),
    action(plan.action),
    node("h2", {}, `${symbolNames[plan.symbol] ?? plan.symbol} · ${plan.session}`),
    note(`裁决截止 ${when(plan.as_of)}`),
    definition([["计划股数", plan.quantity], ["当前持仓", plan.current_quantity],
      ["可卖股数", plan.sellable_quantity], ["资金预留", amount(plan.cash_reserved)]]),
    definition([["市场状态", label(plan.market_state)], ["行业状态", label(plan.industry_state)],
      ["个股状态", label(plan.stock_state)], ["研究逻辑", label(plan.research.thesis_status ?? plan.research.status)]]),
  );
  const decision = panel("P0–P4 裁决",
    node("ol", { class: "reason-list" }, ...priorities.map((title, index) => {
      const key = `P${index}`;
      return node("li", {}, node("strong", {}, `${key} ${title}`),
        node("div", {}, ...(plan.reasons[key] ?? []).map(reasonText)));
    })),
    plan.candidates.length ? details("候选策略与排除依据", table(["策略版本", "注册状态", "取舍依据"],
      plan.candidates.map(candidate => [
        candidate.evidence_ref ? link("experiments", candidate.evidence_ref, candidate.strategy_version) :
          id(candidate.strategy_version),
        `${label(candidate.registry_status)}${candidate.simulation_only ? " · 仅影子" : ""}`,
        node("div", {}, ...candidate.selection_reasons.map(reasonText)),
      ]))) : null,
  );
  const trace = panel("执行条件与版本",
    definition([["所属账本", id(plan.book_id)], ["计划版本", id(plan.plan_id)],
      ["市场快照", id(plan.snapshot_id)],
      ["研究档案", plan.dossier_version ? link("research", plan.dossier_version) : "—"],
      ["账户快照", link("account", plan.account_snapshot_id, shorten(plan.account_snapshot_id))],
      ["风险预算", id(plan.budget_id)], ["策略版本", id(plan.strategy_version)],
      ["有效至", when(plan.valid_until)]], "references"),
    raw("冻结执行条件", {
      执行时段: plan.execution_window, 执行条件: plan.execution_conditions,
      撤销条件: plan.cancel_conditions, 退出条件: plan.exit_conditions,
      未成交处理: plan.if_unfilled, 盘中预设动作: plan.intraday_actions,
    }),
    raw("完整计划记录", plan),
  );
  return node("div", { class: "stack" }, hero, decision, trace);
}

async function plansPage(reference) {
  const [strategies, plans] = await Promise.all([
    api(`/api/strategies/${encodeURIComponent(scope.symbol)}`, { as_of: scope.as_of }),
    reference ? api(`/api/plans/${encodeURIComponent(reference)}`).then(plan => [plan]) :
      api("/api/plans", { book_id: scope.book_id }),
  ]);
  const matching = reference ? plans : plans.filter(item => item.symbol === scope.symbol);
  const latest = matching.at(-1);
  const result = node("div", { class: "stack" }, latest ? planView(latest) :
    empty("这个证券和账户暂无已登记计划。可以先预览盘后裁决，再冻结并登记。"));
  if (matching.length > 1) add(result, panel("近期计划", table(["执行日", "生效方案", "计划版本"],
    matching.slice(-20).reverse().map(plan => [plan.session, action(plan.action),
      link("plans", plan.plan_id, shorten(plan.plan_id))]))));
  const controls = node("div", { class: "stack" }, panel("生成与登记",
    note("使用上方裁决截止时点。候选策略在连续影子账户运行。"),
    form("预览裁决", async () => {
      const { plans } = await api("/api/plans/preview", {}, afterClose());
      result.replaceChildren(...plans.map(planView));
    }),
    node("div", { class: "console" }, registrationForm(strategies))),
  panel("离线重放", lookup("已发布的计划标识", "plan_id", "plans")));
  return node("div", { class: "work-layout" }, result, controls);
}

function sourceLink(url, title) {
  if (typeof url !== "string") return title;
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "https:" || parsed.protocol === "http:") {
      return node("a", { href: parsed.href, target: "_blank", rel: "noreferrer noopener" }, title);
    }
  } catch {
    return title;
  }
  return title;
}

function evidenceList(evidence) {
  if (!evidence.length) return empty("当前时点暂无已发布的公开证据。");
  return node("ul", { class: "evidence-list" }, ...evidence.map(item => node("li", {},
    sourceLink(item.url, item.title || item.id),
    node("div", { class: "subtle" }, [item.source, item.locator].filter(Boolean).join(" · ")),
  )));
}

function dossierView(dossier, evidence) {
  if (!dossier) return panel("研究档案", empty("所选时点暂无有效研究档案。"), evidenceList(evidence));
  return panel("研究档案",
    definition([["版本", id(dossier.version)], ["基本面门禁", label(dossier.fundamental_gate)],
      ["投资逻辑", label(dossier.thesis_status)]]),
    definition([["审核人", dossier.reviewer], ["生效时间", when(dossier.effective_at)],
      ["有效期至", when(dossier.valid_until)]], "references"),
    dossier.hypothesis ? node("p", {}, String(dossier.hypothesis)) : null,
    dossier.invalidation_triggers.length ? details("证伪条件", table(["条件", "比较", "触发影响"],
      dossier.invalidation_triggers.map(trigger => [
        id(trigger.id ?? trigger.feature), [trigger.feature, trigger.operator, trigger.threshold].filter(item => item != null).join(" "),
        trigger.effect,
      ]))) : null,
    details("公开证据", evidenceList(dossier.evidence)),
    raw("档案 Markdown 原文", dossier.markdown),
  );
}

function marketView(report, url) {
  const target = report.securities[report.symbol];
  const windows = Object.entries(target.windows).map(([days, window]) =>
    [days, label(window.status), pct(window.return), pct(window.annualized_volatility),
      pct(window.max_drawdown), pct(report.benchmark.windows[days]?.relative_return)]);
  return [
    definition([["研究窗口", `${report.start} — ${report.end}`], ["数据用途", label(report.snapshot.use_mode)],
      ["有效收盘", `${target.coverage.effective_count} / ${target.coverage.expected_count}`]]),
    table(["证券", "有效 / 预期交易日", "实际首末日", "停牌", "缺口"], Object.entries(report.securities).map(([code, item]) => {
      const c = item.coverage;
      return [symbolNames[code] ?? code, `${c.effective_count} / ${c.expected_count}`,
        c.first_date ? `${c.first_date} — ${c.last_date}` : "—", c.suspended_dates.length, c.gap_dates.length];
    })),
    node("h3", {}, "多周期量价"),
    table(["交易日", "样本状态", "区间收益", "年化波动", "最大回撤", "对宽基超额"], windows),
    node("h3", {}, "行业依据"),
    report.industry_memberships.length ? node("ul", { class: "evidence-list" },
      ...report.industry_memberships.map(item => node("li", {},
        sourceLink(item.source_ref, item.payload.index_name ?? item.payload.index_symbol),
        node("div", { class: "subtle" }, `${item.payload.effective_start} — ${item.payload.effective_end} · ${item.payload.membership_basis}`),
      ))) : empty("冻结区间内暂无可核验的行业归属证据。"),
    report.industry_comparisons.length ? details("行业和 ETF 对照区间", table(["证券", "区间", "口径", "20 日相对收益"],
      report.industry_comparisons.map(item => [item.symbol, `${item.start} — ${item.end}`,
        item.kind === "etf_proxy" ? "ETF 对照" : "行业比较", pct(item.stock_relative_windows?.["20"]?.relative_return)]))) : null,
    definition([["行情快照", id(report.snapshot_id)], ["公开导出引用", id(report.reference)]], "references"),
    node("a", { class: "button secondary", href: url, download: "research-export.json" }, "下载完整公开数据"),
  ].filter(Boolean);
}

function researchForms(basePath, result, activeVersion) {
  const draftText = area("Markdown 草稿", "markdown", { required: "", rows: "8",
    placeholder: "粘贴含 YAML 元数据的 Markdown" });
  const version = input("草稿版本", "version", { placeholder: "默认读取 Markdown 中的 version" });
  const publicationVersion = input("档案版本", "version", { value: activeVersion ?? "", required: "" });
  return panel("编辑与发布",
    form("导入草稿", async (fields, element) => {
      const draft = await api(`${basePath}/drafts`, {}, {
        version: fields.version, markdown: new FormData(element).get("markdown"),
      });
      publicationVersion.querySelector("input").value = draft.version;
      return `已保存草稿 ${draft.version}`;
    }, version, draftText),
    node("div", { class: "console" }, form("确认发布", async fields => {
      const dossier = await api(`${basePath}/dossiers`, {}, fields);
      result.replaceChildren(dossierView(dossier, dossier.evidence));
      return `已发布 ${dossier.version}`;
    }, publicationVersion, input("审核人", "reviewer", { required: "" }),
    input("指定生效时间（可选）", "effective_at", { placeholder: "ISO 8601 时间，含时区" }))),
  );
}

async function researchPage(reference) {
  const symbol = encodeURIComponent(scope.symbol);
  const base = `/api/research/${symbol}`;
  const cutoff = { as_of: scope.as_of };
  const [dossier, sources, snapshots] = await Promise.all([
    api(`${base}/dossiers`, { ...cutoff, version: reference }),
    api(`${base}/inputs`, cutoff),
    api("/api/market/snapshots", { symbol: scope.symbol }),
  ]);
  const current = node("div", {}, dossierView(dossier, sources.evidence));
  const coverage = node("div", { class: "stack" });
  const snapshotField = input("冻结快照标识", "snapshot_id", { required: "" });
  const startField = input("研究起始日", "start", { type: "date", required: "" });
  const endField = input("研究截止日（可选）", "end", { type: "date" });
  const choices = snapshots.map(item => {
    const bars = item.scope.filter(range => range.symbol === scope.symbol && range.series === "daily_bar");
    const start = bars.map(range => range.start).sort()[0];
    const end = bars.map(range => range.end).sort().at(-1);
    return { ...item, start, end, span: Date.parse(end) - Date.parse(start) };
  });
  const selection = select("已冻结快照", "snapshot", [["", "手动输入快照标识"],
    ...choices.map(item => [item.snapshot_id, `${item.start} — ${item.end} · ${label(item.use_mode)} · ${shorten(item.snapshot_id)}`])],
  );
  const snapshotMenu = selection.querySelector("select");
  function fillSnapshot() {
    const snapshot = choices.find(item => item.snapshot_id === snapshotMenu.value);
    snapshotField.querySelector("input").value = snapshot?.snapshot_id ?? "";
    startField.querySelector("input").value = snapshot?.start ?? "2020-01-02";
    endField.querySelector("input").value = "";
  }
  snapshotMenu.addEventListener("change", fillSnapshot);
  const historical = choices.filter(item => item.use_mode !== "LIVE_RUN").sort((a, b) => b.span - a.span)[0];
  snapshotMenu.value = historical?.snapshot_id ?? choices[0]?.snapshot_id ?? "";
  fillSnapshot();

  const followups = node("div", {});
  const findFollowups = async (mode, asOf) => {
    const items = await api(`${base}/followups`, { as_of: asOf, mode });
    followups.replaceChildren(items.length ? table(["原始档案", "证伪条件", "证据与复盘"],
      items.map(item => [item.dossier_version, id(item.trigger_id),
        node("div", {}, ...item.evidence_refs.map(ref => node("div", {}, id(ref))),
          link("reviews", item.registration_id, "查看关联复盘"))])) : empty("这个用途在所选时点暂无待复核事项。"));
  };
  return node("div", { class: "work-layout" },
    node("div", { class: "stack" }, current,
      panel("公开行情与覆盖",
        form("读取冻结行情", async ({ snapshot, ...fields }) => {
          const params = { ...fields, ...cutoff };
          const report = await api(`${base}/export`, params);
          coverage.replaceChildren(...marketView(report, query(`${base}/export`, { ...params, download: true })));
        }, selection, snapshotField, node("div", { class: "two-fields" }, startField, endField)),
        coverage,
      ),
      panel("复盘提出的研究事项",
        form("查询复核事项", async fields => findFollowups(fields.mode, cutoff.as_of),
          modesField(),
        ), followups),
    ),
    node("div", { class: "stack" }, researchForms(base, current, reference),
      panel("历史档案", lookup("已发布的档案版本", "version", "research"))),
  );
}

const experimentPaths = [
  ["trend", "冻结趋势"], ["buy_and_hold", "买入持有"], ["no_active_trading", "不主动交易"],
];

function experimentView(report) {
  const configuration = report.configuration;
  const result = node("div", { class: "stack" }, panel("实验结果",
    action(report.verdict),
    definition([["实验运行", id(report.run_id)], ["冻结策略", id(configuration.strategy.version)],
      ["交易日覆盖", report.coverage.sessions], ["数据路径缺口", report.coverage.path_gaps.length]]),
    definition([["结果版本", id(report.report_id)], ["市场快照", id(configuration.market_snapshot.snapshot_id)],
      ["实验协议", id(configuration.protocol.version)], ["研究档案引用", id(configuration.research_ref)]], "references"),
    node("div", { class: "controls" },
      node("a", { class: "button secondary", download: "experiment-summary.json",
        href: query(`/api/experiments/${encodeURIComponent(report.run_id)}`, { download: true }) }, "下载报告"),
      node("a", { class: "button secondary", download: "experiment-trace.json",
        href: query(`/api/experiments/${encodeURIComponent(report.run_id)}`, { download: true, trace: true }) }, "下载逐日账本"),
    ),
  ));
  for (const [stage, title] of [["acceptance", "锁定验收"], ["development", "开发窗口"]]) {
    const window = report.windows[stage];
    if (!window) continue;
    add(result, panel(title,
      note(`${window.start} — ${window.end} · ${window.evaluable_sessions} 个可评估交易日`),
      table(["路径", "净收益", "最大回撤", "成交笔数", "成本"], experimentPaths.map(([path, name]) => {
        const metrics = window.paths[path];
        return [name, pct(metrics.total_return), pct(metrics.max_drawdown), metrics.fills, amount(metrics.costs)];
      })),
    ));
  }
  if (report.limitations.length || report.verdict_reasons.length) add(result, panel("结果范围",
    node("ul", { class: "evidence-list" }, ...[...report.limitations, ...report.verdict_reasons]
      .map(item => node("li", {}, item)))));
  return result;
}

async function experimentsPage(reference) {
  const [runs, strategies] = await Promise.all([
    api("/api/experiments", { symbol: scope.symbol }),
    api(`/api/strategies/${encodeURIComponent(scope.symbol)}`, { as_of: scope.as_of }),
  ]);
  const selected = reference ?? runs[0]?.run_id;
  const report = selected ? await api(`/api/experiments/${encodeURIComponent(selected)}`) : null;
  return node("div", { class: "work-layout" },
    report ? experimentView(report) : empty("当前证券暂无已完成的冻结实验。"),
    node("div", { class: "stack" }, panel("查找实验",
      lookup("运行编号或报告版本", "reference", "experiments"),
      runs.length ? table(["已完成运行", "冻结策略"], runs.map(run =>
        [link("experiments", run.run_id), id(run.strategy_version)])) : null,
    ), panel("策略注册",
      strategies.length ? table(["冻结版本", "注册状态"], strategies.map(item =>
        [id(item.strategy.version), label(item.status)])) : empty("所选时点暂无冻结的策略版本。"),
    )),
  );
}

async function accountPage(reference) {
  const account = await api("/api/account", {
    book_id: scope.book_id, as_of: scope.as_of, snapshot_id: reference,
  });
  const budget = account.risk_budget;
  return node("div", { class: "work-layout" },
    node("div", { class: "stack" }, panel("本地账户镜像",
      definition([["账本", account.book_id], ["现金", amount(account.cash)],
        ["券商可用现金", amount(account.available_cash)]]),
      definition([["账户快照", id(account.snapshot_id)], ["生效截止", when(account.effective_at)],
        ["获知截止", when(account.known_at)]], "references"),
      raw("账户快照完整记录", account),
    ), panel("持仓批次",
      account.lots.length ? table(["证券", "批次", "持有股数", "取得日期", "批次成本"], account.lots.map(lot =>
        [lot.symbol, id(lot.lot_id), lot.quantity, lot.acquired_on, amount(lot.cost)])) :
        empty("该账户快照没有持仓。"),
      Object.keys(account.known_sellable).length ? definition(Object.entries(account.known_sellable)
        .map(([symbol, quantity]) => [`${symbol} 已知可卖股数`, quantity ?? "未知"])) : null,
    ), panel("在途权益", account.receivables.length ?
      table(["证券", "现金", "股数", "应结转日"], account.receivables.map(item =>
        [item.symbol, amount(item.amount), item.quantity, item.due_date])) : empty("该账户快照没有在途权益。"),
    )),
    node("div", { class: "stack" }, panel("风险预算", budget ? definition([
      ["版本", id(budget.budget_id)], ["现金保留额", amount(budget.cash_reserve)],
      ["总仓上限", pct(budget.max_total_exposure)], ["单票上限", pct(budget.max_symbol_exposure)],
      ["行业上限", pct(budget.max_industry_exposure)], ["有效期", when(budget.expires_at)],
    ]) : empty("该时点没有有效风险预算。")),
    panel("历史账户快照", lookup("账户快照标识", "snapshot_id", "account"))),
  );
}

function modesField() {
  return select("登记用途", "mode", [["live", "真实前向"], ["rehearsal", "演练"], ["reconstructed", "历史重建"]]);
}

const reviewClocks = new Map();

function recordView(review) {
  return panel("原计划、影子与真实结果",
    definition([["登记用途", label(review.mode)], ["裁决日", review.decision_date], ["执行日", review.session]]),
    definition([["登记标识", id(review.registration_id)], ["登记时间", when(review.registered_at)],
      ["影子账本", id(review.shadow_book_id)]], "references"),
    ...review.plans.map(entry => {
      const real = entry.real_plan;
      const active = entry.active_real_plan;
      const paper = entry.shadow_plan;
      const shadow = entry.shadow;
      const report = entry.actual.events.at(-1);
      return node("section", { class: "review-item" },
        node("h3", {}, symbolNames[entry.symbol] ?? entry.symbol),
        table(["记录", "状态", "数量", "版本 / 结果"], [
          ["正式计划", action(real.action), real.quantity,
            review.mode === "reconstructed" ? details("读取历史裁决", planView(real)) :
              link("plans", real.plan_id, shorten(real.plan_id))],
          ...(active && active.plan_id !== real.plan_id ? [
            ["修订计划", action(active.action), active.quantity, link("plans", active.plan_id, shorten(active.plan_id))],
          ] : []),
          ["影子计划", action(paper.action), paper.quantity,
            link("plans", paper.plan_id, shorten(paper.plan_id))],
          ["影子结算", shadow ? action(shadow.status) : "待结算", shadow?.fill?.quantity,
            shadow?.fill ? amount(shadow.fill.price) : shadow?.reason],
          ["实际执行", action(entry.actual.status), entry.actual.fills.reduce((n, fill) => n + fill.payload.quantity, 0),
            report?.reason],
        ]),
        entry.findings.length ? details("复盘归因", table(["分类", "说明", "证据引用"],
          entry.findings.map(item => [label(item.category), item.reason,
            node("div", {}, ...item.evidence_refs.map(ref => node("div", {}, id(ref))))]))) : null,
        entry.deviations.length ? raw("偏差记录", entry.deviations) : null,
      );
    }),
    review.shadow_closing ? raw("影子期末估值", review.shadow_closing) : null,
    raw("完整复盘记录", review),
  );
}

function outcomeForm(endpoint, symbols, fixedClock, refresh) {
  const status = select("实际结果", "status", [
    ["confirmed", "确认"], ["rejected", "拒绝"], ["not_executed", "未执行"], ["filled", "券商成交"],
  ]);
  const fillFields = node("fieldset", { class: "fields broker-fill", disabled: "", hidden: "" },
    node("legend", {}, "券商成交"),
    input("成交流水编号", "event_id", { required: "" }),
    input("成交发生时点", "effective_at", { required: "", placeholder: "ISO 8601 时间，含时区" }),
    select("方向", "side", [["BUY", "买入"], ["SELL", "卖出"]]),
    input("股数", "quantity", { required: "", type: "number", min: "1", step: "1" }),
    input("成交价", "price", { required: "", inputmode: "decimal" }),
    input("实际费用", "fee", { required: "", inputmode: "decimal" }),
    input("券商回报时点（可选）", "reported_at", { placeholder: "ISO 8601 时间，含时区" }),
  );
  status.addEventListener("change", () => {
    const visible = status.querySelector("select").value === "filled";
    fillFields.disabled = !visible;
    fillFields.hidden = !visible;
  });
  return form("记录实际结果", async fields => {
    const { symbol, status, reason, reported_at, now, ...fill } = fields;
    if (status === "filled") fill.quantity = Number(fill.quantity);
    const review = await api(`${endpoint}/outcomes`, {}, {
      symbol, status, reason, reported_at, now, fill: status === "filled" ? fill : null,
    });
    refresh(review, now);
    return "已记录实际结果。";
  }, select("证券", "symbol", symbols), status, input("执行说明", "reason"), fillFields,
  fixedClock && input("演练时钟", "now", { placeholder: "ISO 8601 时间，含时区" }));
}

async function reviewsPage(reference) {
  const results = node("div", {});
  const recent = await api("/api/reviews", { book_id: scope.book_id, as_of: scope.as_of });
  const reviewId = reference ?? recent.at(-1)?.registration_id;
  const endpoint = reviewId && `/api/reviews/${encodeURIComponent(reviewId)}`;
  const knownAt = reviewClocks.get(reviewId) ?? scope.as_of;
  const review = reviewId ? await api(endpoint, { as_of: knownAt }) : null;
  function refresh(record, time) {
    if (time) reviewClocks.set(record.registration_id, time);
    results.replaceChildren(recordView(record));
  }
  if (review) refresh(review);
  else results.replaceChildren(empty("当前账户暂无复盘登记。盘后计划页可冻结并登记。"));

  const side = node("div", { class: "stack" }, panel("查找复盘",
    lookup("登记标识", "registration_id", "reviews"),
    recent.length ? table(["裁决日", "登记用途"], recent.slice(-20).reverse().map(item =>
      [link("reviews", item.registration_id, item.decision_date), label(item.mode)])) : null,
  ));
  if (review) {
    const fixedClock = review.mode !== "live";
    const selectable = review.plans.map(item => [item.symbol, item.symbol]);
    const clockField = () => fixedClock && input("演练或重建时钟", "now", {
      placeholder: "ISO 8601 时间，含时区", value: knownAt ?? "",
    });
    add(side, panel("次日结算", form("结算影子账户", async ({ now }) => {
      refresh(await api(`${endpoint}/settle`, {}, { now }), now);
      return "该时点的影子结算已核对。";
    }, clockField())));
    if (review.mode !== "reconstructed") add(side, panel("实际执行",
      outcomeForm(endpoint, selectable, fixedClock, refresh)));
    add(side, panel("复盘归因", form("记录复盘事项", async ({ evidence_refs, ...fields }) => {
      const evidence = evidence_refs ? evidence_refs.split("\n").map(ref => ref.trim()).filter(Boolean) : [];
      refresh(await api(`${endpoint}/findings`, {}, { ...fields, evidence_refs: evidence }), fields.now);
      return "已记录复盘事项。";
    }, select("证券", "symbol", selectable), select("归因类别", "category", [
      ["research_hypothesis", "研究假设"], ["strategy_applicability", "策略适用性"],
      ["data_quality", "数据质量"], ["execution_deviation", "执行偏差"],
      ["user_deviation", "用户偏差"], ["normal_variation", "正常波动"],
    ]), input("原档案证伪条件标识（可选）", "trigger_id"),
    area("归因说明", "reason", { required: "" }), area("证据引用（每行一条）", "evidence_refs"),
    clockField(),)));
  }
  return node("div", { class: "work-layout" }, results, side);
}

const pages = { plans: plansPage, research: researchPage, experiments: experimentsPage, account: accountPage, reviews: reviewsPage };

function currentSection() {
  const section = location.hash.slice(1).split("/")[0];
  return Object.hasOwn(pages, section) ? section : "plans";
}

async function showPage() {
  const ticket = ++generation;
  const section = currentSection();
  const heading = node("h2", {}, names[section]);
  const body = node("div", {}, empty("正在读取本地数据…"));
  main.replaceChildren(node("div", { class: "section-heading" }, heading), body);
  for (const anchor of document.querySelectorAll("nav a")) {
    if (anchor.hash === `#${section}`) anchor.setAttribute("aria-current", "page");
    else anchor.removeAttribute("aria-current");
  }
  try {
    const encoded = location.hash.slice(1).split("/")[1];
    const content = await pages[section](encoded ? decodeURIComponent(encoded) : null);
    if (generation === ticket) body.replaceChildren(content);
  } catch (error) {
    if (generation === ticket) body.replaceChildren(node("p", { class: "error", role: "alert" }, error.message));
  }
}

context.addEventListener("submit", event => {
  event.preventDefault();
  const next = reading(context);
  next.symbol = next.symbol.toUpperCase();
  context.elements.symbol.value = next.symbol;
  document.querySelector("#security-name").textContent = symbolNames[next.symbol] ?? "证券工作台";
  document.querySelector("#security-code").textContent = next.symbol;
  const changeSecurity = next.symbol !== scope.symbol;
  scope = next;
  if (changeSecurity && location.hash.includes("/")) location.hash = currentSection();
  else showPage();
});
window.addEventListener("hashchange", () => {
  if (location.hash !== "#workspace") showPage();
});
showPage();

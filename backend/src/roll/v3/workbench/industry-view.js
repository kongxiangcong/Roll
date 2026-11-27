import { el, marketMasterDetail, marketTable } from "./market-view.js";

const num = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 });
const number = value => value == null ? "—" : num.format(Number(value));
const signed = (value, unit = "") => value == null ? "—" :
  `${Number(value) > 0 ? "+" : ""}${Number(value).toFixed(2)}${unit}`;
const color = value => value == null || Number(value) === 0 ? "muted" : Number(value) > 0 ? "up" : "down";
const cell = (value, cls = "") => el("td", { class: `num ${cls}` }, value);
const columns = (labels) => labels.map((label, index) => ({ label, numeric: index > 0 }));

function unitLabel(value, unit) {
  if (value == null || !unit) return number(value);
  const label = { share: "股", CNY: "元" }[unit];
  return label ? `${number(value)} ${label}` : number(value);
}

function external(label, href) {
  return href && /^https?:\/\//i.test(href) ? el("a", { href, target: "_blank", rel: "noopener noreferrer" }, label) : null;
}

function trendChart(points, name, benchmark) {
  const lines = [
    { name, color: "#2563eb", samples: points.map(point => point.industry?.change_pct) },
    { name: benchmark, color: "#64748b", samples: points.map(point => point.benchmark?.change_pct) },
  ];
  const values = lines.flatMap(line => line.samples).filter(value => value != null);
  if (!values.length) return el("div", { class: "empty-state" }, "暂无可计算的日涨跌幅");

  const canvas = el("canvas", { width: 840, height: 218, role: "img", "aria-label": `${name}与${benchmark}同期涨跌` });
  const ctx = canvas.getContext("2d");
  const scale = Math.max(0.01, ...values.map(value => Math.abs(Number(value))));
  const x = index => points.length > 1 ? 14 + 812 * index / (points.length - 1) : 420;
  const y = value => 109 - 92 * Number(value) / scale;
  for (const value of [scale, 0, -scale]) {
    ctx.strokeStyle = value === 0 ? "#cbd5e1" : "#e4e8ef";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, y(value));
    ctx.lineTo(840, y(value));
    ctx.stroke();
  }
  for (const line of lines) {
    ctx.strokeStyle = ctx.fillStyle = line.color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    line.samples.forEach((value, index) => {
      if (value == null) return;
      const draw = line.samples[index - 1] == null ? "moveTo" : "lineTo";
      ctx[draw](x(index), y(value));
    });
    ctx.stroke();
    line.samples.forEach((value, index) => {
      if (value == null) return;
      ctx.beginPath();
      ctx.arc(x(index), y(value), 4, 0, 2 * Math.PI);
      ctx.fill();
    });
  }
  return el("figure", { class: "market-industry-chart" },
    el("div", { class: "market-industry-chart-body" },
      el("div", { class: "market-industry-axis muted", "aria-hidden": "true" },
        el("span", {}, signed(scale, "%")), el("span", {}, "0%"), el("span", {}, signed(-scale, "%"))),
      canvas,
    ),
    el("figcaption", { class: "market-metadata card-sub" }, lines.map(line =>
      el("span", { class: "market-industry-legend" }, el("i", { style: `background:${line.color}` }), line.name))),
  );
}

function detailFor(row, report, points) {
  const { benchmark } = report;
  const bar = row.bar;
  const identity = row.identity;
  const previous = bar?.previous_trade_date ? `（${bar.previous_trade_date}）` : "";
  return [
    el("div", { class: "focus-header" }, el("div", { class: "focus-id" },
      el("h2", {}, row.name), el("span", { class: "muted num" }, row.symbol)),
      el("span", { class: "pill" }, "一级行业")),
    el("section", { class: "strip" },
      el("h3", { class: "strip-label" }, `${report.trade_date} 日线明细`),
      el("div", { class: "market-metadata num" },
        el("span", {}, `开盘 ${number(bar?.open)}`), el("span", {}, `最高 ${number(bar?.high)}`),
        el("span", {}, `最低 ${number(bar?.low)}`), el("span", {}, `收盘 ${number(bar?.close)}`),
        el("span", {}, `可比前收 ${number(bar?.previous_close)}${previous}`)),
      bar && (bar.unit.volume || bar.unit.amount) ? el("p", { class: "card-sub" },
        `成交量口径 ${bar.unit.volume || "—"} · 成交额口径 ${bar.unit.amount || "—"}`) : null,
    ),
    el("section", { class: "strip" },
      el("h3", { class: "strip-label" }, "同期日涨跌幅"),
      trendChart(points, row.name, benchmark.name),
      marketTable({ label: "同期日线明细", columns: columns(["交易日", "行业收盘", "行业涨跌", "基准收盘", "基准涨跌", "相对百分点"]),
        rows: [...points].reverse().map(point => el("tr", {},
          el("th", { scope: "row", class: "market-date-cell num" }, point.trade_date),
          cell(number(point.industry?.close)), cell(signed(point.industry?.change_pct, "%"), color(point.industry?.change_pct)),
          cell(number(point.benchmark?.close)), cell(signed(point.benchmark?.change_pct, "%"), color(point.benchmark?.change_pct)),
          cell(signed(point.relative_percentage_points), color(point.relative_percentage_points)),
        )),
      }),
    ),
    el("section", { class: "strip market-industry-sources" },
      el("h3", { class: "strip-label" }, "分类与行情来源"),
      el("p", { class: "card-sub" }, `${identity.classification} · ${identity.effective_start} 起 · ${identity.effective_end || "未登记结束日"}`),
      el("div", { class: "market-metadata" },
        external("分类版本原文", identity.classification_ref), external("一级行业名录", identity.source_ref),
        external("分类生效依据", identity.effective_start_ref), external("行业日线来源", bar?.source_ref),
        external("沪深 300 日线来源", benchmark.bar?.source_ref),
      ),
    ),
  ];
}

export async function renderIndustryView({ tradeDate, themeState, api }) {
  const report = await api("/api/market/industry", { params: { trade_date: tradeDate } });
  if (!report.groups.length) {
    return el("section", { class: "card" }, el("div", { class: "empty-state" }, "暂无行业行情"));
  }
  const { benchmark } = report;
  const master = el("section", { class: "card stack", "aria-label": "行业汇总" });
  const detail = el("section", { class: "card strip-group", tabindex: -1, "aria-label": "行业详情" });
  const classification = el("select", { "aria-label": "行业分类", onchange: () => {
    themeState.classification = classification.value;
    paint();
  } }, report.groups.map(group => el("option", { value: group.classification }, group.classification)));
  classification.value = report.groups.some(group => group.classification === themeState.classification)
    ? themeState.classification : report.groups[0].classification;
  const range = el("select", { "aria-label": "行业趋势范围", onchange: () => {
    themeState.range = Number(range.value);
    paint();
  } }, el("option", { value: "20" }, "近 20 个交易日"), el("option", { value: "5" }, "近 5 个交易日"));
  range.value = themeState.range || 20;

  function paint() {
    const group = report.groups.find(candidate => candidate.classification === classification.value);
    const { classified, expected, priced, comparable } = group.coverage;
    const selected = group.rows.find(row => row.symbol === themeState.selectedSymbol) || group.rows[0];
    const benchmarkStatus = benchmark.bar?.change_pct != null ? `${benchmark.name} ${signed(benchmark.bar.change_pct, "%")}` :
      benchmark.bar?.close != null ? `${benchmark.name} 缺少可比前收` : `${benchmark.name} 当日行情缺失`;
    master.replaceChildren(
      el("div", { class: "card-head market-list-controls" }, el("h2", { class: "card-title" }, "一级行业量价"), classification),
      el("div", { class: "market-metadata card-sub" },
        el("span", {}, `已核验 ${classified}${expected == null ? "" : ` / ${expected}`} 个一级行业`),
        el("span", {}, `当日行情 ${priced} · 可比 ${comparable}`),
        el("span", { class: benchmark.bar?.change_pct == null ? "pill pill-warn" : null }, benchmarkStatus),
        comparable < classified && group.last_comparable_trade_date ?
          el("span", {}, `本地行业最近可比日 ${group.last_comparable_trade_date}`) : null,
      ),
      marketTable({ label: "一级行业量价", columns: columns(["行业指数", "收盘", "涨跌幅", "相对百分点", "成交量", "成交额"]),
        rows: group.rows.map(row => el("tr", { class: row === selected ? "market-selected" : null },
          el("th", { scope: "row" }, el("button", {
            type: "button", class: "market-row-label", "aria-pressed": String(row === selected),
            onclick: () => {
              themeState.selectedSymbol = row.symbol;
              paint();
              detail.focus({ preventScroll: !matchMedia("(max-width: 800px)").matches });
            },
          }, el("strong", {}, row.name), el("span", { class: "watch-code" }, row.symbol))),
          cell(number(row.bar?.close)), cell(signed(row.bar?.change_pct, "%"), color(row.bar?.change_pct)),
          cell(signed(row.relative_percentage_points), color(row.relative_percentage_points)),
          cell(unitLabel(row.bar?.volume, row.bar?.unit.volume)), cell(unitLabel(row.bar?.amount, row.bar?.unit.amount)),
        )),
      }),
      el("p", { class: "card-sub" }, "相对百分点为行业同日涨跌幅减沪深 300 同日涨跌幅。成交量额保留发布源口径。"),
    );
    const [heading, ...sections] = detailFor(selected, report, selected.trend.slice(-Number(range.value)));
    detail.replaceChildren(el("div", { class: "market-list-controls market-industry-detail-head" }, heading, range), ...sections);
  }
  paint();
  return marketMasterDetail(master, detail);
}

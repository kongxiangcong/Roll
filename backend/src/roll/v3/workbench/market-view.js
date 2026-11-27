export const el = (tag, attrs = {}, ...children) => {
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

export function marketTable({ label, columns, rows }) {
  return el("div", { class: "table-wrap market-table", tabindex: 0, role: "region", "aria-label": label },
    el("table", { class: "clean", "aria-label": label },
      el("thead", {}, el("tr", {}, columns.map(column =>
        el("th", { scope: "col", class: column.numeric ? "num" : null }, column.label),
      ))),
      el("tbody", {}, rows),
    ),
  );
}

export function marketMasterDetail(master, detail) {
  return el("div", { class: "market-master-detail" }, master, detail);
}

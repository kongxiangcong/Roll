import { useEffect, useState } from "react";
import type { ReactNode } from "react";

export type Numeric = number | string | null;
export function fmt(value: Numeric | undefined, digits = 2) {
  return value == null
    ? "—"
    : Number(value).toLocaleString("zh-CN", { maximumFractionDigits: digits });
}
export const pct = (value: Numeric | undefined) =>
  value == null
    ? "—"
    : fmt(Number(value) * 100, Math.abs(Number(value)) < 0.001 ? 4 : 2) + "%";
const shanghaiTime = new Intl.DateTimeFormat("sv-SE", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});
export const stamp = (value?: string | null) =>
  value ? shanghaiTime.format(new Date(value)) : "—";
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail ?? res.statusText),
    );
  }
  return res.json() as Promise<T>;
}
export function post<T>(path: string, data: unknown) {
  return api<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}
export function useRead<T>(path: string, revision = 0) {
  const [state, set] = useState<{ data?: T; error?: string }>({});
  useEffect(() => {
    let active = true;
    set({});
    api<T>(path)
      .then((data) => active && set({ data }))
      .catch((e) => active && set({ error: String(e.message) }));
    return () => {
      active = false;
    };
  }, [path, revision]);
  return state;
}
export function Panel({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Message({ error, text }: { error?: string; text?: string }) {
  if (!error && !text) return null;
  return (
    <p
      role={error ? "alert" : "status"}
      className={error ? "message error" : "message"}
    >
      {error || text}
    </p>
  );
}
export function Metric({
  label,
  value,
  sub,
}: {
  label: string;
  value: ReactNode;
  sub?: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {sub && <small>{sub}</small>}
    </div>
  );
}
export function Info({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="info">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

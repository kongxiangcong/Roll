import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, Message } from "./ui";
import Market from "./pages/Market";
import Holdings from "./pages/Holdings";
import Validation from "./pages/Validation";
import "./style.css";

const links = [
  ["/", "今日晴雨表", "◒"],
  ["/holdings", "持仓与跟踪池", "▤"],
  ["/validation", "回测与校准", "▥"],
];
function App() {
  const path = location.pathname,
    title = links.find(([p]) => p === path)?.[1] || links[0][1];
  const [day, setDay] = useState(
    new URLSearchParams(location.search).get("day") || "",
  );
  const [error, setError] = useState("");
  useEffect(() => {
    if (!day)
      api<{ trade_date: string }>("/api/session")
        .then((r) => setDay(r.trade_date))
        .catch((e) => setError(e.message));
  }, []);
  function changeDay(value: string) {
    if (!value) return;
    setDay(value);
    history.replaceState({}, "", path + "?day=" + value);
  }
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <span className="logo" aria-hidden="true">
            R
          </span>
          <b>Roll</b>
        </div>
        <nav aria-label="工作台导航">
          {links.map(([p, label, icon]) => (
            <a
              key={p}
              href={p + (day ? "?day=" + day : "")}
              aria-current={p === path ? "page" : undefined}
            >
              <i aria-hidden="true">{icon}</i>
              {label}
            </a>
          ))}
        </nav>
        <div className="local">
          <span />
          本机工作台
        </div>
      </aside>
      <main>
        <header>
          <div>
            <div className="crumb">
              盘后工作台 <b>/</b> {title}
            </div>
            <h1>{title}</h1>
          </div>
          <label className="date">
            交易日
            <input
              type="date"
              value={day}
              onChange={(e) => changeDay(e.target.value)}
            />
          </label>
        </header>
        <Message error={error} />
        {day &&
          (path === "/holdings" ? (
            <Holdings key={day} day={day} />
          ) : path === "/validation" ? (
            <Validation key={day} day={day} />
          ) : (
            <Market key={day} day={day} />
          ))}
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);

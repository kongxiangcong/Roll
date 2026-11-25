import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../../../", import.meta.url));
const base = path.join(root, ".scratch", "e2e");
mkdirSync(base, { recursive: true });
const data = mkdtempSync(path.join(base, "run-"));
writeFileSync(
  path.join(base, "current-" + (process.env.ROLL_E2E_PORT || "18091")),
  data,
);
const python =
  process.env.ROLL_TEST_PYTHON ||
  path.join(
    root,
    "backend",
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
const env = {
  ...process.env,
  PYTHONPATH: path.join(root, "backend", "src"),
  PYTHONUTF8: "1",
  ROLL_ENV: "test",
  ROLL_ENV_FILE: "",
  FUYAO_API_KEY: "",
};
if (process.env.ROLL_E2E_LIVE_ENV_FILE)
  env.ROLL_ENV_FILE = process.env.ROLL_E2E_LIVE_ENV_FILE;
if (env.ROLL_ENV_FILE) delete env.FUYAO_API_KEY;
const seed = spawnSync(
  python,
  [path.join(root, "frontend", "tests", "e2e", "seed.py"), data],
  { env, stdio: "inherit" },
);
if (seed.status !== 0) process.exit(seed.status || 1);
const server = spawn(
  python,
  [
    "-m",
    "roll.cli",
    "--data-dir",
    data,
    "serve",
    "--port",
    process.env.ROLL_E2E_PORT || "18091",
  ],
  { env, stdio: "inherit" },
);
for (const signal of ["SIGTERM", "SIGINT"])
  process.on(signal, () => server.kill());
server.on("exit", (code) => process.exit(code ?? 0));

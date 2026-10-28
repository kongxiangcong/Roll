# Workbench delivery — 2026-10-23

## Delivered
Integrate / redesign, governed by [spec.md](spec.md). Homepage only; existing research assistance is preserved and its presentation revised. No external visual reference or copied implementation.

- `frontend/src/pages/daily-use.tsx`: three task views, accessible keyboard tabs, retained mounted forms, factual account rail, focused actual-trade entry and mobile account shortcut.
- `frontend/src/styles/workbench.css`: scoped product-owned tokens, hierarchy, responsive layout, focus and reduced-motion rules.
- `frontend/src/components/assistance-panel.tsx`: existing untracked component retained; assessment before source details, readable reflection form, explicit loading/empty states, clearer action labels, preserve newer draft when an earlier save succeeds.
- `frontend/tests/e2e/daily-use.spec.ts`: reflect the new heading and task navigation; retain original actual buy/sell and account assertions.
- `frontend/scripts/workbench-check.mjs`: deterministic browser state board and interaction checks.
- `frontend/scripts/daily-use-live.mjs`: navigation selectors migrated; live script NOT_RUN.

APIs, source policies, accounting confirmation, run identities and formal qualification boundaries remain intact. No backend edits, paid model requests, dependency installation, commit or publication.

## Validation
| Check | Result | Evidence |
| --- | --- | --- |
| TypeScript + Vite production | PASS | `cd frontend; npm run build`; 105 modules, final JS 553.80 kB, gzip 163.51 kB |
| Production browser interactions | PASS | `WORKBENCH_URL=http://127.0.0.1:5191 node scripts/workbench-check.mjs`; Chrome 155.0.8059.85; zero page errors |
| Desktop / compact / narrow | PASS | 1440, 1024, 390, 320px; all three panels checked for page overflow; screenshots in evidence/ |
| Keyboard and drafts | PASS | ArrowRight/Home selection, ARIA panels, draft survives view switch and save failure |
| Primary research action | PASS (fixture) | First request fails, explicit retry returns running state, duplicate start disabled |
| Empty / running / failed | PASS (fixture) | evidence/empty.png, running.png, failed.png; reduced motion enabled |
| Actual buy/sell flow | PASS (isolated backend) | `ROLL_TEST_API_PORT=8027 ROLL_TEST_WEB_PORT=5190 ROLL_BROWSER_CHANNEL=chrome node node_modules/@playwright/test/cli.js test daily-use.spec.ts --config=playwright.config.ts`; 1 passed, 21.4s; cash 100290.00, two fills, capability UNGRANTED |
| Diff whitespace | PASS | `git diff --check` |
| Native IME / screen reader / browser zoom | NOT_RUN | No manual OS or assistive-technology session; text area submits only through explicit save button |
| Live model and market collection | NOT_RUN | UI fixtures and isolated account backend only; no paid or live-source execution |
| Offline standalone | NOT_APPLICABLE | Existing online product integration |

Production build emits a chunk-size warning (>500 kB); build succeeds. Browser fixtures are explicitly illustrative, not market evidence. Previous runtime checks here initially failed because local network required escalation, the old heading assertion no longer matched, and an incomplete fixture omitted the intents response; corrected runs above passed.

Before and after share fixture content and desktop viewport. Final screenshots: [desktop](evidence/after-desktop.png), [mobile](evidence/after-390.png), [320px](evidence/after-320.png). Full-page screenshots were visually inspected. Source/financial/news/review controls remain in their respective views; no claims about live data freshness or investment validity.

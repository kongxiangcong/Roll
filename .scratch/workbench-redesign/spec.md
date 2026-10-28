# Workbench redesign

Mode: Integrate
Visual policy: redesign
Selected specification: this file, 2026-10-23
Product root: D:/dsh-proj/Roll
Reference: none; editorial-ui workflow only.

## Product decision
The 日常使用 homepage becomes a research workbench for 江西铜业. Lead with the saved research assessment, then counterevidence and exploratory comparison. Separate task-oriented views: 研究判断, 事实与来源, 观察复盘. Keep account facts and actual-trade entry in a quiet supporting rail. No decorative KPI row. Research is not a formal Decision or an actual trade.

Replace the homepage's stacked bordered modules and equal action hierarchy with an editorial heading, task tabs, a broad reading surface and a compact account rail. Preserve other routes' visual policy. Numerical tokens and motion live only in frontend/src/styles/workbench.css; system fonts, green accent, warm paper surfaces, 150ms control color transitions, no content motion.

## Contracts and scope
Preserve API endpoints/payloads, polling, saved run identities, accounting preview/confirmation, source permissions, cancellation and failure semantics. Mounted tab panels retain form drafts and selected runs. Keep all existing homepage modules reachable. Do not install, commit, publish, change backend or run paid model tasks.
Required first: homepage structure and real AssistancePanel. Required final: all three views, account entry, narrow layouts, keyboard tabs, build and browser assertions. State board: fixture-backed product screenshots for populated, empty, running and failed states, not a separate mock application.

## Validation
Desktop 1440x1000, compact 1024x768, mobile 390x844 and 320x740, reduced motion, keyboard, long CJK and identifiers. Capture fixed fixture before/after; distinguish fixture interaction from live services. Run TypeScript/Vite build and isolated existing daily-use regression. Native IME and screen readers are not automated.

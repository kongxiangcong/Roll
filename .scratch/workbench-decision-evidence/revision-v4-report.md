# Targeted final corrections

- record() now resolves currentFixture().run_id. Overview and backtest summary, source binding and backtest detail read current fixture dataId/version/basisAsOf rather than a second v2 string. Removed premature initial render before fixture initialization.
- Scoring window has 84 synthetic records, separate 20-row warmup; total input 104. Scorable opportunities 84, no repeated warmup subtraction, zero company-action or other exclusions. Calendar count explicitly synthetic, not a claim about actual exchange sessions.
- Fee stress example is MOCK-COST-STRESS, explicitly not a formal project gate. Probability G3 remains independent.

verify-v4.cjs passes prior regression checks plus summary/source/detail identity, window-set accounting, and absence of formal G2 alias. Zero browser JS errors and HTTP requests. No Library upload. Independent UI policy limitation unchanged.

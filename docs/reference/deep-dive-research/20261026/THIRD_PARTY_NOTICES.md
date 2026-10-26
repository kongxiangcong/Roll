# Third-party notices

`scripts/fundamental_valuation.py` adapts the DCF, reverse DCF and EPV calculations from `equity-research-skill/scripts/dcf.py`, copyright (c) 2026 Sirius, MIT licensed. The full original license is included in [equity-research-LICENSE.txt](equity-research-LICENSE.txt).

Source snapshot inspected on 2026-10-23: local sibling checkout `trading-assistant/equity-research-skill`, file SHA-256 `70db16dd250b5a8ae68d6123b9a6d1a2deae33674da68cd15d2794126603f370`. Git metadata was not verified; the file hash identifies the actual code inspected, independent of branch state.

Adaptations: research-only structured output; explicit FCFF convention and fixed diluted shares; complete annual forecasts rather than implicit fade/dilution; finite input validation; N+1 reverse terminal revenue timing; normalized cash-flow EPV; reproducibility hashes and tests. No upstream investment labels or position sizing are included. No code from the other GitHub projects researched in this task is bundled or installed.

# Implementation coordination checkpoint

Updated 2026-10-27 (Asia/Shanghai). This file records checkout/coordination pointers; task Completion in issues/README.md remains authoritative.

- Integration branch: codex/roll-research-valuation.
- Integration checkout: D:/dsh-proj/Roll/.scratch/worktrees/rv-integration. Always use this explicit path for integration work. The original D:/dsh-proj/Roll checkout retains its existing uncommitted work.
- Pre-existing code/spec snapshot: ebe3fc88388767731e96504b36dcb5173082b392 (parent e47013f). It is baseline, not new feature delivery; baseline-paths.txt records copied paths.
- Local Markdown tracker, no PR requested. Strict ticket order 01 through 12. No dependency may be skipped; overall completion requires all 12 and A1-A10, including two actual post-close cycles.
- User confirmed TDD boundaries: public research service/API, calculator entry, browser flows, backup/recovery. No repeat confirmation needed for those boundaries.

## Completed merges

| Ticket | Integration merge | Evidence |
| --- | --- | --- |
| 01 | 13caf303195c5316000eb906911d86e7f67d6d02 | evidence/01/README.md; 27 frozen files, 94 gate sites |
| 02 | 41a5f318e43f422c3618ec5744d847bc09d69240 | evidence/02/README.md; 42 regression tests passed; actual issuer PDF archived/reopened/exported |
| 03 | f9991ae62c1095b1d1224344c5e11f58e92195e4 | evidence/03/README.md; 51 regression tests passed; two real CODEX attempts, first PARTIAL preserved, final COMPLETE with 3 hypotheses and parent version |
| 04 | c04b6ed824eceec577a1e87291491d48768dc63e | evidence/04/README.md; 72 tests and 5 subtests passed; diagnostic calculator, canonical archives, independent replay and recovery |

Ticket 05 is active on codex/rv-ticket05 at D:/dsh-proj/Roll/.scratch/worktrees/rv-ticket05, based on c04b6ed. Do not duplicate its edits. A separate research subagent owns source-research notes/evidence only; real public issuer PDFs are under D:/dsh-proj/Roll/.scratch/rv05-source-data. No positive economic-review result has yet been accepted. Ticket 06 onward has not started.

## Retained materials and worktrees

Actual sample stores are separate from implementation worktrees: D:/dsh-proj/Roll/.scratch/rv02-real-data and rv03-real-data. Keep them and their evidence receipts; no production/account store was modified. Unknown disclosure/historical receipt times remain unknown. These materials do not establish strict historical PIT, economic valuation review or formal strategy qualification.

Implementation worktrees rv-ticket01 through rv-ticket04 remain under .scratch/worktrees/ for eventual cleanup after their commits are retained in integration; rv-ticket03 has untracked disposable test basetemps/temp API copies. Do not add those temporary paths to commits. Preserve integration checkout. Later worktrees likewise use one branch per ticket, then a merger subagent integrates them.

Before final delivery: run the invoked two-axis code-review skill against the integration branch from the feature baseline, address findings, complete the real acceptance requirements honestly, and clean implementation worktrees. Never substitute synthetic clock cycles for actual post-close observations.


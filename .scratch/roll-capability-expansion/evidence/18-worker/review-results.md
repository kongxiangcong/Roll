# Ticket18 two-axis review

User fixed pointb4fb440; original implementation5e3fd5dd832f0f5fed130063a283d6ee7e094b1c, ticket diffc891d57...5e3fd5d. Parallel independent read-only code-review axes, same documented standards and smell baseline as16/17. Old dirty worker hunks excluded from the commit; only new two-line hook included.

## Standards

0 documented-standard violations. Initial1 judgment finding, possible Duplicated Code with concrete cancellation risk: success ending rechecked persisted status in BEGIN IMMEDIATE, error ending wrote old in-memory job and could overwrite an already saved CANCELLED/USER_CANCELLED. Resolved: error branch now BEGIN IMMEDIATE reads current status, preserves any non-RUNNING terminal receipt, honors paused configuration, and avoids treating ordinary cancellation/pause as source failure backoff. New deterministic public cancel→prepare failure regression proves exact cancellation remains after the handler runs. Final read-only delta review: risk eliminated, no new standard issue or blocker.

## Spec

Initial1 blocker: same fact/model inputs reused one immutable series even after the next consumer checkpoint arrived; a previously pending event could stay pending forever. Resolved by latest actually reached registered15:05 trading checkpoint in classified observation/series logical inputs. Same checkpoint remains cached; later checkpoints create successors while original source_available_through, old series and cached model classification stay unchanged. Semantic notice key stays unchanged. New Thu15:01 source/15:06 classification→Fri15:06 METHOD case shows old pending becomes consumed, no source re-age, old series unchanged, model invoked only once and station notice remains1. Final read-only delta review: blocker eliminated, no new wrong behavior; conditional pass once final tests/commit fixed.

Standards:1 initial judgment risk,1 resolved;0 remaining violations/blockers. Spec:1 initial blocker,1 resolved;0 remaining blockers. Final full new-observation suite10passed80.83s; runtime04 exact final code positive saved-source real process/lease/restart with0HTTP/0model calls. Build/Chrome unchanged UI checks remain valid. Actual first inference timeout and3 reproduced old notification baseline failures remain explicit. No grant, fresh real acquisition or inference success claimed.

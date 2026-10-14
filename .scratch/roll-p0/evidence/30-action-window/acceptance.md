# Offline protocol-bound action reference-window consumer

Ticket30 remains partial. This slice consumes saved public originals and immutable source assessments; it adds no source acquisition or authoritative event/lifecycle proof.

## Concrete delivered behavior

`POST /api/research/collections/{plan_id}/action-window-packets` creates an append-only `ACTION_WINDOW_SUCCESSOR` from an explicit saved `ACTION_SUCCESSOR`, registered protocol and saved known-obligation audit ID. The predecessor contains the fixed source receipt and assessment IDs. The command cannot supply cutoff, coverage, lifecycle, eligibility or forward-start flags.

The consumer validates both existing owners' original archives, registered design, known-time cutoff, calendar, preserved raw/mapping and original normalized facts. It reuses the saved obligation reference window, keeps record/dividend DATE precision, classifies reported dates against that window and consumer cutoff, and retains raw candidate pointers. A dividend date never becomes a payment date, effective instant or fulfilled obligation. No reported candidate is associated with any of the 14 notice identities by date, title or amount.

The new immutable packet includes the exact original daily packet ID/cutoff and its original rows with source/assessment IDs, reported candidates and the missing reported FH row count attached. Original quantities, units and completion remain unchanged. A PRICE_SUCCESSOR predecessor is unwrapped only to obtain its preserved daily reference; price quotes do not become model daily inputs.

`GET /action-window-packets/{id}` and the existing generic packet replay validate saved IDs and sources without reselecting later assessments. `GET /action-window-inputs?protocol_id=...` chooses the last saved successor for that registered protocol and current reference checkpoint date, ignores future-known packets, and carries explicit packet IDs, candidates and missing rows. It does not carry an earlier day's reference forward as current.

The actual read-only `ForwardArchive.rows` consumer uses this same saved protocol-window selection and enriches existing source rows; concrete missing-row and packet provenance enter refusal gaps. It calls no model and adds no sample. The new forward adapter fingerprint requires successors for existing plans rather than rewriting their frozen identities.

## Authority preserved

- Existing company-action collector, action assessment, price quote and daily packet modules/reference blobs are unchanged. Their saved packet schemas, IDs, original files and normalization fingerprints are preserved.
- The existing FH source still contains first 5 of reported 6 and the SG source is still an empty finite response with unknown scope. Scope/all-category/version/negative coverage remain unproved.
- Unit, authoritative event/version identity, publisher first availability, revision/cancellation, fulfillment/deferral, account entitlement and all older obligations remain UNKNOWN.
- Every new packet and consumer remains system_usable=false, model_daily_input_allowed=false, forward_admissible=false, forward_started_at=null and NOT_GRANTED, with zero account events and confirmatory checkpoints.
- No actual HTTP, provider/model request, fit, SEALED read, real account database access, qualification, notification or source expansion occurred. Public originals were consumed only through isolated METHOD source suppliers and owned SQLite/files.

## TDD and validation stages

| Stage | Recorded outcome |
|---|---|
| Public immutable successor | Genuine missing endpoint RED: 1 failed / 12.22s; GREEN 1 passed / 11.13s |
| Read-only forward provenance | Genuine missing row-count/provenance RED: 1 failed / 12.22s |
| Source cutoff/protocol/restart | Intermediate 2 passed / 1 harness expectation failure / 29.41s: existing predecessor Host-clock future cutoff correctly returned 422, test initially expected only409; expectation corrected to accept existing refusal semantics |
| Concrete original daily-row consumption | Genuine missing reference_rows RED: 1 failed / 12.44s |
| Corrected four-case combination | 4 passed / 40.08s |
| Fixed final affected source | 42 passed / 255.47s: all10 new cases, preserved action successor, full price quote suite, known-obligation read-only forward seam and pure forward features |
| Integration-tip composition | After merging integration policy/broker implementation into a1098e1: concrete row consumer, fixed IDs/restart and broker cost suite 6 passed / 44.66s; previous42 is not restated as a post-merge full suite |

Initial unprivileged venv discovery failed to resolve the configured host Python and was interrupted; it is not a product RED. One subsequent automatic permission review timed out, its permitted retry succeeded; this was not a safety rejection.

`git diff --exit-code f463dcb` against company-action collector/assessment, price quotes, daily post-close module and the complete `market/reference/` tree passed; `git diff --check` is clean. All seven newly owned METHOD runtime directories were moved only after test completion to the fresh ignored `.roll-data/implementation-evidence/ticket30-action-window-20261014/` target. The exact source/destination file manifests and pre/post SHA256-length comparisons are in `runtime-preservation-receipt.json`: 2558 files, zero differences. SQLite files were byte-hashed only during preservation, never reopened. No old preservation target was read or overwritten. The worktree is retained for independent acceptance.

The separate post-merge composition directory is preserved under the same fresh target with its own `composition-preservation-receipt.json`; the earlier manifest remains unchanged. Frozen source/reference diff checks passed again after integration merge.

The remaining complete-current action inventory/lifecycle, nonempty SG schema, full effective risk/listing/resume/status and daily session/completion/unit semantics require authoritative source evidence unavailable in these saved originals. This implementation does not close Ticket30 first acceptance condition or start Tickets32/33 real clocks.

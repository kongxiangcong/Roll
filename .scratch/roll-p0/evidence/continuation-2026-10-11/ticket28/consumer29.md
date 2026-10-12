# 29 notification consumer

Read-only report query: `GET /api/notifications/time-chain?decision_id=<registered decision>&evaluation_id=<registered evaluation>&intent_id=<optional persisted26 intent>`. Pair mismatch refuses409; unknown decision refuses404. The query reads registered state, does not check/advance, and never rewrites intent or allocation facts.

`time_chain` copies the latest persisted26 user-declaration chain, preserving decision-issued/prepared/occurred/reported/known timestamps and their sources. `notification_timeline` separately exposes immutable attempts/results and source associations; report these as evidence, without assigning user action to a transmission.

| Field | Meaning / limit |
|---|---|
| `sent_at`, `sent_source` | null/UNKNOWN; local attempt start is not socket-write proof |
| `dispatch_started_at` | local committed HOST_ATTEMPT_STARTED event; not sent/accepted/delivered |
| `publish_confirmed_at`, `accepted_known_at` | host receipt knowledge of a valid ntfy acceptance event/id |
| `accepted_occurred_at` | optional provider-reported integer time, explicitly NTFY_REPORTED_TIME_UNVERIFIED_CLOCK; no invented clock authority |
| `delivered_at`, `delivery_source` | null/UNKNOWN; ntfy publisher response does not prove terminal delivery |
| `read_at`, `read_source` | explicit station-read only; external read remains unknown. A read of the original merged message does not establish a later decision was read (`OLDER_MESSAGE_ONLY`, null) |
| `original_source_binding`, `source_links` | distinguishes original immutable message from later semantic merge associations; never equate different decision/evaluation IDs |
| `attempts[].source`, `.body`, `.message_projection` | exact pre-claim chosen source and body. Over4096UTF8 original station text uses an explicitly registered short current-link body; station message is preserved |
| `attempts[].events/result` | append-only local start/outcome/recovery and sanitized acceptance/rejection/unknown; old attempt cannot be overwritten by retry |

`GET /api/notifications/audit` reports actual business notifications, transmission attempts, merged source associations, failed/unknown attempts and possible duplicate retry attempts separately. It does not infer delivered message count. RUN02 `metrics.duplicate_notifications` is connected to this committed evidence; its value is merge count, with the separate counts preserved. The external real acceptance axis is PENDING_USER_CONFIGURATION; fixed Mock and local loopback OS proof remain METHOD.

`GET /api/notifications/{id}/current` explains CURRENT/EXPIRED/SUPERSEDED/INVALIDATED/RESOLVED while preserving original notification. `prepare_allowed=false`: old links cannot prepare intents. The dedicated report time-chain query does not perform this current-check side effect. Facts/pending external operations survive suspension; unresolved restore state is its own reminder, not recovered qualification. Authentication/configuration contents are never report material.

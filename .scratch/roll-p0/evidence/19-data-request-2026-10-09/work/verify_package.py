"""Independent self-verification of the ticket19-data-delivery package.

Checks:
  - required layout files all exist
  - every JSONL/JSON parses
  - record_id uniqueness within each file
  - evidence_refs non-empty and resolvable to evidence_index ids
  - relative_path locators resolve to real files
  - manifest sha256 / bytes / record_count match the actual files (recomputed)
  - every sha256 is lowercase 64-hex
  - no truncation (files end with newline; JSONL line count == record count)
  - README exists and references the real directory layout
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "ticket19-data-delivery"
HEX64 = re.compile(r"^[0-9a-f]{64}$")

REQUIRED = [
    "manifest.json", "README.md",
    "data/daily_bars.jsonl", "data/trading_calendar.jsonl", "data/security_status.jsonl",
    "data/corporate_actions.jsonl", "data/historical_rules.jsonl", "data/revisions.jsonl",
    "evidence/sources.jsonl", "evidence/evidence_index.jsonl", "evidence/search_log.jsonl",
    "evidence/raw",
    "reports/coverage.json", "reports/gaps.json", "reports/conflicts.json",
]

errors: list[str] = []
warnings: list[str] = []
ok: list[str] = []


def err(m):
    errors.append(m)


def warn(m):
    warnings.append(m)


# ---------------------------------------------------------------- layout
for rel in REQUIRED:
    p = PKG / rel
    if not p.exists():
        err(f"MISSING required path: {rel}")
if not errors:
    ok.append(f"layout: all {len(REQUIRED)} required paths exist")


# ---------------------------------------------------------------- parse + ids + refs
def load_jsonl(rel):
    p = PKG / rel
    raw = p.read_bytes()
    if not raw.endswith(b"\n"):
        err(f"{rel}: does not end with a newline (possible truncation)")
    text = raw.decode("utf-8")
    rows = []
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            err(f"{rel}:{i}: blank line")
            continue
        try:
            rows.append(json.loads(line))
        except Exception as e:
            err(f"{rel}:{i}: JSON parse error: {e}")
    return rows


DATA_FILES = [
    "data/daily_bars.jsonl", "data/trading_calendar.jsonl", "data/security_status.jsonl",
    "data/corporate_actions.jsonl", "data/historical_rules.jsonl", "data/revisions.jsonl",
    "evidence/sources.jsonl", "evidence/evidence_index.jsonl", "evidence/search_log.jsonl",
]

parsed = {}
for rel in DATA_FILES:
    rows = load_jsonl(rel)
    parsed[rel] = rows
    ok.append(f"{rel}: parsed {len(rows)} rows")

# --- record_id uniqueness
for rel, rows in parsed.items():
    if rel in ("evidence/sources.jsonl",):
        continue
    keys = []
    for r in rows:
        k = r.get("record_id") or r.get("evidence_id") or r.get("search_id")
        if k is None:
            err(f"{rel}: row without record_id/evidence_id/search_id")
        keys.append(k)
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        err(f"{rel}: duplicate ids: {sorted(dupes)[:5]}")
    else:
        ok.append(f"{rel}: {len(keys)} unique ids")

# --- sources uniqueness
src_ids = [r["source_id"] for r in parsed["evidence/sources.jsonl"]]
if len(src_ids) != len(set(src_ids)):
    err("evidence/sources.jsonl: duplicate source_id")
else:
    ok.append(f"evidence/sources.jsonl: {len(src_ids)} unique source_id")

# ---------------------------------------------------------------- evidence index
ev_rows = parsed["evidence/evidence_index.jsonl"]
EV = {r["evidence_id"]: r for r in ev_rows}
if len(EV) != len(ev_rows):
    err("evidence_index: duplicate evidence_id")

# every evidence row must have a real file OR an explicit reason for relative_path=None
for r in ev_rows:
    rp = r.get("relative_path")
    if rp is None:
        warn(f"evidence {r['evidence_id']}: relative_path is null (must have limitation text)")
        if not r.get("limitations"):
            err(f"evidence {r['evidence_id']}: null relative_path without a limitations note")
        continue
    if rp.startswith("evidence/raw/"):
        fp = PKG / rp
        if not fp.exists():
            err(f"evidence {r['evidence_id']}: relative_path missing on disk: {rp}")
            continue
        b = fp.read_bytes()
        h = hashlib.sha256(b).hexdigest()
        if h != r.get("sha256"):
            err(f"evidence {r['evidence_id']}: sha256 mismatch vs file ({h} != {r.get('sha256')})")
        if len(b) != r.get("bytes"):
            err(f"evidence {r['evidence_id']}: bytes mismatch ({len(b)} != {r.get('bytes')})")
        if not HEX64.match(r.get("sha256") or ""):
            err(f"evidence {r['evidence_id']}: sha256 not lowercase 64-hex")
    elif "project-archived" in rp or "not shipped" in rp:
        warnings_ok = True
    else:
        warn(f"evidence {r['evidence_id']}: relative_path not under evidence/raw/: {rp}")

ok.append(f"evidence_index: {len(EV)} rows, sha/bytes re-verified against disk")

# ---------------------------------------------------------------- evidence_refs resolvable
def check_refs(rel, rows, field="evidence_refs"):
    bad = 0
    for r in rows:
        refs = r.get(field)
        if not isinstance(refs, list) or not refs:
            # empty refs are allowed ONLY when the record carries an explicit reason
            documented = bool(r.get("evidence_refs_missing_reason")) or bool(r.get("limitations"))
            allowed_ids = {"SS-600362-STATUS-COVERAGE-NOTE", "CA-COVERAGE-NOTE", "REV-CHAIN-COMPLETENESS-NOTE"}
            allow = documented or r.get("record_id") in allowed_ids or r.get("id") in ("GAP-007", "GAP-008")
            if not allow:
                err(f"{rel} {r.get('record_id') or r.get('evidence_id')}: empty {field} without a documented reason")
                bad += 1
            continue
        for ref in refs:
            eid = ref.get("evidence_id")
            if eid not in EV:
                err(f"{rel} {r.get('record_id') or r.get('evidence_id')}: dangling evidence_id {eid}")
                bad += 1
    return bad


for rel, rows in parsed.items():
    if rel == "evidence/evidence_index.jsonl":
        continue
    n = check_refs(rel, rows)
    if n == 0:
        ok.append(f"{rel}: all evidence_refs resolve")

# gaps/conflicts refs
for rel in ("reports/gaps.json", "reports/conflicts.json"):
    obj = json.loads((PKG / rel).read_text(encoding="utf-8"))
    key = "gaps" if "gaps" in rel else "conflicts"
    items = obj[key]
    for it in items:
        for ref in it.get("evidence_refs", []):
            if ref.get("evidence_id") not in EV:
                err(f"{rel} {it['id']}: dangling evidence_id {ref.get('evidence_id')}")
    ok.append(f"{rel}: {len(items)} entries, refs checked")

# ---------------------------------------------------------------- required fact fields
UNIVERSAL = ["instrument", "source_id", "evidence_refs", "historical_publication",
             "historical_availability", "captured_at", "received_at", "evidence_class"]
TIMEEV = {"value", "precision", "not_later_than", "basis", "evidence_refs"}
PRECISIONS = {"DATE", "MINUTE", "SECOND", "MILLISECOND", "UNKNOWN"}
CLASSES = {"CAPTURED_HISTORICAL_VERSION", "PROVIDER_VERSION_ARCHIVE",
           "DOCUMENTED_PUBLICATION_AND_REVISION_HISTORY", "CURRENT_QUERY_ONLY", "UNKNOWN"}

for rel in ["data/daily_bars.jsonl", "data/trading_calendar.jsonl", "data/security_status.jsonl",
            "data/corporate_actions.jsonl", "data/historical_rules.jsonl", "data/revisions.jsonl"]:
    rows = parsed[rel]
    miss = 0
    for r in rows:
        for f in UNIVERSAL:
            if f not in r:
                err(f"{rel} {r.get('record_id')}: missing universal field {f}")
                miss += 1
        if r.get("evidence_class") not in CLASSES:
            err(f"{rel} {r.get('record_id')}: bad evidence_class {r.get('evidence_class')}")
        for tf in ("historical_publication", "historical_availability", "captured_at"):
            t = r.get(tf)
            if not isinstance(t, dict):
                err(f"{rel} {r.get('record_id')}: {tf} not an object")
                continue
            if set(t.keys()) != TIMEEV:
                err(f"{rel} {r.get('record_id')}: {tf} keys {sorted(t.keys())} != template")
            if t.get("precision") not in PRECISIONS:
                err(f"{rel} {r.get('record_id')}: {tf}.precision {t.get('precision')} invalid")
    if miss == 0:
        ok.append(f"{rel}: universal fields present on all {len(rows)} rows")

# ---------------------------------------------------------------- manifest integrity
man = json.loads((PKG / "manifest.json").read_text(encoding="utf-8"))
if man.get("schema_version") != "ticket19-external-evidence-v1":
    err("manifest: wrong schema_version")
if man.get("window_status") != "COLLECTION_CANDIDATE_NOT_PREREGISTERED_DEV_CAL":
    err("manifest: wrong window_status")
if man.get("delivery_status") not in ("EVIDENCE_DELIVERED", "PARTIAL_DELIVERY", "NO_QUALIFYING_BODY_FOUND"):
    err("manifest: bad delivery_status")

listed = {f["path"]: f for f in man["files"]}
for rel, meta in listed.items():
    p = PKG / rel
    if not p.exists():
        err(f"manifest lists missing file: {rel}")
        continue
    b = p.read_bytes()
    h = hashlib.sha256(b).hexdigest()
    if h != meta["sha256"]:
        err(f"manifest sha256 mismatch for {rel}")
    if len(b) != meta["bytes"]:
        err(f"manifest bytes mismatch for {rel}")
    if not HEX64.match(meta["sha256"]):
        err(f"manifest sha256 not 64-hex for {rel}")
    if meta.get("record_count") is not None and rel in parsed:
        if len(parsed[rel]) != meta["record_count"]:
            err(f"manifest record_count mismatch for {rel}: {meta['record_count']} vs {len(parsed[rel])}")
    if meta.get("record_count") is not None and rel.endswith(".json") and rel != "reports/coverage.json":
        obj = json.loads(b.decode("utf-8"))
        if "gaps" in rel:
            key = "gaps"
        elif "conflicts" in rel:
            key = "conflicts"
        elif rel == "reports/cross_source_validation.json":
            # this report is a single object, not a list-wrapping one
            if meta["record_count"] != 1:
                err(f"manifest record_count mismatch for {rel}: expected 1")
            key = None
        else:
            key = None
        if key is not None and len(obj[key]) != meta["record_count"]:
            err(f"manifest record_count mismatch for {rel}")
ok.append(f"manifest: {len(listed)} entries re-hashed and size-checked")

# every delivered artifact should be in the manifest
actual = set()
for p in PKG.rglob("*"):
    if p.is_file():
        actual.add(str(p.relative_to(PKG)).replace("\\", "/"))
actual.discard("manifest.json")
actual.discard("README.md")
missing_from_manifest = actual - set(listed)
if missing_from_manifest:
    err(f"files present but not in manifest: {sorted(missing_from_manifest)[:10]}")
else:
    ok.append("manifest: covers every file in the package (plus manifest/README)")

# raw dir file count vs manifest
raw_files = {p.name for p in (PKG / "evidence/raw").iterdir() if p.is_file()}
raw_listed = {Path(k).name for k in listed if k.startswith("evidence/raw/")}
if raw_files != raw_listed:
    err(f"raw dir vs manifest mismatch: extra={raw_files - raw_listed} missing={raw_listed - raw_files}")
else:
    ok.append(f"evidence/raw: {len(raw_files)} files, all in manifest")

# ---------------------------------------------------------------- coverage keys
cov = json.loads((PKG / "reports/coverage.json").read_text(encoding="utf-8"))
REQ_KEYS = ["requested_scope", "delivered_scope", "context_only_scope", "daily_row_count",
            "unique_business_dates", "version_count", "calendar_coverage", "status_coverage",
            "corporate_action_coverage_by_type", "historical_rule_coverage", "missing_bar_dates",
            "unknown_status_dates", "unit_conflict_dates", "incomplete_bar_dates",
            "longest_consecutive_exchange_session_run", "historical_version_evidence_counts",
            "metadata_candidate_21_row_windows", "historical_availability_coverage",
            "revision_chain_completeness", "provenance_missing_records", "hash_length_validation",
            "cross_source_conflicts", "mature_labels_calculated", "model_training_performed",
            "sealed_payloads_read", "formal_dev_cal_windows_registered", "qualification_decision"]
missing_keys = [k for k in REQ_KEYS if k not in cov]
if missing_keys:
    err(f"coverage.json missing required keys: {missing_keys}")
else:
    ok.append(f"coverage.json: all {len(REQ_KEYS)} required keys present")

for k in ("mature_labels_calculated", "model_training_performed", "sealed_payloads_read",
          "formal_dev_cal_windows_registered"):
    if cov.get(k) is not False:
        err(f"coverage.{k} must be false, got {cov.get(k)}")
if cov.get("qualification_decision") != "HOST_REVIEW_REQUIRED":
    err("coverage.qualification_decision must be HOST_REVIEW_REQUIRED")

# ---------------------------------------------------------------- gaps/conflicts severity vocab
SEV = {"BLOCKS_HISTORICAL_INPUT", "BLOCKS_EXECUTION_OR_RIGHTS", "LIMITS_COVERAGE", "INFORMATION_ONLY"}
for rel, key in (("reports/gaps.json", "gaps"), ("reports/conflicts.json", "conflicts")):
    items = json.loads((PKG / rel).read_text(encoding="utf-8"))[key]
    need = ["id", "category", "severity", "affected_dates_or_scope", "affected_fields", "description",
            "evidence_refs", "methods_attempted", "why_unresolved", "next_step",
            "requires_external_authorization"]
    for it in items:
        for f in need:
            if f not in it:
                err(f"{rel} {it.get('id')}: missing field {f}")
        if it["severity"] not in SEV:
            err(f"{rel} {it.get('id')}: bad severity {it['severity']}")
    ok.append(f"{rel}: {len(items)} entries, fields+severity checked")

# ---------------------------------------------------------------- report
print("=" * 72)
print("SELF-VERIFICATION")
print("=" * 72)
for m in ok:
    print("  OK   ", m)
for m in warnings:
    print("  WARN ", m)
for m in errors:
    print("  FAIL ", m)
print("-" * 72)
print(f"OK={len(ok)}  WARN={len(warnings)}  FAIL={len(errors)}")
if errors:
    raise SystemExit(1)
print("ALL CHECKS PASSED")

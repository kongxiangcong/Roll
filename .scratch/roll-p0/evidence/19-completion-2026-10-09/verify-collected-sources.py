"""Hash only explicitly public collection references; emit compact review metadata.

Run with backend/.venv/Scripts/python.exe -B -X utf8 <this file>.
No network, runtime database, SEALED, model, label, budget, or ticket access.
Existing source manifests and receipts are read as original bytes, never rewritten.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parent
REPO = BASE.parents[3]
PUBLIC = BASE / ".roll-data"
COLLECTIONS = BASE / "collections"
OLD_PUBLIC = REPO / ".scratch/roll-p0/evidence/continuation-2026-10-09/.roll-data"
ALLOWED = [PUBLIC] + [OLD_PUBLIC / name for name in (
    "official-disclosures-v6", "gap-research-v1", "gap-research-v2-2022",
    "gap-research-v3-2025",
)]
DROP_TEXT = {"text", "page_text", "extracted_text", "article_text", "full_text", "decoded_html"}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def digest(path):
    h, count = hashlib.sha256(), 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            h.update(chunk)
            count += len(chunk)
    return h.hexdigest(), count


def approved(path):
    return any(path.is_relative_to(root.resolve()) for root in ALLOWED)


def resolve_source(value, metadata):
    p = Path(value)
    choices = [p] if p.is_absolute() else [metadata.parent / p, REPO / p]
    for candidate in choices:
        absolute = candidate.resolve()
        if approved(absolute) and absolute.is_file():
            return absolute
    raise ValueError("Missing reference or path outside explicitly public collection roots")


def compact(value, key=""):
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            if k in DROP_TEXT:
                result[k + "_omitted"] = "Full extraction retained only in ignored public collection"
            elif k == "headers" and isinstance(v, dict):
                result[k] = {h: x for h, x in v.items() if h.lower() in (
                    "content-type", "content-length", "content-location", "location",
                    "memento-datetime", "link", "date",
                ) or h.lower().startswith("x-archive-")}
            else:
                result[k] = compact(v, k)
        return result
    if isinstance(value, list):
        return [compact(v, key) for v in value]
    return value


def records(value, pointer=""):
    if isinstance(value, dict):
        if "path" in value and "sha256" in value:
            yield pointer, value
        for key, child in value.items():
            yield from records(child, pointer + "/" + str(key).replace("~", "~0").replace("/", "~1"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from records(child, pointer + "/" + str(index))


def classify(record, pointer, metadata, path):
    status = record.get("http_status", record.get("status_code"))
    url = record.get("url", record.get("requested_url", ""))
    original = record.get("original_url", url)
    host = urlparse(original).hostname or ""
    if status is not None and status != 200:
        return "NON_200_FAILURE_OR_REDIRECT_RESPONSE"
    if "cdx/search/cdx" in url or record.get("kind") == "INDEX" or record.get("is_index_only"):
        return "ARCHIVE_INDEX_JSON_NOT_ORIGINAL_BODY"
    if "hisAnnouncement/query" in url or "/queries/" in pointer:
        return "DISCLOSURE_SEARCH_INDEX_JSON_NOT_ORIGINAL_BODY"
    if host.endswith(("cninfo.com.cn", "jxcc.com")) and path.suffix.lower() == ".pdf":
        return "ISSUER_DISCLOSURE_PDF_HTTP_STATUS_RECORDED" if status == 200 else "REUSED_ISSUER_DISCLOSURE_PDF_HTTP_STATUS_UNKNOWN"
    if "rules" in metadata.name or "fee2022-archive" in str(metadata):
        if host.endswith(("sse.com.cn", "mof.gov.cn", "chinaclear.cn")):
            return "OFFICIAL_POLICY_BODY_HTTP200" if status == 200 else "OFFICIAL_POLICY_BODY_HTTP_STATUS_UNKNOWN"
    if "fee2022-followup" in str(metadata):
        return "NEWS_POLICY_LOCATOR_HTTP200_NOT_OFFICIAL_NOTICE"
    if "COMMON_SSE_CP_GPJCTPZ" in url:
        return "CURRENT_OFFICIAL_QUOTE_QUERY_JSON_NOT_HISTORICAL_VINTAGE"
    if "TFPXX" in url:
        return "CURRENT_OFFICIAL_STATUS_QUERY_JSON_NOT_COMPLETE_STATE"
    if "pit-status-public" in str(metadata):
        return "PUBLIC_SITE_OR_JS_DISCOVERY_HTTP200_NOT_POLICY_OR_QUOTE_ORIGINAL"
    if "node_" in url:
        return "NEWSPAPER_NAVIGATION_INDEX_HTML"
    if "dated-paper-sample" in str(metadata) or "pit-newspaper-fields" in str(metadata):
        return "NEWSPAPER_PUBLIC_BODY_NOT_COMPLETE_PRICE_SERIES"
    if "captures" in pointer and any(x in original for x in ("sina", "sohu")):
        return "ARCHIVED_QUOTE_BODY_UNQUALIFIED_FOR_TRAINING"
    if "sina-kline-discovery" in metadata.name:
        return "QUOTE_SITE_OR_JS_DISCOVERY_HTTP200_NOT_HISTORICAL_PRICE_ORIGINAL"
    return "PUBLIC_RESPONSE_UNCLASSIFIED_NO_AUTHORITY_UPGRADE"


def structure(path):
    # Transport/format inspection, not an issuer or point-in-time qualification.
    with path.open("rb") as stream:
        head = stream.read(512)
    stripped = head.lstrip()
    if stripped.startswith(b"%PDF-"):
        return "PDF_HEADER_PRESENT"
    if stripped.startswith((b"[", b"{")):
        try:
            json.loads(path.read_bytes())
            return "JSON_PARSE_VALID_METADATA_OR_RESPONSE"
        except (ValueError, UnicodeError):
            return "JSON_LIKE_NOT_PARSE_VALID"
    if b"<html" in head.lower() or b"<!doctype" in head.lower():
        return "HTML_HEADER_PRESENT_CONTENT_AUTHORITY_NOT_INFERRED"
    return "OTHER_RESPONSE_BYTES"


def main():
    COLLECTIONS.mkdir(exist_ok=True)
    # Only collection metadata patterns are enumerated. No broad repository scan.
    inputs = sorted(set(PUBLIC.rglob("*manifest*.json")) |
                    set(PUBLIC.rglob("*inventory*.json")) |
                    set(PUBLIC.rglob("*assessment*.json")) |
                    set(BASE.glob("*receipts.json")))
    source_refs, metadata_refs, skipped = [], [], []
    verified_paths = {}
    for metadata in inputs:
        raw = metadata.read_bytes()
        document = json.loads(raw.decode("utf-8-sig"))
        relative = metadata.relative_to(BASE).as_posix()
        name = relative.replace("/", "--")
        if name.startswith(".roll-data--"):
            name = name[len(".roll-data--"):]
        snapshot = COLLECTIONS / name
        write_json(snapshot, {
            "snapshot_kind": "COMPACT_PUBLIC_COLLECTION_METADATA_NOT_ORIGINAL_DOCUMENT",
            "source_metadata_path": str(metadata),
            "source_metadata_sha256": hashlib.sha256(raw).hexdigest(),
            "source_metadata_bytes": len(raw),
            "source_metadata_received_clock": "Not substituted for SOURCE received_at",
            "collection": compact(document),
        })
        metadata_refs.append({"path": str(metadata), "sha256": hashlib.sha256(raw).hexdigest(),
                              "bytes": len(raw), "compact_snapshot": str(snapshot),
                              "existing_bytes_unchanged": metadata.read_bytes() == raw})
        for pointer, record in records(document):
            if "bytes" not in record:
                skipped.append({"metadata": relative, "pointer": pointer,
                                "path": record["path"], "sha256": record["sha256"],
                                "reason": "NO_DECLARED_BYTES; excluded from path+sha256+bytes verification totals"})
                continue
            reference = {"metadata": relative, "pointer": pointer,
                         "path": record["path"], "declared_sha256": record["sha256"],
                         "declared_bytes": record["bytes"],
                         "source_received_at": record.get("received_at"),
                         "http_status": record.get("http_status", record.get("status_code")),
                         "url": record.get("url", record.get("requested_url")),
                         "original_url": record.get("original_url"),
                         "publication_date": record.get("publication_date"),
                         "effective_date": record.get("effective_date"),
                         "capture_time_utc": record.get("capture_time_utc")}
            try:
                path = resolve_source(record["path"], metadata)
                # Re-read bytes for every reference, even when referenced by receipt and manifest.
                actual_sha, actual_bytes = digest(path)
                reference.update({"resolved_path": str(path), "actual_sha256": actual_sha,
                                  "actual_bytes": actual_bytes,
                                  "sha256_matches": actual_sha == record["sha256"],
                                  "bytes_match": actual_bytes == record["bytes"],
                                  "category": classify(record, pointer, metadata, path),
                                  "structure": structure(path)})
                verified_paths[str(path)] = (actual_sha, actual_bytes)
            except (OSError, ValueError) as exc:
                reference.update({"error": str(exc), "category": "REFERENCE_NOT_VERIFIED",
                                  "sha256_matches": False, "bytes_match": False})
            source_refs.append(reference)
    unique = {r["actual_sha256"]: r["actual_bytes"] for r in source_refs if "actual_sha256" in r}
    category_stats = {}
    for category in sorted({r["category"] for r in source_refs}):
        group = [r for r in source_refs if r["category"] == category]
        shas = {r["actual_sha256"]: r["actual_bytes"] for r in group if "actual_sha256" in r}
        category_stats[category] = {"reference_count": len(group), "unique_sha256": len(shas),
                                    "unique_bytes": sum(shas.values())}
    differences = [r for r in source_refs if not r["sha256_matches"] or not r["bytes_match"]]
    result = {
        "schema": "PUBLIC_SOURCE_REFERENCE_VERIFICATION_V1",
        "verification_at": datetime.now(timezone.utc).isoformat(),
        "verification_clock_is_not_source_received_clock": True,
        "scope": "Explicit public collection manifests, inventory, assessment and existing receipts only",
        "summary": {"metadata_file_count": len(inputs), "source_reference_count": len(source_refs),
                    "unique_verified_paths": len(verified_paths), "unique_sha256": len(unique),
                    "unique_bytes": sum(unique.values()), "difference_count": len(differences),
                    "missing_declared_bytes_reference_count": len(skipped),
                    "http_status_reference_counts": dict(Counter(str(r["http_status"]) for r in source_refs)),
                    "all_metadata_original_bytes_unchanged": all(r["existing_bytes_unchanged"] for r in metadata_refs)},
        "categories": category_stats,
        "boundaries": {"actual_training_performed": False, "full_PIT_proven": False,
                       "complete_daily_status_and_rights_proven": False,
                       "independent_calibration_or_model_freeze_proven": False,
                       "runtime_database_read": False, "SEALED_read": False,
                       "labels_or_models_or_budget_modified": False,
                       "http200_is_not_semantic_validity_or_original_authority": True,
                       "index_json_404_and_redirects_are_not_official_originals": True,
                       "raw_pdf_and_response_bytes_copied_to_collections": False},
        "metadata_files": metadata_refs, "references": source_refs,
        "excluded_incomplete_references": skipped, "differences": differences,
        "deduplication": "Unique bytes sum once per actual SHA256; per-category totals may overlap and must not be added",
        "format": "New snapshots and result: UTF-8 without BOM, LF; existing receipt bytes preserved",
    }
    write_json(BASE / "source-verification.json", result)
    print(json.dumps(result["summary"], ensure_ascii=False))
    if differences:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""Bounded HTTP acquisition helper using curl as transport.

The local MITM proxy breaks Python httpx for some hosts (web.archive.org -> 502),
while curl succeeds. This helper shells out to curl, preserves exact response
bytes, records headers, and returns a receipt. It performs NO parsing decisions
that could hide failures: the caller decides.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

CURL = "curl"


def fetch(url: str, headers: dict[str, str] | None = None, timeout: int = 45,
          max_bytes: int = 64 * 1024 * 1024, follow: bool = False) -> dict:
    """Fetch url with curl. Returns receipt dict with exact bytes + metadata."""
    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    if headers:
        hdrs.update(headers)
    with tempfile.TemporaryDirectory() as td:
        body_path = Path(td) / "body.bin"
        hdr_path = Path(td) / "hdr.txt"
        cmd = [CURL, "-sS", "--max-time", str(timeout),
               "--max-filesize", str(max_bytes),
               "-D", str(hdr_path), "-o", str(body_path)]
        if follow:
            cmd += ["-L", "--max-redirs", "3"]
        else:
            cmd += ["--max-redirs", "0"]
        for k, v in hdrs.items():
            cmd += ["-H", f"{k}: {v}"]
        cmd.append(url)
        requested_at = datetime.now(timezone.utc).isoformat()
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
        body = body_path.read_bytes() if body_path.exists() else b""
        raw_headers = hdr_path.read_bytes() if hdr_path.exists() else b""
    received_at = datetime.now(timezone.utc).isoformat()
    status = None
    header_map: dict[str, str] = {}
    for line in raw_headers.decode("latin-1", "replace").splitlines():
        if line.startswith("HTTP/"):
            try:
                status = int(line.split()[1])
            except Exception:
                pass
        elif ":" in line:
            k, _, v = line.partition(":")
            header_map[k.strip().lower()] = v.strip()
    # curl exit 0 but empty body with 4xx still records the failure body
    return {
        "url": url,
        "requested_at": requested_at,
        "received_at": received_at,
        "curl_exit": proc.returncode,
        "curl_stderr": proc.stderr.strip()[:500] if proc.stderr else "",
        "http_status": status,
        "headers": header_map,
        "body": body,
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
    }

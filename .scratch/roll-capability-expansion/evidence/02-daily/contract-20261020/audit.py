"""Read-only continuation audit; never read labels or allocate research budgets."""
import hashlib
import json
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

repo = Path(__file__).resolve().parents[5]
out = Path(__file__).resolve().parent
feature = repo / ".scratch/roll-capability-expansion"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


issues = {}
for path in sorted((feature / "issues").glob("*.md")):
    content = path.read_text(encoding="utf-8-sig")
    completion = re.search(r"\*\*Completion:\*\*\s*(\w+)", content).group(1)
    dependency_line = next(line for line in content.splitlines() if "**Blocked by:**" in line)
    dependencies = re.findall(r"\]\((\d\d)-", dependency_line)
    issues[path.name[:2]] = {
        "path": path.relative_to(repo).as_posix(),
        "completion": completion,
        "sha256": sha(path),
        "dependencies": dependencies,
    }
for issue in issues.values():
    issue["unmet_dependencies"] = [
        number for number in issue["dependencies"] if issues[number]["completion"] != "complete"
    ]

references = []
for name in ("authority-20261020", "daily-session-20261020"):
    directory = repo / "backend/src/roll/market/reference" / name
    manifest = directory / "sources.json"
    catalog = json.loads(manifest.read_bytes())
    for role, item in catalog["sources"].items():
        path = directory / item["path"]
        references.append({
            "catalog": name, "role": role, "sha256": sha(path),
            "hash_matches": sha(path) == item["sha256"],
            "length_matches": path.stat().st_size == item["bytes"],
            "source_status": item.get("status"),
            "source_error": item.get("error"),
        })

metadata = []
for relative in (".roll-data/pit/roll.sqlite3", ".scratch/r22-real03/roll.sqlite3"):
    path = repo / relative
    if not path.exists():
        metadata.append({"path": relative, "exists": False})
        continue
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as connection:
        connection.execute("PRAGMA query_only=ON")
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {
            name: connection.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
            for name in ("research_protocols", "research_attempts")
            if name in tables
        }
    metadata.append({"path": relative, "exists": True, "counts": counts,
                     "access": "READ_ONLY_COUNTS_NO_LABELS_NO_ATTEMPT_CONTENT"})

result = {
    "at": datetime.now(timezone.utc).isoformat(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
    "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=repo, text=True).strip(),
    "tickets": issues,
    "counts": {state: sum(i["completion"] == state for i in issues.values())
               for state in ("complete", "partial", "pending")},
    "reference_integrity": references,
    "reference_integrity_passed": all(r["hash_matches"] and r["length_matches"] for r in references),
    "research_metadata": metadata,
    "scope": "Only named stores checked; no assertion about other deployments or external artifacts.",
    "market_calls": 0, "fits": 0, "sealed_reads": 0, "funds_mutations": 0,
}
(out / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: result[key] for key in ("head", "branch", "counts", "reference_integrity_passed", "research_metadata")}, indent=2))

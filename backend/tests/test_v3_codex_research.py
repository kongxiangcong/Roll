import json
from pathlib import Path

from test_v3_research_tasks import material_file, snapshot, start, task_cli


def test_missing_codex_records_replayable_configuration_error(tmp_path, snapshot, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "no-binaries"))
    path = material_file(tmp_path, "季报", excerpt="经营现金流增加")
    receipt = start(tmp_path, snapshot, "--executor", "codex", "--material", path)
    assert receipt["status"] == "failed"
    assert receipt["failure_kind"] == "configuration"
    assert receipt["executor"] == "codex"
    assert receipt["draft_version"] is None and receipt["exit_code"] is None
    assert "codex" in receipt["error"].lower()
    assert receipt["attempt_id"] in receipt["log_ref"]
    assert (tmp_path / receipt["log_ref"]).is_file()
    assert task_cli(tmp_path, "attempt", receipt["attempt_id"]) == receipt


def install_cli(tmp_path, monkeypatch, body):
    executable = tmp_path / "bin" / "codex"
    executable.parent.mkdir(exist_ok=True)
    executable.write_text("""#!/usr/bin/python3
import json, sys
from pathlib import Path
if "--version" in sys.argv:
    print("codex-cli 0.172.0")
elif "debug" in sys.argv:
    print(json.dumps({"models": [{"slug":"gpt-6.2-sol"}]}))
else:
""" + "\n".join("    " + line for line in body.splitlines()) + "\n")
    executable.chmod(0o700)
    monkeypatch.setenv("PATH", str(executable.parent))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "empty-home"))
    monkeypatch.setenv("CODEX_API_KEY", "synthetic-probe-key")


def test_codex_gap_retains_diagnostics_without_raw_streams(tmp_path, snapshot, monkeypatch):
    install_cli(tmp_path, monkeypatch, """
answer = {"gaps": [{"reason": "缺少同期对照", "required_evidence": "上期现金流", "blocking": True}], "draft": None}
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps(answer))
print("synthetic-probe-key", file=sys.stderr)
""")
    report = material_file(tmp_path, "季报", excerpt="本期回款增加。")
    receipt = start(tmp_path, snapshot, "--material", report, "--executor", "codex")
    assert receipt["status"] == "blocked", receipt
    assert receipt["gaps"] == [{"reason": "缺少同期对照", "required_evidence": "上期现金流", "blocking": True}]
    assert receipt["exit_code"] == 0
    assert receipt["cli_version"] == "codex-cli 0.172.0"
    assert receipt["draft_version"] is None
    log = (tmp_path / receipt["log_ref"]).read_text()
    assert "synthetic-probe-key" not in log and "synthetic-probe-key" not in str(receipt)

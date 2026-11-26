import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from roll.v3.storage import sessions
from test_v3_codex_research import install_cli
from test_v3_development_inputs import PRESET, load_snapshot, observation
from test_v3_development_replay import _quotes


_SOURCE = str(Path(__file__).resolve().parents[1] / "src")


def cli_environment():
    return {**os.environ, "PYTHONPATH": _SOURCE}


def invocation(data_dir, *arguments):
    return [sys.executable, "-m", "roll.v3.cli", "--data-dir", str(data_dir), *arguments]


def cli(data_dir, *arguments, payload=None):
    process = subprocess.run(invocation(data_dir, *arguments), check=True, capture_output=True, text=True,
                             input=payload, env=cli_environment(), timeout=45)
    return json.loads(process.stdout)


def development_snapshot(data_dir):
    days = list(sessions("2023-01-03", "2023-12-29"))[-70:]
    _, rows = _quotes(days[0])
    for row in rows:
        row["source_ref"] = str(data_dir / "private-source-sentinel")
    rows.extend([
        observation("2024-01-02", close="88888000"),
        observation("2026-11-25", series="announcement", payload={"text": "later-announcement-sentinel"}),
        observation("2026-11-25", series="review_note", payload={"text": "later-review-sentinel"}),
        observation(days[-1], series="window_summary", payload={"text": "full-window-sentinel"}),
    ])
    return load_snapshot(data_dir, rows)


_REPLY = """
public = json.loads(raw)
reference = next(ref for ref in public["evidence"] if ref.startswith("trade:e0:"))
metric_ref = "metric:e0:costs"
answer = {"claims": [{"interpretation": "模拟路径发生了交易费用。",
                       "metrics": [{"ref": metric_ref, "value": public["metrics"][metric_ref]},
                                   {"ref": reference + "#quantity", "value": public["evidence"][reference]["quantity"]}],
                       "evidence_refs": [reference]}],
          "uncertainties": ["历史重建仅覆盖一个开发窗口。"], "gaps": [], "follow_up": []}
"""


def test_development_assistant_reads_a_persisted_receipt_once_and_returns_a_grounded_report(tmp_path, monkeypatch):
    snapshot = development_snapshot(tmp_path)
    at = "2023-12-29T15:05:00+08:00"
    cli(tmp_path, "account", "init", payload=json.dumps({
        "cash": "919991.83", "available_cash": "919991.83", "effective_at": at, "known_at": at,
    }))
    capture = tmp_path / "capture.json"
    receipt_command = invocation(tmp_path, "research", "task", "development-receipt")
    install_cli(tmp_path, monkeypatch, f"""
import subprocess
raw = sys.stdin.read()
attempt_id = Path.cwd().parent.name
attempt = subprocess.check_output({invocation(tmp_path, "research", "task", "attempt")!r} + [attempt_id],
                                  env={{"PYTHONPATH": {_SOURCE!r}}})
task_id = json.loads(attempt)["task_id"]
frozen = json.loads(subprocess.check_output({receipt_command!r} + [task_id], env={{"PYTHONPATH": {_SOURCE!r}}}))
assert frozen["receipt_id"] == json.loads(raw)["receipt_id"]
with Path({str(capture)!r}).open("a") as stream:
    stream.write(raw + "\\n")
""" + _REPLY + """
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps(answer))
""")

    attempt = cli(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot,
                  "--executor", "codex")
    assert attempt["status"] == "report_ready", attempt
    assert attempt["draft_version"] is None
    assert cli(tmp_path, "research", "task", "attempt", attempt["attempt_id"]) == attempt
    assert cli(tmp_path, "research", "task", "show", attempt["task_id"])["attempts"] == [attempt]
    report = attempt["report"]
    assert report["version"] == attempt["report_version"]
    assert report["attempt_id"] == attempt["attempt_id"]

    captured, = capture.read_text().splitlines()
    assert (tmp_path / attempt["input_ref"]).read_text() == captured
    public = json.loads(captured)
    frozen = cli(tmp_path, "research", "task", "development-receipt", attempt["task_id"])
    assert public["receipt_id"] == frozen["receipt_id"] == report["receipt_id"]
    assert public["snapshot"]["use_mode"] == "RECONSTRUCTED_RESEARCH"
    assert any(source["last_received_at"].startswith("2026-") for source in public["snapshot"]["sources"])
    fee, quantity = report["claims"][0]["metrics"]
    assert fee == {"ref": "metric:e0:costs", "value": "30.41"}
    assert quantity == {"ref": "trade:e0:2023-12-18#quantity", "value": 9800}
    for token in ("919991.83", "88888000", "later-announcement-sentinel", "later-review-sentinel",
                  "full-window-sentinel", "private-source-sentinel", str(tmp_path), "2024-01-02", "event_id"):
        assert token not in captured

    publish = subprocess.run(invocation(tmp_path, "research", "publish", "600362.SH", report["version"],
                                        "--reviewer", "测试研究者"), capture_output=True, text=True,
                             env=cli_environment(), timeout=15)
    assert publish.returncode == 2 and "无此研究草稿" in publish.stderr
    retry = cli(tmp_path, "research", "task", "retry", attempt["task_id"], "--executor", "offline")
    assert retry["status"] == "report_ready" and retry["report_version"] != attempt["report_version"]
    assert retry["development_receipt_id"] == frozen["receipt_id"]
    assert cli(tmp_path, "research", "task", "show", attempt["task_id"])["attempts"] == [attempt, retry]


def test_uncomputed_development_receipts_skip_the_assistant_on_start_and_retry(tmp_path, monkeypatch):
    marker = tmp_path / "unexpected"
    install_cli(tmp_path, monkeypatch, f"Path({str(marker)!r}).touch()")
    blocked_snapshot = load_snapshot(tmp_path, [])
    for snapshot, status, stage in ((blocked_snapshot, "blocked", "common_sample"),
                                    ("unknown-snapshot", "failed", "freeze_inputs")):
        first = cli(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot,
                    "--executor", "codex")
        frozen = cli(tmp_path, "research", "task", "development-receipt", first["task_id"])
        retry = cli(tmp_path, "research", "task", "retry", first["task_id"], "--executor", "codex")
        for attempt in (first, retry):
            assert attempt["status"] == status and attempt["failure_stage"] == stage
            assert attempt["development_receipt_id"] == frozen["receipt_id"]
            assert "report" not in attempt
        assert retry["attempt_id"] != first["attempt_id"]
    assert not marker.exists()


@pytest.mark.parametrize("outcome", ["failed", "timed_out", "cancelled", "invalid_response"])
def test_failed_development_interpretations_can_retry_the_same_receipt_and_public_input(tmp_path, monkeypatch, outcome):
    snapshot = development_snapshot(tmp_path)
    capture = tmp_path / "prompts"
    read_prompt = f"""
raw = sys.stdin.read()
with Path({str(capture)!r}).open("a") as stream:
    stream.write(raw + "\\n")
"""
    write_reply = """
Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(json.dumps(answer))
"""
    action = {
        "failed": "sys.exit(8)",
        "timed_out": "import time; time.sleep(30)",
        "cancelled": "import time; time.sleep(30)",
        "invalid_response": _REPLY + 'answer["claims"][0]["metrics"][0]["value"] = "999.99"' + write_reply,
    }[outcome]
    install_cli(tmp_path, monkeypatch, read_prompt + action)
    start = invocation(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot,
                       "--executor", "codex", "--timeout", "2" if outcome == "timed_out" else "30")
    with subprocess.Popen(start, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          env=cli_environment()) as process:
        if outcome == "cancelled":
            deadline = time.monotonic() + 15
            while not capture.is_file() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            assert capture.is_file(), "the supervised assistant did not receive its input"
            _, task_id, _, attempt_id = process.stderr.readline().strip().split()
            cancellation = cli(tmp_path, "research", "task", "cancel", attempt_id)
            assert cancellation["task_id"] == task_id and cancellation["status"] == "cancelled"
        out, stderr = process.communicate(timeout=35)
        assert process.returncode == 0, stderr

    first = json.loads(out)
    assert first["status"] == ("failed" if outcome == "invalid_response" else outcome), first
    if outcome in ("timed_out", "cancelled"):
        assert first["termination_reason"] == outcome
    else:
        assert first["failure_kind"] == ("cli_exit" if outcome == "failed" else "invalid_response")
    assert "report" not in first
    assert cli(tmp_path, "research", "task", "attempt", first["attempt_id"]) == first
    frozen = cli(tmp_path, "research", "task", "development-receipt", first["task_id"])

    # A changed observation and a new snapshot remain invisible to this frozen task.
    load_snapshot(tmp_path, [observation("2023-12-29", close="80")])
    install_cli(tmp_path, monkeypatch, read_prompt + _REPLY + write_reply)
    retry = cli(tmp_path, "research", "task", "retry", first["task_id"], "--executor", "codex")
    assert retry["status"] == "report_ready", retry
    assert retry["development_receipt_id"] == first["development_receipt_id"] == frozen["receipt_id"]
    assert cli(tmp_path, "research", "task", "development-receipt", first["task_id"]) == frozen
    original_prompt, retry_prompt = capture.read_text().splitlines()
    assert original_prompt == retry_prompt
    assert cli(tmp_path, "research", "task", "show", first["task_id"])["attempts"] == [first, retry]


def test_misconfigured_development_assistant_preserves_computation_for_retry(tmp_path):
    snapshot = development_snapshot(tmp_path)
    attempt = cli(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot,
                  "--executor", "unknown-acp")
    assert attempt["status"] == "failed"
    assert attempt["failure_kind"] == "configuration"
    frozen = cli(tmp_path, "research", "task", "development-receipt", attempt["task_id"])
    assert frozen["status"] == "computed"
    retry = cli(tmp_path, "research", "task", "retry", attempt["task_id"], "--executor", "offline")
    assert retry["status"] == "report_ready"
    assert retry["development_receipt_id"] == attempt["development_receipt_id"] == frozen["receipt_id"]


def test_configured_acp_delivers_the_same_development_contract(tmp_path, monkeypatch):
    snapshot = development_snapshot(tmp_path)
    (tmp_path / "research-harnesses.toml").write_text("""
default = "acp-test"
[acp.acp-test]
image = "test/development"
command = ["development", "acp"]
""")
    capture = tmp_path / "acp-prompts"
    engine = tmp_path / "docker"
    engine.write_text("""#!/usr/bin/python3
import json, sys
from pathlib import Path
if sys.argv[1] == "image":
    print("sha256:" + "3" * 64)
    sys.exit(0)
if sys.argv[1] == "rm":
    sys.exit(0)
assert "--mount" not in sys.argv

def emit(**message):
    print(json.dumps(dict(jsonrpc="2.0", **message)), flush=True)

msg = json.loads(input())
assert msg["method"] == "initialize"
emit(id=msg["id"], result={"protocolVersion": 1, "agentInfo": {"version": "1.2.3"}})
msg = json.loads(input())
assert msg["method"] == "session/new" and msg["params"]["mcpServers"] == []
emit(id=msg["id"], result={"sessionId": "development"})
msg = json.loads(input())
assert msg["method"] == "session/prompt"
instructions, schema, raw = msg["params"]["prompt"][0]["text"].rsplit("\\n", 2)
assert "开发实验" in instructions and json.loads(schema)["title"] == "DevelopmentReply"
""" + f"""
with Path({str(capture)!r}).open("a") as stream:
    stream.write(raw + "\\n")
""" + _REPLY + """
emit(method="session/update", params={"sessionId": "development", "update": {
    "sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": json.dumps(answer)}}})
emit(id=msg["id"], result={"stopReason": "end_turn"})
""")
    engine.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))

    attempt = cli(tmp_path, "research", "task", "development", "--preset", PRESET, "--snapshot", snapshot)
    assert attempt["status"] == "report_ready", attempt
    assert attempt["executor"] == "acp-test" and attempt["cli_version"] == "1.2.3"
    raw, = capture.read_text().splitlines()
    assert raw == (tmp_path / attempt["input_ref"]).read_text()
    assert json.loads(raw)["receipt_id"] == attempt["report"]["receipt_id"]

import pytest

from fastapi.testclient import TestClient

from roll.v3.web import create_app
from test_v3_research_tasks import snapshot, start, task_cli, material_file


@pytest.mark.parametrize("outcome", ["blocked", "draft_ready", "invalid_response"])
def test_workbench_selects_configured_acp_for_next_cli_attempt(tmp_path, monkeypatch, snapshot, outcome):
    (tmp_path / "research-harnesses.toml").write_text("""
default = "offline"
[acp.agy]
image = "test/agy"
command = ["agy", "acp"]
[acp.dsh]
image = "test/dsh"
command = ["dsh", "--profile", "acp"]
""")
    engine = tmp_path / "docker"
    script = '''#!/usr/bin/python3
import json, sys
args = sys.argv[1:]
if args[0] == "image":
    print("sha256:" + "3"*64)
    sys.exit(0)
if args[0] == "rm":
    sys.exit(0)
assert args[args.index("--entrypoint")+1] == "dsh"
assert args[-2:] == ["--profile","acp"]
def read():
    return json.loads(input())
def emit(**message):
    print(json.dumps(dict(jsonrpc="2.0", **message)), flush=True)
def result(msg, **data):
    emit(id=msg["id"],result=data)
msg = read()
assert msg["method"] == "initialize" and msg["params"]["clientCapabilities"] == {}
result(msg, protocolVersion=1, agentInfo={"version":"1.2.3"})
msg = read()
assert msg["method"] == "session/new" and msg["params"]["mcpServers"] == []
result(msg, sessionId="demo")
msg = read()
assert msg["method"] == "session/prompt" and msg["params"]["sessionId"]=="demo"
assert "第 3 页现金流" in msg["params"]["prompt"][0]["text"]
emit(id=10,method="session/request_permission",params={})
assert read()["result"]["outcome"]["outcome"] == "cancelled"
emit(id=11,method="fs/read_text_file",params={})
assert read()["error"]["code"] == -32601
body=json.dumps({"draft":None,"gaps":[{"reason":"缺少现金流比较","required_evidence":"上年季报","blocking":True}]})
if "OUTCOME" == "draft_ready":
    payload=json.loads(msg["params"]["prompt"][0]["text"].splitlines()[-1])
    body=json.dumps({"gaps":[], "draft":{"symbol":payload["symbol"],"as_of":payload["as_of"],
            "valid_until":payload["suggested_valid_until"],"markdown":"季报第三节现金流事实待复核",
            "evidence_refs":[payload["evidence"][0]["id"]],"fundamental_gate":"unknown",
            "thesis_status":"unknown","strategy_whitelist":[],"invalidation_triggers":[],
            "constraint_basis":{k:{"evidence_refs":[],"rationale":""} for k in
                ("fundamental_gate","thesis_status","strategy_whitelist","invalidation_triggers")}}})
elif "OUTCOME" == "invalid_response":
    body = "unstructured"
for part in [body[:10], body[10:]]:
    emit(method="session/update", params={"sessionId":"demo","update":{"sessionUpdate":"agent_message_chunk","content":{"type":"text","text":part}}})
result(msg, stopReason="end_turn")
'''
    engine.write_text(script.replace("OUTCOME", outcome))
    engine.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    endpoint = "/api/settings/research-harness"
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(endpoint).json()["selected"] == "offline"
        assert client.post(endpoint, json={"name":"garbage"}).status_code == 400
        assert client.post(endpoint, json={"name":"dsh"}).json()["selected"] == "dsh"
        receipt = start(tmp_path, snapshot, "--material", material_file(tmp_path, "公告", excerpt="第 3 页现金流"))
        assert receipt["executor"] == "dsh" and receipt["cli_version"] == "1.2.3", receipt
        if outcome == "invalid_response":
            assert receipt["status"] == "failed" and receipt["failure_kind"] == outcome
        else:
            assert receipt["status"] == outcome
        if outcome == "blocked":
            assert receipt["gaps"][0]["required_evidence"] == "上年季报"
        if outcome == "draft_ready":
            assert receipt["draft_version"] == receipt["attempt_id"]
        assert receipt["image_id"].startswith("sha256:")
        assert task_cli(tmp_path, "attempt", receipt["attempt_id"]) == receipt
        retry = task_cli(tmp_path, "retry", receipt["task_id"], "--executor", "offline")
        assert retry["status"] == "draft_ready"
        assert client.get(endpoint).json()["selected"] == "dsh"
        assert client.post(endpoint, json={"name":None}).json()["selected"] == "offline"

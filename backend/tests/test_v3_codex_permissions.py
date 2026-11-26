"""Target-machine probe through Roll with the installed CLI and a synthetic inference endpoint."""
import base64
import json
import time
from datetime import UTC, datetime
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import shlex
import shutil
import subprocess
from threading import Thread
from urllib.request import urlopen

import pytest

from test_v3_research_tasks import material_file, snapshot, start


@contextmanager
def server(handler):
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as http:
        worker = Thread(target=http.serve_forever, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{http.server_port}"
        finally:
            http.shutdown()
            worker.join()


class QuietHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.mark.parametrize("auth_mode", ["apikey", "chatgpt"])
def test_target_codex_has_no_file_workbench_or_extension_tools(tmp_path, monkeypatch, snapshot, auth_mode):
    codex = shutil.which("codex")
    if not codex or subprocess.check_output([codex, "--version"], text=True).strip() != "codex-cli 0.172.0":
        pytest.skip("requires the target codex-cli 0.172.0")
    requests = []
    hits = []
    marker = secrets.token_hex(20)
    secret = tmp_path / "private-host-only"
    secret.write_text(marker)

    class Workbench(QuietHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()

    class Inference(QuietHandler):
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(request)

            def emit(event, **payload):
                data = json.dumps({"type": event, **payload})
                self.wfile.write(f"event: {event}\ndata: {data}\n\n".encode())

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            rid = f"resp_{len(requests)}"
            emit("response.created", response={"id": rid, "object": "response", "status": "in_progress", "output": []})
            if len(requests) == 1:
                items = [{"id": f"fc_{n}", "type": "function_call", "call_id": f"call_{n}",
                          "name": "exec_command", "namespace": "functions", "arguments": json.dumps({"cmd": cmd})}
                         for n, cmd in enumerate((f"cat {shlex.quote(str(secret))}", f"curl {workbench}/assistant"))]
            else:
                answer = {"gaps": [{"blocking": True, "required_evidence": "上期公告", "reason": "缺少同期对照"}],
                          "draft": None}
                items = [{"id": "msg_final", "type": "message", "role": "assistant", "status": "completed",
                          "content": [{"type": "output_text", "text": json.dumps(answer), "annotations": []}]}]
            for i, item in enumerate(items):
                emit("response.output_item.added", output_index=i, item=item)
                emit("response.output_item.done", output_index=i, item=item)
            emit("response.completed", response={"id": rid, "object": "response", "status": "completed", "output": items})

    # Keep all credentials synthetic. Poison global context to verify that it never reaches inference.
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("Private project " + marker)
    project_config = tmp_path / ".codex"
    project_config.mkdir()
    (project_config / "config.toml").write_text(f'developer_instructions="{marker}"\n')
    account = tmp_path / "cli-account"
    account.mkdir()
    (account / "AGENTS.md").write_text(marker)
    (account / "config.toml").write_text(f'developer_instructions="{marker}"\n')
    if auth_mode == "chatgpt":
        claims = {"exp": int(time.time()) + 86400, "sub": "synthetic",
                  "https://api.openai.com/auth": {"chatgpt_account_id": "synthetic", "chatgpt_plan_type": "plus"}}
        encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
        token = "eyJhbGciOiJub25lIn0." + encoded + ".fake"
        login = {"auth_mode": "chatgpt", "last_refresh": datetime.now(UTC).isoformat(),
                 "tokens": {"id_token": token, "access_token": token, "refresh_token": "synthetic",
                            "account_id": "synthetic"}}
    else:
        login = {"OPENAI_API_KEY": "dummy-local-probe-only"}
    (account / "auth.json").write_text(json.dumps(login))
    (account / "auth.json").chmod(0o600)
    monkeypatch.setenv("CODEX_HOME", str(account))
    for name in ("OPENAI_API_KEY", "CODEX_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    with server(Workbench) as workbench, server(Inference) as endpoint:
        assert secret.read_text() == marker
        assert urlopen(workbench + "/host-control", timeout=2).status == 200
        wrapper = tmp_path / "bin" / "codex"
        wrapper.parent.mkdir()
        # Use the built-in OpenAI provider. Redirect the binary's HTTP endpoint solely in this fixture.
        wrapper.write_text(
            "#!/usr/bin/python3\nimport os,sys,subprocess\n"
            f"exe={codex!r}\nargs=sys.argv[1:]\n"
            "if 'exec' in args:\n"
            f" if {auth_mode!r}=='apikey': subprocess.run([exe,'login','--with-api-key'], "
            "input=b'rotated-synthetic-login\\n', check=True)\n"
            f" args[-1:-1]=['-c','openai_base_url=\"{endpoint}/v1\"','-c','chatgpt_base_url=\"{endpoint}/backend-api/\"']\n"
            "os.execv(exe,[exe,*args])\n"
        )
        wrapper.chmod(0o700)
        monkeypatch.setenv("PATH", str(wrapper.parent))
        answer = start(tmp_path, snapshot, "--executor", "codex", "--timeout", "20",
                       "--material", material_file(tmp_path, "本期报告", excerpt="销售回款较同期增加"))
    assert answer["status"] == "blocked", answer
    assert answer["exit_code"] == 0
    if auth_mode == "apikey":
        assert json.loads((account / "auth.json").read_text())["OPENAI_API_KEY"] == "rotated-synthetic-login"
    assert len(requests) == 2
    first, second = requests
    for request in requests:
        assert not request.get("tools")
        assert all(item.get("type") != "additional_tools" for item in request["input"])
        assert marker not in json.dumps(request)
    assert first["text"]["format"]["type"] == "json_schema"
    assert all(item["type"] == "message" or (
        item["type"] == "configuration_update" and set(item) <= {"type", "reasoning"}) for item in first["input"])
    messages = [(item["role"], item["content"][0]["text"]) for item in first["input"] if item["type"] == "message"]
    instructions = {msg for role, msg in messages if role == "developer"}
    assert len(instructions) == 1
    assert [role for role, _ in messages].count("user") == 1
    public, = [json.loads(text) for role, text in messages if role == "user"]
    assert public["materials"][0]["content"] == "销售回款较同期增加"
    assert public["materials"][0]["locator"] == "第三节"
    refusals = [item["output"] for item in second["input"] if item["type"] == "function_call_output"]
    assert len(refusals) == 2 and all("unsupported call: exec_command" in output for output in refusals)
    assert hits == ["/host-control"]
    assert marker not in str(answer)

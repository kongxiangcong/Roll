"""One ACP v1 turn over JSON-RPC stdio, run inside Roll's process supervisor."""
import json
import re
import subprocess
import sys


def turn(agent, prompt):
    chunks = []
    size = 0
    session_id = None

    def send(message):
        agent.stdin.write(json.dumps({"jsonrpc": "2.0", **message}, ensure_ascii=False).encode() + b"\n")
        agent.stdin.flush()

    def request(seq, method, params):
        nonlocal size
        send({"id": seq, "method": method, "params": params})
        while True:
            line = agent.stdout.readline(4_194_305)
            if not line or len(line) > 4_194_304:
                raise ValueError("invalid ACP frame")
            msg = json.loads(line)
            if msg.get("jsonrpc") != "2.0":
                raise ValueError("invalid ACP envelope")
            if "method" in msg:
                if "id" in msg:
                    if msg["method"] == "session/request_permission":
                        send({"id": msg["id"], "result": {"outcome": {"outcome": "cancelled"}}})
                    else:
                        send({"id": msg["id"], "error": {"code": -32601, "message": "Unsupported client method"}})
                elif msg["method"] == "session/update" and method == "session/prompt":
                    event = msg["params"]
                    if event["sessionId"] != session_id:
                        raise ValueError("unexpected session")
                    update = event["update"]
                    if update["sessionUpdate"] == "agent_message_chunk" and update["content"]["type"] == "text":
                        part = update["content"]["text"]
                        size += len(part)
                        if size > 4_194_304:
                            raise ValueError("oversize ACP response")
                        chunks.append(part)
            elif msg.get("id") == seq:
                if "error" in msg:
                    raise RuntimeError("ACP request failed")
                return msg["result"]

    init = request(1, "initialize", {"protocolVersion": 1, "clientCapabilities": {},
                                     "clientInfo": {"name": "roll", "version": "3"}})
    if init["protocolVersion"] != 1:
        raise ValueError("unsupported ACP version")
    session_id = request(2, "session/new", {"cwd": "/tmp", "mcpServers": []})["sessionId"]
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("missing session")
    result = request(3, "session/prompt", {"sessionId": session_id, "prompt": [{"type": "text", "text": prompt}]})
    if result.get("stopReason") != "end_turn":
        raise RuntimeError("ACP turn incomplete")
    version = (init.get("agentInfo") or {}).get("version")
    return {"text": "".join(chunks), "version": version if isinstance(version, str)
            and re.fullmatch(r"[0-9][0-9a-zA-Z.+_-]{0,63}", version) else None}


if __name__ == "__main__":
    with subprocess.Popen(sys.argv[1:], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL) as child:
        try:
            print(json.dumps(turn(child, sys.stdin.buffer.read().decode()), ensure_ascii=False))
        except (ValueError, KeyError, TypeError, AttributeError, BrokenPipeError, RuntimeError):
            sys.exit(2)
        finally:
            child.stdin.close()
            try:
                child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                child.kill()

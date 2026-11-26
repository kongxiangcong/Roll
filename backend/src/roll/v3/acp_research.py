"""Isolated ACP stdio harness, using a local image selected by trusted configuration."""
import json
import os
from pathlib import Path
import shutil
import sys

from roll.v3.research_harness import (HarnessFailure, INSTRUCTIONS, Reply, ResearchHarness, public_text,
                                      read_reply, record_input, runtime_directory)


class AcpExecutor(ResearchHarness):
    def __init__(self, name, profile, timeout):
        super().__init__(timeout)
        self.name = name
        self.profile = profile

    def permissions(self):
        return {"protocol": "ACP v1", "client_capabilities": {}, "mcp_servers": [],
                "runtime": "docker", "image": self.profile.image, "command": self.profile.command,
                "host_mounts": [], "network": self.profile.network}

    def _execute(self, manifest, receipt, data_dir, run_process):
        from roll.v3.research_tasks import preflight_gaps

        public = public_text(manifest)
        if preflight_gaps(manifest) or any(gap["blocking"] for gap in public["unreadable_materials"]):
            return {"gaps": public["unreadable_materials"]}
        engine = shutil.which("docker")
        if not engine:
            raise HarnessFailure("configuration", "ACP 助手需要本机 Docker 和已配置的本地镜像")
        with runtime_directory(data_dir, receipt["attempt_id"]) as work:
            env = {"HOME": str(work), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
            info = run_process([engine, "image", "inspect", "--format", "{{.Id}}", self.profile.image],
                               env=env, cwd=work)
            image_id = info.stdout.decode().strip()
            if info.returncode or not image_id.startswith("sha256:"):
                raise HarnessFailure("configuration", "无法读取 ACP 本地镜像，请核对 Docker 服务及镜像配置")
            receipt["image_id"] = image_id
            name = "roll-" + receipt["attempt_id"]
            args = [engine, "run", "--rm", "--interactive", "--pull=never", "--name", name,
                    "--network", self.profile.network, "--cap-drop=ALL", "--security-opt", "no-new-privileges",
                    "--read-only", "--tmpfs", "/tmp:rw,nosuid,nodev", "--workdir", "/tmp",
                    "--env", "HOME=/home/research"]
            if self.profile.login_volume:
                args.extend(["--mount", f"type=volume,source={self.profile.login_volume},target=/home/research"])
            else:
                args.extend(["--tmpfs", "/home/research:rw,nosuid,nodev,mode=1777"])
            key = self.profile.credential_env
            if key:
                if not os.environ.get(key):
                    raise HarnessFailure("configuration", f"未设置 ACP 提供方认证变量 {key}")
                env[key] = os.environ[key]
                args.extend(["--env", key])
            args.extend(["--entrypoint", self.profile.command[0], image_id, *self.profile.command[1:]])
            frozen = record_input(public, receipt, data_dir)
            prompt = (INSTRUCTIONS + "\n最终答复只输出一个符合下列 schema 的 JSON 对象。\n"
                      + json.dumps(Reply.model_json_schema(), ensure_ascii=False) + "\n" + frozen.decode())
            bridge = Path(__file__).with_name("acp_stdio.py")
            proc = run_process([sys.executable, "-I", "-S", str(bridge), *args], cwd=work, env=env,
                               input=prompt.encode(), cleanup=[engine, "rm", "-f", name])
            receipt["exit_code"] = proc.returncode
            if proc.returncode:
                raise HarnessFailure("cli_exit", "ACP 握手或研究会话失败，请核对镜像内的启动命令和认证")
            output = work / "last-message"
            transport = json.loads(proc.stdout)
            receipt["cli_version"] = transport["version"]
            response = transport["text"].strip().encode()
            lines = response.splitlines()
            if len(lines) >= 3 and lines[0] in (b"```json", b"```") and lines[-1] == b"```":
                response = b"\n".join(lines[1:-1])
            output.write_bytes(response)
            return read_reply(output, public)

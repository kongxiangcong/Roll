"""Version-pinned native Codex adapter."""
import json
import os
import platform
import re
import shutil
from pathlib import Path

from roll.v3.research_harness import (HarnessFailure, INSTRUCTIONS, Reply, ResearchHarness,
                                      public_text, read_reply, record_input, runtime_directory)


class CodexExecutor(ResearchHarness):
    name = "codex"

    def permissions(self):
        return {"tools": [], "sandbox": "read-only", "approval": "never", "model": MODEL,
                       "disabled_features": list(DISABLED_FEATURES), "settings": list(SETTINGS),
                       "isolated_home": True, "ephemeral": True, "model_catalog": "bundled, shell disabled"}

    def _execute(self, manifest, receipt, data_dir, run_process):
        from roll.v3.research_tasks import preflight_gaps

        executable = shutil.which("codex")
        if not executable:
            raise HarnessFailure("configuration", "找不到 codex 可执行文件，请检查 PATH 和安装版本")
        with runtime_directory(data_dir, receipt["attempt_id"]) as work:
            # No project or user configuration, inherited process environment, or session history.
            (work / ".roll-codex-root").touch()
            home = work / "home"
            home.mkdir(mode=0o700)
            env = {"HOME": str(home), "CODEX_HOME": str(home), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"}
            executable = str(Path(executable).resolve())
            version = run_process([executable, "--version"], cwd=work, env=env)
            actual = version.stdout.decode(errors="replace").strip()
            if not re.fullmatch(r"codex-cli [0-9]+\.[0-9]+\.[0-9]+", actual):
                raise HarnessFailure("configuration", "无法核实 Codex CLI 版本")
            receipt["cli_version"] = actual
            if version.returncode or actual != "codex-cli 0.172.0":
                raise HarnessFailure("configuration", f"该权限配置要求 codex-cli 0.172.0，实际版本为 {actual}")
            if platform.system() != "Linux" or platform.machine() != "x86_64":
                raise HarnessFailure("configuration", "该权限配置要求 x86_64 Linux")
            public = public_text(manifest)
            if preflight_gaps(manifest) or any(gap["blocking"] for gap in public["unreadable_materials"]):
                return {"gaps": public["unreadable_materials"]}
            managed = Path("/etc/codex")
            if managed.is_dir() and any(managed.iterdir()):
                raise HarnessFailure("configuration", "检测到尚未验证的系统 Codex 配置 /etc/codex")
            configure_model(executable, work, env, run_process)
            attach_login(home, env)
            output = work / "last-message"
            prompt = record_input(public, receipt, data_dir)
            proc = run_process(exec_command(executable, work), cwd=work, env=env, input=prompt)
            receipt["exit_code"] = proc.returncode
            if proc.returncode:
                raise classify_exit(proc)
            return read_reply(output, public)


MODEL = "gpt-6.2-sol"
DISABLED_FEATURES = (
    "shell_tool", "unified_exec", "view_image", "apps", "plugins", "hooks", "code_mode", "code_mode_host",
    "browser_use", "computer_use", "in_app_browser", "image_generation", "multi_agent", "multi_agent_v2",
    "skill_search", "sleep_tool", "goals", "tool_suggest", "api_key_model_discovery", "shell_snapshot",
    "enable_request_compression",
)


SETTINGS = (
    'project_root_markers=[".roll-codex-root"]', "mcp_servers={}", "analytics.enabled=false", "feedback.enabled=false",
    'web_search="disabled"', "project_doc_max_bytes=0", "tools.update_plan.enabled=false",
    "tools.experimental_request_user_input.enabled=false", "agents.enabled=false", "include_apps_instructions=false",
    "include_collaboration_mode_instructions=false", "include_environment_context=false",
    "include_permissions_instructions=false", "skills.include_instructions=false", "cloud.skills.enabled=false",
    "orchestrator.mcp.enabled=false",
)
def configure_model(executable, work, env, run_process):
    catalog = run_process([executable, "debug", "models", "--bundled"], cwd=work, env=env)
    try:
        models = json.loads(catalog.stdout)["models"]
        model = next(model for model in models if model["slug"] == MODEL)
    except (ValueError, KeyError, StopIteration, TypeError):
        raise HarnessFailure("configuration", "Codex 内置目录未提供已验证的研究模型") from None
    if catalog.returncode:
        raise HarnessFailure("configuration", "无法读取 Codex 内置模型目录")
    model.update(tool_mode="default", shell_type="disabled", apply_patch_tool_type=None,
                 experimental_supported_tools=[], supports_search_tool=False,
                 include_skills_usage_instructions=False, include_plugin_usage_instructions=False,
                 include_apps_usage_instructions=False)
    model.pop("multi_agent_version", None)
    (work / "catalog.json").write_text(json.dumps({"models": [model]}))
    (work / "instructions.txt").write_text(INSTRUCTIONS, encoding="utf-8")
    (work / "response.json").write_text(json.dumps(Reply.model_json_schema()))


def attach_login(home, env):
    auth = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "auth.json"
    key = os.environ.get("CODEX_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if key:
        env["CODEX_API_KEY"] = key
    elif auth.is_file():
        # This CLI's file credential store updates auth.json in place. Share its
        # locking files as well, while excluding global instructions/plugins.
        auth_dir = auth.parent.resolve()
        for name in ("auth.json", "auth.lock", "auth.json.lock"):
            (home / name).symlink_to(auth_dir / name)
    else:
        raise HarnessFailure("configuration", "未找到 Codex 登录，请先执行 codex login")


def exec_command(executable, work):
    args = [executable, "--no-daemon", "-a", "never", "exec", "--ignore-rules", "--ignore-user-config",
            "--strict-config", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
            "--color", "never", "-m", MODEL, "--output-schema", str(work / "response.json"),
            "--output-last-message", str(work / "last-message")]
    for feature in DISABLED_FEATURES:
        args.extend(["--disable", feature])
    args.extend(["--enable", "skip_host_skill_discovery"])
    files = {"model_catalog_json": work / "catalog.json", "model_instructions_file": work / "instructions.txt"}
    for setting in SETTINGS:
        args.extend(["-c", setting])
    for name, path in files.items():
        args.extend(["-c", f"{name}={json.dumps(str(path), ensure_ascii=False)}"])
    return [*args, "-"]


def classify_exit(proc):
    diagnostic = proc.stderr.lower()
    if any(token in diagnostic for token in (b"401 unauthorized", b"403 forbidden", b"not logged in",
                                             b"invalid api key", b"authentication", b"refresh token")):
        return HarnessFailure("configuration", "Codex 认证或模型访问失败，请检查 codex login 与账户权限")
    if any(token in diagnostic for token in (b"error loading config", b"error loading configuration",
                                             b"unknown feature", b"unknown field", b"invalid config")):
        return HarnessFailure("configuration", "Codex 未能启用已验证的权限配置，请核对 CLI 安装")
    if b"429" in diagnostic:
        reason = "模型服务请求受限，请核对额度或稍后人工重试"
    elif b"503" in diagnostic or b"502" in diagnostic:
        reason = "模型服务暂时不可用，可稍后人工重试"
    elif b"context_length_exceeded" in diagnostic:
        reason = "公开输入超过模型上下文，请缩短材料摘录并发起关联任务"
    else:
        reason = "Codex 运行或服务连接失败，请核对网络和服务状态"
    return HarnessFailure("cli_exit", f"{reason}（CLI 退出码 {proc.returncode}）")

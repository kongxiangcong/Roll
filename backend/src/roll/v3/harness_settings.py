"""Local ACP profiles and the workbench's per-data-directory selection."""
import re
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from roll.v3.storage import database


class AcpProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    image: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._/:@-]*$")
    network: str = Field("bridge", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
    command: list[str] = Field(min_length=1)
    # Only the named provider credential is forwarded into the container.
    credential_env: str | None = Field(None, pattern=r"^[A-Z][A-Z0-9_]*$")
    login_volume: str | None = Field(None, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")


class Catalog(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    default: str = "offline"
    acp: dict[str, AcpProfile] = Field(default_factory=dict)


def catalog(data_dir):
    path = Path(data_dir) / "research-harnesses.toml"
    try:
        with path.open("rb") as stream:
            config = Catalog.model_validate(tomllib.load(stream))
    except FileNotFoundError:
        return Catalog()
    except (ValidationError, tomllib.TOMLDecodeError):
        raise ValueError("research-harnesses.toml 配置无效，请核对研究助手配置格式") from None
    for name, profile in config.acp.items():
        if (not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name) or name in ("offline", "codex")
                or profile.network == "host"
                or not all(arg and "\x00" not in arg for arg in profile.command)):
            raise ValueError("ACP 助手名称或启动参数无效")
    if config.default not in ("offline", "codex", *config.acp):
        raise ValueError("默认研究助手未配置")
    return config


def settings(data_dir, *, save=False, selection=None):
    config = catalog(data_dir)
    names = ["offline", "codex", *config.acp]
    if save and selection is not None and selection not in names:
        raise ValueError("所选研究助手未配置")
    override = _selection(data_dir, save, selection)
    return {"available": names, "default": config.default, "override": override,
            "selected": override or config.default}


def _selection(data_dir, save=False, selection=None):
    with database(data_dir, write=save) as db:
        db.execute("CREATE TABLE IF NOT EXISTS research_harness_setting (id INTEGER PRIMARY KEY, name TEXT)")
        if save:
            db.execute("INSERT OR REPLACE INTO research_harness_setting VALUES (1, ?)", (selection,))
        row = db.execute("SELECT name FROM research_harness_setting WHERE id=1").fetchone()
    return row[0] if row else None


def select_harness(data_dir, name, timeout):
    from roll.v3.acp_research import AcpExecutor
    from roll.v3.codex_research import CodexExecutor

    config = None
    if name is None:
        config = catalog(data_dir)
        name = _selection(data_dir) or config.default
    if name == "offline":
        return None
    if name == "codex":
        return CodexExecutor(timeout)
    profile = (config or catalog(data_dir)).acp.get(name)
    if profile is None:
        raise ValueError(f"研究助手 {name} 未配置，请重新选择")
    return AcpExecutor(name, profile, timeout)

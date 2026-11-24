import os
import re
from pathlib import Path


def load_runtime_environment() -> None:
    """Read one explicit file or the source checkout's .env without overriding the process.

    Values are literals: no variable interpolation, shell expansion or credential discovery.
    Test hosts do not implicitly read the checkout's credentials.
    """
    explicit = os.environ.get('ROLL_ENV_FILE')
    if os.environ.get('ROLL_ENV') == 'test' and not explicit:
        return
    path = Path(explicit).expanduser() if explicit else Path(__file__).resolve().parents[3] / '.env'
    if not path.is_file():
        if explicit:
            raise ValueError('ROLL_ENV_FILE_NOT_FOUND')
        return
    if path.stat().st_size > 65536:
        raise ValueError('ROLL_ENV_FILE_TOO_LARGE')
    values = {}
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].lstrip()
        key, separator, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if not separator or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
            raise ValueError(f'ROLL_ENV_FILE_INVALID_LINE_{number}')
        if value.startswith(('"', "'")):
            quote = value[0]
            end = value.find(quote, 1)
            if end < 0 or (value[end + 1:].strip() and not value[end + 1:].strip().startswith('#')):
                raise ValueError(f'ROLL_ENV_FILE_INVALID_LINE_{number}')
            value = value[1:end]
        else:
            value = re.split(r'\s+#', value, maxsplit=1)[0].rstrip()
        values[key] = value
    for key, value in values.items():
        os.environ.setdefault(key, value)


def data_directory() -> Path:
    if configured := os.environ.get("ROLL_DATA_DIR"):
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Roll"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "roll"

DEFAULT_WATCHLIST = Path(__file__).resolve().parents[3] / "config" / "watchlist.yaml"


def load_watchlist(path=None):
    import yaml
    from pydantic import BaseModel, Field, ConfigDict, TypeAdapter

    class WatchItem(BaseModel):
        model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
        code: str = Field(pattern=r"^[0-9]{6}\.(SH|SZ)$")
        sector_etf: str = Field(pattern=r"^[0-9]{6}\.(SH|SZ)$")
        name: str = Field(min_length=1)
        max_position_pct: float = Field(ge=0, le=1)
        atr_stop_multiplier: float = Field(gt=0)

    try:
        values = yaml.safe_load(Path(path or DEFAULT_WATCHLIST).read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as error:
        raise ValueError("跟踪池 YAML 语法错误") from error
    if not isinstance(values, dict) or set(values) != {"watchlist"}:
        raise ValueError("跟踪池 YAML 顶层须有 watchlist")
    items = TypeAdapter(list[WatchItem]).validate_python(values["watchlist"])
    if len({item.code for item in items}) != len(items) or any(item.code == "000300.SH" for item in items):
        raise ValueError("跟踪池证券重复或包含沪深 300 指数")
    return [item.model_dump() for item in items]


def active_watchlist(data_dir):
    from roll.db import connect
    import json
    with connect(data_dir / "roll.sqlite3") as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='watchlist_config'").fetchone():
            row = db.execute("SELECT items FROM watchlist_config WHERE id=1").fetchone()
            if row:
                return json.loads(row[0])
    return []

"""Fresh METHOD engineering fixture; actual clock, zero acquisition or delivery."""
from pathlib import Path
import json, os
import httpx
from roll.app import create_app

def factory():
    root = Path(os.environ['ROLL_DATA_DIR'])
    assert not (root / 'roll.sqlite3').exists(), 'Fresh owned runtime only'
    def forbidden(request):
        with (root.parent / 'forbidden-external-attempts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'method': request.method, 'url': str(request.url)}) + '\n')
        raise AssertionError('METHOD fixture forbids external acquisition/delivery')
    return create_app(root, runtime_role='IN_PROCESS', market_transport=httpx.MockTransport(forbidden),
                      codex_worker=root.parent / 'DISABLED_PROVIDER.py',
                      baostock_worker=root.parent / 'DISABLED_SOURCE.py',
                      notification_transport=httpx.MockTransport(forbidden))

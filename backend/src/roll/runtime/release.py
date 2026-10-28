"""Serve the pinned frontend build from the local API origin."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse


def identity():
    root = Path(__file__).resolve().parents[4]
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, timeout=2, stderr=subprocess.DEVNULL).decode().strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=root, timeout=2))
    except (OSError, subprocess.SubprocessError):
        commit, dirty = None, None
    dist = Path(os.environ.get('ROLL_WEB_DIST', root/'frontend/dist'))
    manifest = dist/'release.json'
    return {'source_commit': commit, 'unavailable_modules': [] if (root/'backend/src/roll/market/sse_daily.py').is_file() else ['roll.market.sse_daily'], 'source_dirty': dirty,
            'web_build': json.loads(manifest.read_text()) if manifest.is_file() else None,
            'backend_lock_sha256': hashlib.sha256((root/'backend/uv.lock').read_bytes()).hexdigest() if (root/'backend/uv.lock').is_file() else None}


def mount_web(app):
    configured = os.environ.get('ROLL_WEB_DIST')
    if not configured:
        return
    root = Path(configured).resolve()
    if not (root/'index.html').is_file():
        raise RuntimeError('ROLL_WEB_DIST must contain a built index.html')

    @app.get('/{path:path}', include_in_schema=False)
    def built_web(path: str):
        if path == 'api' or path.startswith('api/'):
            raise HTTPException(404, 'API_NOT_FOUND')
        target = (root/path).resolve()
        if not target.is_relative_to(root):
            raise HTTPException(404)
        if not target.is_file():
            if Path(path).suffix:
                raise HTTPException(404)
            target = root/'index.html'
        return FileResponse(target, headers={'Cache-Control': 'no-cache'})

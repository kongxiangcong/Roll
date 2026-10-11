"""Diagnostic only: exact private SDK bootstrap, no Host, ReviewRun or model methods."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[5]
PRIVATE = ROOT / '.roll-data/implementation-evidence/continuation-review-fixes/codex-startup-diagnostic'


def child(output):
    # Execution is gated until the parent assigns the Windows kill-on-close job.
    assert sys.stdin.readline().strip() == 'DIAGNOSTIC_ACCOUNT_ONLY'
    from importlib.metadata import version
    from openai_codex.client import CodexClient, CodexConfig
    stages = []
    client = None
    result = {'model_calls': 0, 'review_runs_created': 0, 'material_reads': 0}
    started = time.monotonic()
    try:
        versions = {n: version(n) for n in ['openai-codex', 'openai-codex-cli-bin']}
        assert set(versions.values()) == {'0.161.0'}
        result['versions'] = versions
        stages.append('client_construct')
        client = CodexClient(CodexConfig(cwd=os.getcwd(), client_name='roll_evidence',
            client_title='Roll evidence'), approval_handler=lambda *_: {'error': {'code': -32601,
            'message': 'Diagnostic has no model or tool capability'}})
        stages.append('client_enter')
        with client:
            stages.append('initialize')
            initialized = client.initialize()
            result['initialize_succeeded'] = True
            result['runtime_version'] = client._runtime_version
            stages.append('account_read')
            account = client.account_read().model_dump(mode='json', by_alias=True)
            result['account_type'] = (account.get('account') or {}).get('type')
            assert result['account_type'] == 'chatgpt'
            result['account_read_succeeded'] = True
        result['verdict'] = 'PASS'
    except Exception as error:
        result.update(verdict='FAIL', failed_stage=stages[-1] if stages else 'sdk_import',
            error_type=type(error).__name__, rpc_code=getattr(error, 'code', None),
            error_message=str(error), traceback=traceback.format_exc())
    finally:
        result['stages'] = stages
        result['elapsed_seconds'] = round(time.monotonic() - started, 3)
        result['runtime_stderr'] = list(client._stderr_lines) if client else []
        # This is a private ignored artifact; no account response or auth object is saved.
        Path(output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--child-output')
    parser.add_argument('--diagnostic-account-only', action='store_true')
    parser.add_argument('--auth-file')
    parser.add_argument('--attempt', choices=['01-original'], default='01-original')
    args = parser.parse_args()
    if args.child_output:
        child(args.child_output)
        return
    assert args.diagnostic_account_only
    auth_path = Path(args.auth_file).resolve()
    assert auth_path == Path('C:/Users/72449/.codex/auth.json').resolve() and auth_path.is_file()
    output = PRIVATE / args.attempt
    output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(ROOT / 'backend/src'))
    from roll.agents.codex_process import Job, clean_environment
    from roll.agents.codex_evidence import CONFIG
    # Same existing credential pipeline subset as codex_evidence/codex_process.
    original_auth = auth_path.read_bytes()
    auth = json.loads(original_auth)
    assert auth.get('auth_mode') == 'chatgpt' and auth.get('tokens')
    task_auth = {'auth_mode': 'chatgpt', 'tokens': {k: v for k, v in auth['tokens'].items()
        if k in {'access_token', 'id_token', 'refresh_token', 'account_id'}},
        'last_refresh': auth.get('last_refresh')}
    secret_values = [str(v) for v in auth.get('tokens', {}).values() if v]
    def redact(value):
        if isinstance(value, dict):
            return {k: redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [redact(v) for v in value]
        if not isinstance(value, str):
            return value
        for secret in secret_values:
            value = value.replace(secret, '<REDACTED>')
        value = re.sub(r'(?i)(authorization\s*[:=]\s*|bearer\s+)[^\s,;]+', r'\1<REDACTED>', value)
        value = re.sub(r'\b(?:sk-[A-Za-z0-9_-]+|eyJ[A-Za-z0-9_.-]{25,})\b', '<REDACTED>', value)
        return value
    protected = [ROOT / 'backend/src/roll/agents/codex_worker.py',
        ROOT / 'backend/src/roll/agents/codex_process.py', ROOT / 'backend/src/roll/agents/codex_evidence.py']
    source_before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    raw = output / 'private-sdk-result.json'
    audit = {'purpose': 'SDK_INITIALIZE_ACCOUNT_READ_ONLY', 'review_runs_created': 0,
        'model_calls': 0, 'material_reads': 0, 'deepseek_calls': 0,
        'network_limitation': 'Initialization/account refresh may contact OpenAI; no network-zero claim.'}
    with tempfile.TemporaryDirectory(prefix='roll-codex-startup-diagnostic-') as directory:
        task = Path(directory)
        for name in ['home', 'cwd', 'user']:
            (task / name).mkdir()
        (task / 'home/auth.json').write_text(json.dumps(task_auth), encoding='utf-8')
        (task / 'home/config.toml').write_text(CONFIG, encoding='utf-8')
        del task_auth, auth
        with (output / 'private-child-stdout.txt').open('w', encoding='utf-8') as stdout, \
             (output / 'private-child-stderr.txt').open('w', encoding='utf-8') as stderr:
            process = subprocess.Popen([sys.executable, '-u', str(Path(__file__).resolve()),
                '--child-output', str(raw)], cwd=task / 'cwd', env=clean_environment(task),
                stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW)
            job = Job(process.pid)
            audit.update(worker_pid=process.pid, containment='WINDOWS_JOB_KILL_ON_CLOSE',
                isolated_cwd=True, isolated_home=True, environment_keys=sorted(clean_environment(task)))
            try:
                process.stdin.write('DIAGNOSTIC_ACCOUNT_ONLY\n')
                process.stdin.flush()
                process.wait(timeout=45)
                audit['child_exit_code'] = process.returncode
            except subprocess.TimeoutExpired:
                audit['timed_out'] = True
            finally:
                job.terminate()
                process.wait(timeout=5)
                audit['remaining_job_pids'] = job.pids()
                job.close()
        audit['credential_source_unchanged'] = original_auth == auth_path.read_bytes()
    audit['temporary_directory_removed'] = not task.exists()
    audit['production_sources_unchanged'] = all(hashlib.sha256(p.read_bytes()).hexdigest() == source_before[str(p.relative_to(ROOT))] for p in protected)
    result = json.loads(raw.read_text(encoding='utf-8')) if raw.exists() else {'verdict': 'FAIL', 'error_type': 'PROBE_NO_RESULT'}
    sanitized = redact(result)
    sanitized['process_audit'] = audit
    assert audit['credential_source_unchanged'] and audit['production_sources_unchanged'] and audit['temporary_directory_removed']
    (Path(__file__).parent / 'codex-startup-probe-results.json').write_text(json.dumps(sanitized, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: sanitized.get(k) for k in ['verdict', 'failed_stage', 'error_type', 'rpc_code', 'error_message', 'elapsed_seconds', 'stages']}, ensure_ascii=False))
    sys.exit(0 if sanitized['verdict'] == 'PASS' else 1)


if __name__ == '__main__':
    main()

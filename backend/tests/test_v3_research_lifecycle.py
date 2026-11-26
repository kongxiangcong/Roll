import json
import pytest
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from roll.v3.research_tasks import offline_executor, retry_task
from test_v3_research_tasks import material_file, snapshot, start


def cli(data_dir, *args, check=True, payload=None):
    return subprocess.run([sys.executable, '-m', 'roll.v3.cli', '--data-dir', str(data_dir), *args],
                          text=True, input=json.dumps(payload) if payload is not None else None,
                          capture_output=True, timeout=10, check=check)


def test_waiting_attempt_allows_other_cli_writes_and_rejects_parallel_retry(tmp_path, snapshot):
    from test_v3_account import BASELINE

    first = start(tmp_path, snapshot, '--material', material_file(tmp_path, '季报', excerpt='销售回款增加'))
    task_id = first['task_id']
    waiting, release = Event(), Event()

    def executor(manifest):
        waiting.set()
        assert release.wait(15)
        return offline_executor(manifest)

    with ThreadPoolExecutor() as pool:
        owner = pool.submit(retry_task, tmp_path, task_id, executor=executor)
        assert waiting.wait(5)
        try:
            current = json.loads(cli(tmp_path, 'research', 'task', 'show', task_id).stdout)['attempts']
            assert [item['status'] for item in current] == ['draft_ready', 'running']
            write = cli(tmp_path, 'account', 'init', payload=BASELINE)
            assert json.loads(write.stdout)['book_id'] == 'real'
            duplicate = cli(tmp_path, 'research', 'task', 'retry', task_id, check=False)
            assert duplicate.returncode == 2 and current[-1]['attempt_id'] in duplicate.stderr
        finally:
            release.set()
        assert owner.result()['status'] == 'draft_ready'
    assert len(json.loads(cli(tmp_path, 'research', 'task', 'show', task_id).stdout)['attempts']) == 2


def test_cancellation_during_delivery_keeps_receipt_and_draft_consistent(tmp_path, snapshot):
    import time

    from roll.v3.cli import run

    original = start(tmp_path, snapshot, '--material', material_file(tmp_path, '季报', excerpt='销售回款增加'))
    task_id = original['task_id']
    ready, deliver = Event(), Event()

    def executor(manifest):
        result = offline_executor(manifest)
        ready.set()
        assert deliver.wait(10)
        return result

    with ThreadPoolExecutor() as pool:
        owner = pool.submit(retry_task, tmp_path, task_id, executor=executor)
        assert ready.wait(5)
        attempt_id = run(['research', 'task', 'show', task_id], data_dir=tmp_path)['attempts'][-1]['attempt_id']
        cancel = pool.submit(cli, tmp_path, 'research', 'task', 'cancel', attempt_id)
        try:
            deadline = time.monotonic() + 5
            while not cancel.done() and time.monotonic() < deadline:
                attempt = run(['research', 'task', 'attempt', attempt_id], data_dir=tmp_path)
                if attempt['status'] == 'cancelling':
                    break
                time.sleep(.02)
        finally:
            deliver.set()
        receipt = owner.result()
        assert json.loads(cancel.result().stdout) == receipt
    assert receipt['status'] == 'cancelled' and receipt['draft_version'] is None
    latest = run(['research', 'show', '600362.SH', '--draft'], data_dir=tmp_path)
    assert latest['version'] == original['draft_version']
    # The other ordering: a cancel arriving after publication of the result is idempotent.
    assert json.loads(cli(tmp_path, 'research', 'task', 'cancel', original['attempt_id']).stdout) == original


def test_killed_owner_can_be_retried_with_its_original_manifest(tmp_path, snapshot):
    from pathlib import Path
    import time

    from roll.v3.cli import run

    original = start(tmp_path, snapshot, '--material', material_file(tmp_path, '季报', excerpt='销售回款增加'))
    task_id = original['task_id']
    # Use the public injection boundary to terminate an offline owner inside a blocking executor.
    script = """
import sys, time
from pathlib import Path
from roll.v3.research_tasks import retry_task
def wait(manifest):
    Path(sys.argv[1], 'started').touch()
    time.sleep(30)
retry_task(sys.argv[1], sys.argv[2], executor=wait)
"""
    owner = subprocess.Popen([sys.executable, '-c', script, str(tmp_path), task_id])
    try:
        deadline = time.monotonic() + 5
        while not Path(tmp_path, 'started').exists():
            assert owner.poll() is None and time.monotonic() < deadline
            time.sleep(.02)
        visible = run(['research', 'task', 'show', task_id], data_dir=tmp_path)
        assert visible['attempts'][-1]['status'] == 'running'
    finally:
        owner.kill()
        owner.wait()
    retried = json.loads(cli(tmp_path, 'research', 'task', 'retry', task_id).stdout)
    recovered = json.loads(cli(tmp_path, 'research', 'task', 'show', task_id).stdout)
    assert [item['status'] for item in recovered['attempts']] == ['draft_ready', 'interrupted', 'draft_ready']
    interrupted = recovered['attempts'][1]
    assert interrupted['termination_reason'] == 'interrupted' and interrupted['draft_version'] is None
    assert visible['manifest'] == recovered['manifest']
    assert len({item['manifest_sha256'] for item in [original, interrupted, retried]}) == 1


@pytest.mark.skipif(sys.platform != "linux", reason="Linux Codex subprocess acceptance")
@pytest.mark.parametrize("reason", ["timed_out", "cancelled", "interrupted", "signal"])
def test_stop_reaps_all_codex_descendants_and_releases_the_task(tmp_path, snapshot, monkeypatch, reason):
    import os
    from pathlib import Path
    import signal
    import time

    original = start(tmp_path, snapshot, '--material', material_file(tmp_path, '季报', excerpt='经营现金流增加'))
    task_id = original['task_id']
    marker = tmp_path / 'pids.json'
    fake = tmp_path / 'codex'
    # A descendant escapes the original process group. The OS probe checks for zombies too.
    fake.write_text(f"""#!{sys.executable}
import json, os, pathlib, subprocess, sys, time
if '--version' in sys.argv:
    print('codex-cli 0.172.0')
    sys.exit()
if 'debug' in sys.argv:
    print(json.dumps({{'models': [{{'slug': 'gpt-6.2-sol'}}]}}))
    sys.exit()
assert 'exec' in sys.argv
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
pathlib.Path({str(marker)!r}).write_text(json.dumps([os.getpid(), child.pid]))
if {reason == 'signal'!r}:
    while not pathlib.Path({str(tmp_path / 'exit-now')!r}).exists():
        time.sleep(.01)
    os.kill(os.getpid(), 9)
time.sleep(30)
""")
    fake.chmod(0o700)
    monkeypatch.setenv('PATH', str(tmp_path) + os.pathsep + os.environ['PATH'])
    monkeypatch.setenv('CODEX_API_KEY', 'fake')
    monkeypatch.setenv('CODEX_HOME', str(tmp_path / 'empty-home'))
    timeout = '1.5' if reason == 'timed_out' else '30'
    args = [sys.executable, '-m', 'roll.v3.cli', '--data-dir', str(tmp_path),
            'research', 'task', 'retry', task_id, '--executor', 'codex', '--timeout', timeout]
    owner = subprocess.Popen(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pids = []
    try:
        deadline = time.monotonic() + 5
        while not marker.exists():
            assert owner.poll() is None, owner.communicate()
            assert time.monotonic() < deadline
            time.sleep(.02)
        pids = json.loads(marker.read_text())
        visible = json.loads(cli(tmp_path, 'research', 'task', 'show', task_id).stdout)['attempts'][-1]
        assert visible['status'] == 'running' and visible['executor'] == 'codex'
        assert visible['cli_version'] == 'codex-cli 0.172.0' and visible['input_sha256']
        assert (tmp_path / visible['log_ref']).is_file()
        attempt_id = visible['attempt_id']
        if reason == 'cancelled':
            json.loads(cli(tmp_path, 'research', 'task', 'cancel', attempt_id).stdout)
        elif reason == 'interrupted':
            owner.kill()
        elif reason == 'signal':
            (tmp_path / 'exit-now').touch()
        expected = 'interrupted' if reason == 'signal' else reason
        out, err = owner.communicate(timeout=7)
        if reason != 'interrupted':
            assert owner.returncode == 0, err
            assert json.loads(out)['status'] == expected
        receipt = json.loads(cli(tmp_path, 'research', 'task', 'attempt', attempt_id).stdout)
        assert receipt['status'] == receipt['termination_reason'] == expected
        if reason == 'signal':
            assert receipt['exit_code'] == -9
        assert receipt['draft_version'] is None
        assert all(not Path(f'/proc/{pid}').exists() for pid in pids)
        old_log = (tmp_path / receipt['log_ref']).read_bytes()
        fake.write_text(f'#!{sys.executable}\nprint("unexpected version")\n')
        retried = json.loads(cli(tmp_path, 'research', 'task', 'retry', task_id, '--executor', 'codex').stdout)
        assert retried['attempt_id'] != attempt_id and retried['log_ref'] != receipt['log_ref']
        assert retried['manifest_sha256'] == receipt['manifest_sha256'] == original['manifest_sha256']
        assert (tmp_path / receipt['log_ref']).read_bytes() == old_log
        assert json.loads(cli(tmp_path, 'research', 'task', 'attempt', attempt_id).stdout) == receipt
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=5)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

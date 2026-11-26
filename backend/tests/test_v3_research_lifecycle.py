import json
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

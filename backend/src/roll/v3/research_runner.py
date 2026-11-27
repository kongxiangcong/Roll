"""Background research worker managed by the local Roll workbench."""
from concurrent.futures import ThreadPoolExecutor
import json
import threading

from roll.v3.research_tasks import (
    ACTIVE,
    ACTIVE_PARAMS,
    _DEFAULT_HARNESS,
    execute_attempt,
    read_receipt,
    task_database,
)


class ResearchRunner:
    """Single-worker background queue for local workbench research attempts."""

    def __init__(self, data_dir, *, default_executor=_DEFAULT_HARNESS):
        self.data_dir = data_dir
        self.default_executor = default_executor
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="roll-research")
        self._lock = threading.Lock()
        self._futures = {}
        self._closed = False

    def recover_orphans(self):
        """Reconcile only attempts whose owning process lock is no longer held."""
        with task_database(self.data_dir) as db:
            rows = db.execute(
                f"SELECT receipt FROM research_attempt WHERE json_extract(receipt, '$.status') IN ({ACTIVE_PARAMS})",
                ACTIVE,
            ).fetchall()
        recovered = []
        for row in rows:
            receipt = json.loads(row["receipt"])
            if receipt["status"] == "pending":
                continue
            updated = read_receipt(self.data_dir, receipt)
            if updated["status"] != receipt["status"]:
                recovered.append(updated)
        return recovered

    def submit(self, attempt_id, *, executor=_DEFAULT_HARNESS, executor_name=None, timeout=180):
        chosen = self.default_executor if executor is _DEFAULT_HARNESS else executor
        with self._lock:
            if self._closed:
                raise ValueError("工作台研究执行器已停止")
            future = self._pool.submit(
                execute_attempt,
                self.data_dir,
                attempt_id,
                executor=chosen,
                executor_name=executor_name,
                timeout=timeout,
            )
            self._futures[attempt_id] = future
            future.add_done_callback(lambda _done: self._drop(attempt_id))
            return future

    def wait(self, attempt_id, timeout=None):
        with self._lock:
            future = self._futures.get(attempt_id)
        if future is not None:
            return future.result(timeout=timeout)
        return None

    def _drop(self, attempt_id):
        with self._lock:
            self._futures.pop(attempt_id, None)

    def shutdown(self, *, wait=True):
        with self._lock:
            self._closed = True
        self._pool.shutdown(wait=wait)

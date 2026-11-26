"""A research attempt's OS lock outlives the Roll process while its children are cleaned up."""
from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path


@contextmanager
def attempt_lock(data_dir, attempt_id):
    # The path is also safe for receipts from databases with older identifier formats.
    name = sha256(attempt_id.encode()).hexdigest()
    directory = Path(data_dir) / "research-attempts" / "locks"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / name).open("a+b") as handle:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                yield None
                return
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield None
                return
        # On Linux supervisors inherit the same open file description. Closing the
        # owner's copy must not explicitly unlock it while a supervisor is alive.
        yield handle

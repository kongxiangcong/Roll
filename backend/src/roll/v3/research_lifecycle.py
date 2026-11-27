"""A research attempt's OS lock outlives the Roll process while its children are cleaned up."""
from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path


@contextmanager
def attempt_lock(data_dir, attempt_id, *, children=False, wait=False, observe=False):
    # The path is also safe for receipts from databases with older identifier formats.
    name = sha256(attempt_id.encode()).hexdigest()
    if children:
        name += ".children"
    directory = Path(data_dir) / "research-attempts" / "locks"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / name).open("a+b") as handle:
        acquired = True
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK, 1)
            except OSError:
                acquired = False
        else:
            import fcntl
            try:
                kind = fcntl.LOCK_SH if observe else fcntl.LOCK_EX
                fcntl.flock(handle, kind if wait else kind | fcntl.LOCK_NB)
            except BlockingIOError:
                acquired = False
        # On Linux supervisors inherit the same open file description. Closing the
        # owner's copy must not explicitly unlock it while a supervisor is alive.
        yield handle if acquired else None


class AttemptStopped(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


class ProcessConfigurationError(ValueError):
    pass


def run_process(argv, *, cwd, env, lock, check_state, input=b"", cleanup=()):
    import json
    from tempfile import TemporaryFile
    import subprocess
    import sys

    if sys.platform != "linux":
        raise ProcessConfigurationError("研究进程回收配置要求 Linux")
    supervisor = Path(__file__).with_name("research_supervisor.py").resolve()
    read_fd, write_fd = os.pipe()
    with (os.fdopen(read_fd, "rb") as worker, os.fdopen(write_fd, "wb") as owner,
          TemporaryFile() as status, TemporaryFile() as public_input):
        public_input.write(input)
        public_input.seek(0)
        helper = [sys.executable, "-I", "-S", str(supervisor), str(worker.fileno()), str(status.fileno()), json.dumps(cleanup), *argv]
        check_state()
        with subprocess.Popen(helper, stdin=public_input, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=cwd, env=env, start_new_session=True,
                              pass_fds=(worker.fileno(), status.fileno(), lock.fileno())) as proc:
            worker.close()
            try:
                while True:
                    try:
                        stdout, stderr = proc.communicate(timeout=.1)
                        break
                    except subprocess.TimeoutExpired:
                        check_state()
                check_state()
                status.seek(0)
                outcome = status.read(1024)
            finally:
                # EOF wakes the subreaper on cancellation, timeout and owner SIGKILL.
                owner.close()
                proc.wait()
    if not outcome:
        raise AttemptStopped("interrupted", "进程监护程序意外退出")
    result = json.loads(outcome)
    if "error" in result:
        raise ProcessConfigurationError(f"无法启动研究命令或 Linux 进程监护程序（errno={result['error']}）")
    return subprocess.CompletedProcess(argv, result["returncode"], stdout, stderr)

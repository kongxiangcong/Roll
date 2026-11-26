"""Linux subreaper for a single external research command (invoked with isolated Python)."""
import ctypes
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time


def kill_and_reap():
    # When a direct child dies, its remaining descendants are adopted by this
    # subreaper, including grandchildren that created a new session/process group.
    children = Path("/proc/thread-self/children")
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if not pid:
            for child in children.read_text().split():
                try:
                    os.kill(int(child), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            time.sleep(.005)


def supervise(control, argv, cleanup):
    # PR_SET_CHILD_SUBREAPER. Verify procfs before starting an external process.
    if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError("无法启用 Linux 子进程回收")
    Path("/proc/thread-self/children").read_text()
    disconnected = select.poll()
    disconnected.register(control, select.POLLIN | select.POLLHUP)
    if disconnected.poll(0):
        return None
    child = subprocess.Popen(argv)
    try:
        while child.poll() is None and not disconnected.poll(30):
            pass
        return child.returncode
    finally:
        kill_and_reap()
        if cleanup:
            # A daemon-owned container is outside the Linux subreaper tree.
            removed = subprocess.run(cleanup, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, timeout=15, check=False)
            if removed.returncode:
                raise OSError("无法确认研究容器已清理")


if __name__ == "__main__":
    try:
        message = {"returncode": supervise(int(sys.argv[1]), sys.argv[4:], json.loads(sys.argv[3]))}
    except OSError as error:
        message = {"error": error.errno}
    os.write(int(sys.argv[2]), json.dumps(message).encode())

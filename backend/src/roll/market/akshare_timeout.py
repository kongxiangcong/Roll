"""Apply finite HTTP timeouts to AKShare calls in the current synchronization context."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from threading import Lock
from time import monotonic

_deadline = ContextVar("roll_akshare_deadline", default=None)
_lock = Lock()


def _install(requests):
    # The SDK uses module-level requests.get and does not expose its HTTP session.
    # Other threads/requests retain their original timeout semantics.
    with _lock:
        original = requests.Session.send
        if getattr(original, "_roll_akshare_timeout", False):
            return

        @wraps(original)
        def send(session, request, **kwargs):
            deadline = _deadline.get()
            if deadline is not None:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise TimeoutError("市场请求时限已到")
                requested = kwargs.get("timeout")
                cap = min(22.0, remaining)
                if isinstance(requested, (int, float)):
                    cap = min(cap, requested)
                kwargs["timeout"] = cap
            return original(session, request, **kwargs)

        send._roll_akshare_timeout = True
        requests.Session.send = send


@contextmanager
def bounded_requests(seconds):
    import requests

    _install(requests)
    token = _deadline.set(monotonic() + seconds)
    try:
        yield
    finally:
        _deadline.reset(token)

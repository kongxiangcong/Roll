"""One local background process using the application's durable task lease.

Run ``python -m roll.worker`` beside the API with the same ROLL_DATA_DIR.
The process has no HTTP listener, model selection, or additional task queue.
"""
import asyncio
import signal
import sys

from roll.app import create_app


async def serve():
    loop = asyncio.get_running_loop()
    stopping = asyncio.Event()
    signals = {signal.SIGINT, signal.SIGTERM}
    if hasattr(signal, 'SIGBREAK'):
        signals.add(signal.SIGBREAK)
    for signum in signals:
        signal.signal(signum, lambda *_: loop.call_soon_threadsafe(stopping.set))
    app = create_app(runtime_role='WORKER')
    async with app.router.lifespan_context(app):
        print('ROLL_BACKGROUND_WORKER_RUNNING', flush=True)
        while not stopping.is_set():
            try:
                await asyncio.wait_for(stopping.wait(), timeout=.5)
            except TimeoutError:
                if not app.state.reviews.thread.is_alive():
                    raise RuntimeError('BACKGROUND_WORKER_LOOP_STOPPED')
    print('ROLL_BACKGROUND_WORKER_STOPPED', flush=True)


def main():
    try:
        asyncio.run(serve())
    except Exception as error:
        code = str(error) if str(error) in {
            'BACKGROUND_WORKER_ALREADY_RUNNING', 'BACKGROUND_WORKER_LOOP_STOPPED',
            'UPGRADE_REQUIRES_STOP_ALL_LOCAL_HOSTS', 'STARTUP_BUSY',
            'RESTORE_PENDING_STOP_ALL_LOCAL_HOSTS',
        } else 'BACKGROUND_WORKER_START_OR_RUN_FAILED'
        print(code, file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

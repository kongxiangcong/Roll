"""Use the existing durable worker with explicit store and no model credentials.

Public sources retain their existing configuration and limits. If newly adapted
facts need CODEX, its normal missing-auth path records UNAVAILABLE without send.
No scheduler clock override, replay, backfill, or new automation is installed.
"""
import asyncio
import os
from pathlib import Path
for key in list(os.environ):
    if key.startswith(('ROLL_CODEX_', 'ROLL_DEEPSEEK_')):
        os.environ.pop(key, None)
import roll.app

async def main():
    root=Path('D:/dsh-proj/Roll/.scratch/rv12-daily01')
    app=roll.app.create_app(root,runtime_role='WORKER')
    async with app.router.lifespan_context(app):
        print('RV12_EXISTING_WORKER_RUNNING_NO_MODEL_AUTH',flush=True)
        while app.state.reviews.thread.is_alive():
            await asyncio.sleep(.5)
        raise RuntimeError('BACKGROUND_WORKER_LOOP_STOPPED')

asyncio.run(main())

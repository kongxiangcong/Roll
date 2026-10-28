"""Existing worker on the report acceptance copy; all model auth absent."""
import asyncio
import os
from pathlib import Path
for key in list(os.environ):
    if key.startswith(('ROLL_CODEX_', 'ROLL_DEEPSEEK_')):
        os.environ.pop(key, None)
import roll.app

async def main():
    app=roll.app.create_app(Path('D:/dsh-proj/Roll/.scratch/rv12-real01'),runtime_role='WORKER')
    async with app.router.lifespan_context(app):
        print('RV12_REPORT_WORKER_RUNNING_NO_MODEL_AUTH',flush=True)
        while app.state.reviews.thread.is_alive():
            await asyncio.sleep(.5)
        raise RuntimeError('BACKGROUND_WORKER_LOOP_STOPPED')

asyncio.run(main())

"""Actual WORKER host, with a bounded file-controlled lifecycle for acceptance."""
import asyncio,os
from pathlib import Path
from roll.app import create_app
async def main():
 app=create_app(runtime_role='WORKER')
 async with app.router.lifespan_context(app):
  print('REAL_OBSERVATION_WORKER_ONLINE',flush=True)
  for _ in range(900):
   if Path(os.environ['ROLL_ACCEPTANCE_STOP']).exists():break
   if not app.state.reviews.thread.is_alive():raise RuntimeError('ORIGINAL_WORKER_STOPPED')
   await asyncio.sleep(.1)
 print('REAL_OBSERVATION_WORKER_CLOSED',flush=True)
asyncio.run(main())

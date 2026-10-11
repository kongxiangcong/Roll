import {defineConfig} from '@playwright/test';
import {resolve,delimiter} from 'node:path';
const base=resolve('..');
const stage=process.env.ROLL_FINAL_STAGE!;
const out=resolve('../.scratch/roll-p0/evidence/final-review-fix',stage);
export default defineConfig({testDir:'tests/e2e',testMatch:'final-review.spec.ts',workers:1,outputDir:resolve(out,'artifacts'),
  use:{baseURL:'http://127.0.0.1:5196',channel:'chrome',headless:true},reporter:[['list'],['json',{outputFile:resolve(out,'results.json')}]],
  webServer:[{command:'"D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe" -B -m uvicorn final_review_method_app:factory --factory --host 127.0.0.1 --port 8096',cwd:resolve('../backend'),url:'http://127.0.0.1:8096/api/health',reuseExistingServer:false,
    env:{ROLL_ENV:'test',ROLL_DATA_DIR:resolve(base,'.fr',stage,'api'),PYTHONDONTWRITEBYTECODE:'1',PYTHONPATH:[resolve('../backend/src'),resolve('../backend/tests/support')].join(delimiter)}},
  {command:'npm run dev -- --port 5196',url:'http://127.0.0.1:5196',reuseExistingServer:false,env:{ROLL_API_PORT:'8096'}}]});

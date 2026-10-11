import {defineConfig} from '@playwright/test';
import {resolve} from 'node:path';
const api='http://127.0.0.1:18013',web='http://127.0.0.1:15173';
export default defineConfig({testDir:'tests/e2e',testMatch:'codex-only-scope.spec.ts',workers:1,
  outputDir:'../.scratch/roll-p0/evidence/continuation-2026-10-11/codex-only-scope/browser-results-final',
  use:{baseURL:web,headless:true,channel:'chrome'},reporter:[['list']],webServer:[
    {command:'"D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe" -B -m uvicorn roll.app:create_app --factory --host 127.0.0.1 --port 18013',cwd:resolve('../backend'),url:api+'/api/health',
      env:{ROLL_DATA_DIR:resolve('../.scratch/csbrowser2'),ROLL_ENV:'test',PYTHONPATH:resolve('../backend/src'),PYTHONDONTWRITEBYTECODE:'1'},reuseExistingServer:false},
    {command:'npm run dev -- --port 15173',url:web,env:{ROLL_API_PORT:'18013'},reuseExistingServer:false}
  ]});

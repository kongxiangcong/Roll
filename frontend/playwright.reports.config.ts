import {defineConfig} from '@playwright/test';
import {mkdtempSync} from 'node:fs';
import {resolve} from 'node:path';
const api='8091',web='5291',python='D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe';
const profile=process.env.ROLL_REPORT_PROFILE??mkdtempSync(resolve('../.scratch/t29-browser-'));
const paths=['src','tests/support','tests/application'].map(p=>resolve('../backend',p)).join(';');
export default defineConfig({testDir:'tests/e2e',testMatch:'reports.spec.ts',workers:1,
  use:{baseURL:`http://127.0.0.1:${web}`,headless:true,channel:'chrome'},
  reporter:[['list'],['json',{outputFile:'test-results/reports-results.json'}]],webServer:[
    {command:`"${python}" -B -X utf8 -m uvicorn report_method_app:factory --factory --host 127.0.0.1 --port ${api}`,cwd:resolve('../backend'),url:`http://127.0.0.1:${api}/api/health`,env:{ROLL_DATA_DIR:resolve(profile,'data'),ROLL_ENV:'test',PYTHONDONTWRITEBYTECODE:'1',PYTHONPATH:paths},reuseExistingServer:false},
    {command:`npm run dev -- --port ${web} --config vite.reports.config.ts`,url:`http://127.0.0.1:${web}`,env:{ROLL_API_PORT:api},reuseExistingServer:false}
  ]});

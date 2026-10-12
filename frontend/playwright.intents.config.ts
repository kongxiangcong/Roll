import {defineConfig} from '@playwright/test';
import {resolve} from 'node:path';
const api='8066',web='5266',python=resolve('../backend/.venv/Scripts/python.exe');
const data=resolve(process.env.ROLL_INTENT_DATA??'../t26-browser1/data');
const paths=['src','tests/support','tests/application'].map(p=>resolve('../backend',p)).join(';');
export default defineConfig({testDir:'tests/e2e',testMatch:'intents.spec.ts',workers:1,
  use:{baseURL:`http://127.0.0.1:${web}`,headless:true,channel:'chrome'},
  reporter:[['list'],['json',{outputFile:'test-results/intents-results.json'}]],webServer:[
    {command:`"${python}" -B -X utf8 -m uvicorn intent_method_app:factory --factory --host 127.0.0.1 --port ${api}`,cwd:resolve('../backend'),url:`http://127.0.0.1:${api}/api/health`,env:{ROLL_DATA_DIR:data,ROLL_ENV:'test',PYTHONDONTWRITEBYTECODE:'1',PYTHONPATH:paths},reuseExistingServer:false},
    {command:`npm run dev -- --port ${web}`,url:`http://127.0.0.1:${web}`,env:{ROLL_API_PORT:api},reuseExistingServer:false}
  ]});

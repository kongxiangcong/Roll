import {defineConfig} from '@playwright/test';
import {resolve} from 'node:path';
const apiPort=process.env.ROLL_TEST_API_PORT??'8042',webPort=process.env.ROLL_TEST_WEB_PORT??'5202';
const data=resolve(process.env.ROLL_RISK_DATA??'../backend/.roll-data/acceptance-22-real-final');
const python=resolve('../backend/.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const method=process.env.ROLL_RISK_METHOD==='1';
export default defineConfig({testDir:'tests/e2e',testMatch:'risk-policies-live.spec.ts',workers:1,
  use:{baseURL:`http://127.0.0.1:${webPort}`,headless:true,channel:process.env.ROLL_BROWSER_CHANNEL},
  reporter:[['list'],['json',{outputFile:`test-results/risk-${method?'method':'real'}-results.json`}]],webServer:[
    {command:`"${python}" -m uvicorn ${method?'risk_policy_method_app:factory':'roll.app:create_app'} --factory --host 127.0.0.1 --port ${apiPort}`,cwd:resolve('../backend'),url:`http://127.0.0.1:${apiPort}/api/health`,env:{ROLL_DATA_DIR:data,PYTHONPATH:resolve('../backend/tests/support'),...(method?{ROLL_ENV:'test'}:{})},reuseExistingServer:false},
    {command:`npm run dev -- --port ${webPort}`,url:`http://127.0.0.1:${webPort}`,env:{ROLL_API_PORT:apiPort},reuseExistingServer:false}
  ]});

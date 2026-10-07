import {defineConfig} from '@playwright/test';
import {resolve} from 'node:path';
const apiPort=process.env.ROLL_TEST_API_PORT??'8038',webPort=process.env.ROLL_TEST_WEB_PORT??'5198';
const data=resolve(process.env.ROLL_EXECUTION_DATA??'../backend/.roll-data/acceptance-18-second');
const python=resolve('../backend/.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
export default defineConfig({testDir:'tests/e2e',testMatch:'executions-live.spec.ts',workers:1,
  use:{baseURL:`http://127.0.0.1:${webPort}`,headless:true,channel:process.env.ROLL_BROWSER_CHANNEL},
  reporter:[['list'],['json',{outputFile:'test-results/executions-results.json'}]],webServer:[
    {command:`"${python}" -m uvicorn roll.app:create_app --factory --host 127.0.0.1 --port ${apiPort}`,cwd:resolve('../backend'),url:`http://127.0.0.1:${apiPort}/api/health`,env:{ROLL_DATA_DIR:data},reuseExistingServer:false},
    {command:`npm run dev -- --port ${webPort}`,url:`http://127.0.0.1:${webPort}`,env:{ROLL_API_PORT:apiPort},reuseExistingServer:false}
  ]});

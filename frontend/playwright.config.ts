import {defineConfig} from '@playwright/test';
import {mkdtempSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {delimiter,join,resolve} from 'node:path';
const dataDir=process.env.ROLL_E2E_FILE_DATA_DIR??process.env.ROLL_TEST_DATA_DIR??mkdtempSync(join(tmpdir(),'roll-browser-'));
const python=resolve('../backend/.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const apiPort=process.env.ROLL_TEST_API_PORT??'8010';
const webPort=process.env.ROLL_TEST_WEB_PORT??'5173';
export default defineConfig({testDir:'tests/e2e',testIgnore:'market-overflow.spec.ts',workers:1,use:{baseURL:`http://127.0.0.1:${webPort}`,headless:true,channel:process.env.ROLL_BROWSER_CHANNEL},reporter:[['list'],['json',{outputFile:'test-results/results.json'}]],webServer:[
  {command:`"${python}" -B -m uvicorn ${process.env.ROLL_PLAYWRIGHT_FACTORY??'roll.app:create_app'} --factory --host 127.0.0.1 --port ${apiPort}`,cwd:resolve('../backend'),url:`http://127.0.0.1:${apiPort}/api/health`,env:{ROLL_DATA_DIR:dataDir,ROLL_ENV:'test',PYTHONDONTWRITEBYTECODE:'1',PYTHONPATH:[resolve('../backend/src'),...(process.env.ROLL_BROWSER_METHOD==='1'?[resolve('../backend/tests/support')]:[])].join(delimiter)},reuseExistingServer:false},
  {command:`npm run dev -- --port ${webPort}`,url:`http://127.0.0.1:${webPort}`,env:{ROLL_API_PORT:apiPort},reuseExistingServer:false}
]});

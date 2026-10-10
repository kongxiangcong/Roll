import {defineConfig} from '@playwright/test';
import {resolve} from 'node:path';
export default defineConfig({testDir:'tests/e2e',testMatch:'forward.spec.ts',workers:1,
  use:{baseURL:'http://127.0.0.1:5190',headless:true,channel:'chrome'},reporter:[['list']],
  webServer:[{command:'"D:/dsh-proj/Roll/backend/.venv/Scripts/python.exe" -B -X utf8 -m uvicorn forward_method_app:factory --factory --host 127.0.0.1 --port 8090',
    cwd:resolve('../backend'),url:'http://127.0.0.1:8090/api/health',env:{ROLL_ENV:'test',ROLL_DATA_DIR:process.env.ROLL_TEST_DATA_DIR!,
      ROLL_FORWARD_METHOD_NOW:'2024-12-02T16:00:00+08:00',PYTHONPATH:resolve('../backend/src')+';'+resolve('../backend/tests/support')},reuseExistingServer:false},
  {command:'npm run dev -- --port 5190',url:'http://127.0.0.1:5190',env:{ROLL_API_PORT:'8090'},reuseExistingServer:false}]});

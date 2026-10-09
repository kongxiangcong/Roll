import {defineConfig} from '../../../../frontend/node_modules/@playwright/test/index.mjs';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';
const evidence=dirname(fileURLToPath(import.meta.url));
const root=resolve(evidence,'../../../..');
const directory=resolve(evidence,'.roll-data/public-host-v3');
export default defineConfig({testDir:evidence,testMatch:'public-history.browser.mjs',workers:1,
  use:{baseURL:'http://127.0.0.1:5191',headless:true,channel:'chrome'},
  reporter:[['list'],['json',{outputFile:resolve(evidence,'browser-results.json')}]],
  outputDir:resolve(evidence,'.roll-data/browser-output-v2'),
  webServer:[
    {command:`"${resolve(root,'backend/.venv/Scripts/python.exe')}" -B -X utf8 -m uvicorn roll.app:create_app --factory --host 127.0.0.1 --port 8191`,
      cwd:resolve(root,'backend'),url:'http://127.0.0.1:8191/api/health',reuseExistingServer:false,
      env:{ROLL_ENV:'test',ROLL_DATA_DIR:directory,PYTHONPATH:resolve(root,'backend/src')}},
    {command:`node "${resolve(root,'frontend/node_modules/vite/bin/vite.js')}" --host 127.0.0.1 --port 5191`,
      cwd:resolve(root,'frontend'),url:'http://127.0.0.1:5191',reuseExistingServer:false,env:{ROLL_API_PORT:'8191'}}
  ]});

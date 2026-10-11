/** Isolated three-process acceptance; no source fetch, model or external send. */
import assert from 'node:assert/strict';
import {createWriteStream, mkdirSync, mkdtempSync, writeFileSync, lstatSync, readFileSync} from 'node:fs';
import {join, resolve} from 'node:path';
import {createServer} from 'node:net';
import {createHash} from 'node:crypto';
import {spawn, spawnSync} from 'node:child_process';
import {chromium} from '@playwright/test';

const frontend=resolve(import.meta.dirname,'..');
const repo=resolve(frontend,'..');
const parent=join(repo,'.roll-data','acceptance-31-browser');mkdirSync(parent,{recursive:true});
const root=mkdtempSync(join(parent,'run-'));
const data=join(root,'runtime');
const env={...process.env,ROLL_ENV:'test',ROLL_DATA_DIR:data,ROLL_RUNTIME_ROLE:'API',PYTHONPATH:join(repo,'backend','src')};
for(const key of ['ROLL_ENV_FILE','ROLL_CODEX_AUTH_FILE','ROLL_DEEPSEEK_API_KEY_FILE','DEEPSEEK_API_KEY','OPENAI_API_KEY','FUYAO_API_KEY','ROLL_TEST_CRASH_POINT','ROLL_TEST_BOOTSTRAP_FAULT'])delete env[key];
const python=join(repo,'backend','.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const children=[];
const receipt={started_at:new Date().toISOString(),profile:'ISOLATED_OFFLINE_DELIVERY',data_directory:data,processes:[],checks:{},status:'RUNNING'};
const freePort=()=>new Promise((ok,bad)=>{const server=createServer();server.on('error',bad);server.listen(0,'127.0.0.1',()=>{const port=server.address().port;server.close(()=>ok(port));});});
function launch(role,command,args,cwd,overrides={}){
  const log=createWriteStream(join(root,role+'.log'));
  const child=spawn(command,args,{cwd,env:{...env,...overrides},windowsHide:true,shell:false});
  child.stdout.pipe(log,{end:false});child.stderr.pipe(log,{end:false});
  children.push({child,log});receipt.processes.push({role,launcher_pid:child.pid,command,args,cwd});
  child.on('error',error=>log.write(String(error)));
  return child;
}
async function wait(query,predicate){
  for(let i=0;i<300;i++){
    try{const result=await query();if(predicate(result))return result;}catch{}
    await new Promise(ok=>setTimeout(ok,100));
  }
  throw new Error('DELIVERY_RECEIPT_TIMEOUT');
}
let browser;
try{
  receipt.install_directories=['backend/.venv','frontend/node_modules'].map(path=>({path:join(repo,path),directory:lstatSync(join(repo,path)).isDirectory(),symbolic_link:lstatSync(join(repo,path)).isSymbolicLink()}));
  assert.ok(receipt.install_directories.every(item=>item.directory&&!item.symbolic_link));
  receipt.lockfiles=['backend/uv.lock','frontend/package-lock.json'].map(path=>({path,sha256:createHash('sha256').update(readFileSync(join(repo,path))).digest('hex')}));
  const apiPort=await freePort(),uiPort=await freePort();
  const api=`http://127.0.0.1:${apiPort}`;
  const get=async path=>{const response=await fetch(api+path);assert.equal(response.status,200);return response.json();};
  const post=async(path,body)=>{const response=await fetch(api+path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});assert.ok(response.ok);return response.json();};
  launch('api',python,['-m','uvicorn','roll.app:create_app','--factory','--host','127.0.0.1','--port',String(apiPort)],join(repo,'backend'));
  receipt.api_health=await wait(()=>get('/api/health'),v=>v.status==='ok');
  assert.equal(receipt.api_health.runtime_role,'API');
  assert.equal((await get('/api/reviews/health')).worker_state,'STOPPED');
  launch('worker',python,['-m','roll.worker'],join(repo,'backend'));
  receipt.worker_health=await wait(()=>get('/api/reviews/health'),v=>v.worker_state==='RUNNING');
  const owner=receipt.worker_health.worker.host_owner;
  const ui=launch('ui',process.execPath,[join(frontend,'node_modules','vite','bin','vite.js'),'--host','127.0.0.1','--port',String(uiPort),'--strictPort'],frontend,{ROLL_API_PORT:String(apiPort)});
  await wait(async()=> (await fetch(`http://127.0.0.1:${uiPort}`)).status,v=>v===200);
  browser=await chromium.launch({headless:true,channel:process.env.ROLL_BROWSER_CHANNEL??'chrome'});
  const page=await browser.newPage();await page.goto(`http://127.0.0.1:${uiPort}`);
  await page.getByRole('button',{name:'同步账户',exact:true}).click();
  await page.getByLabel('事实截至时点').fill('2026-10-07T10:00');
  await page.getByLabel('账面现金（元）').fill('1234.56');
  await page.getByRole('button',{name:'预览差异'}).click();
  await page.getByRole('heading',{name:'确认前的差异'}).waitFor();
  await page.getByRole('button',{name:'确认入账'}).click();
  await page.getByRole('heading',{name:'已确认，回执已保存'}).waitFor();
  await page.getByRole('button',{name:'查询回执'}).click();
  await page.getByText('回执查询成功').waitFor();
  await page.screenshot({path:join(root,'receipt.png'),fullPage:true});
  receipt.account=await get('/api/account');assert.equal(receipt.account.version,1);assert.equal(receipt.account.cash_balance,'1234.56');
  await browser.close();browser=null;
  receipt.after_browser_close={api:await get('/api/health'),worker:await get('/api/reviews/health'),ui_running:ui.exitCode===null};
  assert.equal(receipt.after_browser_close.api.status,'ok');
  assert.deepEqual(receipt.after_browser_close.worker.worker.host_owner,owner);
  assert.equal(receipt.after_browser_close.worker.worker_state,'RUNNING');
  const queued=await post('/api/reviews/tasks',{mode:'ON_DEMAND',cutoff:'2026-10-07T02:00:00+00:00',refresh_missing:false});
  receipt.observation=await wait(()=>get('/api/reviews/tasks/'+queued.task_id),v=>v.result!==null);
  assert.equal(receipt.observation.result.forecast,null);
  assert.equal(receipt.observation.result.forward_sample_created,false);
  assert.equal((await get('/api/account')).version,1);
  receipt.coverage=await get('/api/reviews/coverage');
  assert.equal(receipt.coverage.forward_predictions_reconstructed,false);
  receipt.checks={clean_physical_install:true,api_role_does_not_lease:true,independent_worker:true,ui_confirm_and_receipt:true,browser_close_keeps_services:true,offline_observation_without_prediction:true};
  receipt.status='PASS';
}catch(error){receipt.status='FAIL';receipt.error=String(error);process.exitCode=1;}
finally{
  if(browser)await browser.close();
  for(const {child,log} of children.reverse()){
    if(child.exitCode===null&&child.pid){
      if(process.platform==='win32')spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore'});
      else child.kill('SIGTERM');
    }
    log.end();
  }
  receipt.completed_at=new Date().toISOString();writeFileSync(join(root,'receipt.json'),JSON.stringify(receipt,null,2)+'\n');
  console.log(JSON.stringify({status:receipt.status,receipt:join(root,'receipt.json')}));
}

import {mkdirSync,mkdtempSync,readFileSync,writeFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
import {spawn} from 'node:child_process';
import {defaultFiles} from './default-files.mjs';

const selection=process.argv[2];
if(selection==='--list'){console.log(JSON.stringify(defaultFiles));process.exit(0);}
if(process.argv.length>3||(selection&&!selection.startsWith('--file=')))throw new Error('Use --list or --file=<current default file>.');
const files=selection?[selection.slice('--file='.length)]:defaultFiles;
if(files.some(file=>!defaultFiles.includes(file)))throw new Error('File is outside current default acceptance scope.');
const externalFlags=['ROLL_ENV_FILE','ROLL_TEST_DATA_DIR','ROLL_PLAYWRIGHT_FACTORY','ROLL_BROWSER_METHOD',
  'ROLL_LIVE_MARKET','ROLL_LIVE_FALLBACK','ROLL_LIVE_CODEX','ROLL_LIVE_BACKEND_SWITCH','ROLL_DEEPSEEK_METHOD','ROLL_BROWSER_DEEPSEEK_METHOD','ROLL_BROWSER_DEEPSEEK_LIVE',
  'ROLL_RESEARCH_LIVE','ROLL_EXECUTION_LIVE','ROLL_MODEL_LIVE','ROLL_RISK_LIVE',
  'ROLL_BACKUP_BROWSER_PHASE','ROLL_REVIEW_REAL_CACHE','ROLL_REAL_VERIFICATION'];
if(externalFlags.some(key=>process.env[key])){
  throw new Error('Default acceptance needs a fresh profile. Remove external/METHOD/restore flags and use the explicit profiles in docs/browser-acceptance.md.');
}
const defaultRoot=resolve('test-results/default');
mkdirSync(defaultRoot,{recursive:true});
const reportRoot=mkdtempSync(join(defaultRoot,'run-'));
const runtimeParent=resolve('../backend/.roll-data');
mkdirSync(runtimeParent,{recursive:true});
const dataRoot=mkdtempSync(join(runtimeParent,'e2e-default-'));
const profile={...process.env};
// The default suite proves missing-credential behavior and never sends paid model requests.
for(const key of ['ROLL_ENV_FILE','ROLL_CODEX_AUTH_FILE','DEEPSEEK_API_KEY','ROLL_DEEPSEEK_API_KEY_FILE','FUYAO_API_KEY','BAOSTOCK_API_KEY','OPENAI_API_KEY'])delete profile[key];
const results={started_at:new Date().toISOString(),profile:selection?'DEFAULT_OFFLINE_SUBSET':'DEFAULT_OFFLINE',data_root:dataRoot,report_root:reportRoot,
  database_isolation:'PER_FILE; within-file ordered cases share history',files:[]};
let failed=false;
for(const file of files){
  const reportDir=join(reportRoot,file);mkdirSync(reportDir,{recursive:true});
  const dataDir=join(dataRoot,file);mkdirSync(dataDir);
  const stdout=[];
  const started=new Date().toISOString();
  const code=await new Promise(resolveExit=>{
    const child=spawn(process.execPath,[resolve('node_modules/@playwright/test/cli.js'),'test',`${file}.spec.ts`,'--config=playwright.default.config.ts'],
      {cwd:process.cwd(),env:{...profile,ROLL_E2E_FILE_DATA_DIR:dataDir,ROLL_E2E_REPORT_DIR:reportDir,
        ...(file==='codex-only-scope'?{ROLL_PLAYWRIGHT_FACTORY:'codex_scope_method_app:factory',ROLL_BROWSER_METHOD:'1'}:{})},shell:false});
    for(const stream of [child.stdout,child.stderr])stream.on('data',chunk=>{stdout.push(chunk);process.stdout.write(chunk);});
    child.on('error',error=>{stdout.push(Buffer.from(String(error)));resolveExit(1);});
    child.on('close',code=>resolveExit(code??1));
  });
  writeFileSync(join(reportDir,'stdout.txt'),Buffer.concat(stdout));
  let stats=null;
  try{stats=JSON.parse(readFileSync(join(reportDir,'results.json'),'utf8')).stats;}catch{}
  results.files.push({file:`${file}.spec.ts`,data_dir:dataDir,report_dir:reportDir,started_at:started,completed_at:new Date().toISOString(),exit_code:code,stats});
  failed ||= code!==0;
}
results.completed_at=new Date().toISOString();results.exit_code=failed?1:0;
writeFileSync(join(reportRoot,'manifest.json'),JSON.stringify(results,null,2)+'\n');
writeFileSync(join(defaultRoot,'manifest.json'),JSON.stringify(results,null,2)+'\n');
process.exitCode=results.exit_code;

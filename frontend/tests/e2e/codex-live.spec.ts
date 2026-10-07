import {createHash} from 'node:crypto';
import {mkdirSync,writeFileSync} from 'node:fs';
import {expect,test} from '@playwright/test';

test.skip(process.env.ROLL_LIVE_CODEX!=='1','Explicit real ChatGPT Codex runtime acceptance; separate from method cases');
test('real Codex multi-round evidence and cancellation are displayed and archived',async({page})=>{
  test.setTimeout(210000);
  const draft=await (await page.request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{
    effective_at:'2026-10-08T00:00:00+08:00',source:'11 isolated actual runtime acceptance, not user account',
    cash_balance:'10000.00',broker_available:null,broker_frozen:null,withdrawable:null,permission_profile:[],
    positions:[{instrument:'SSE:600519',quantity:'100',sellable_quantity:null,reference_cost:null}]}}})).json();
  expect((await page.request.post('/api/account/confirm',{data:{draft_id:draft.draft_id,idempotency_key:'11-live-browser'}})).ok()).toBeTruthy();
  const before=await (await page.request.get('/api/account')).json();
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByRole('button',{name:'市场事实',exact:true}).click();
  await page.getByLabel('取证方式').selectOption('CODEX');
  await page.getByLabel('报价来源').selectOption('SINA');
  for(const name of ['日线与复权','调整事件','业绩','重大事项','当前状态'])await page.getByRole('checkbox',{name,exact:true}).uncheck();
  await page.getByLabel('开始日期（上海交易/披露日期）').fill('2026-10-07');
  await page.getByLabel('需要补充核对的问题').fill('先取得报价依据，再检查缺口并查公司官方主页。公司主营业务是否有实际原文？分开保留报价、事项时间和公告原文缺口。仅引用来源原文中逐字连续出现的短句，不能拼接或补标点。');
  await page.getByRole('button',{name:'启动 Codex 取证',exact:true}).click();
  await expect(page.getByRole('button',{name:'取消本次取证',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'补充证据候选'})).toBeVisible({timeout:135000});
  const run=(await (await page.request.get('/api/data/runs')).json()).find((r:{backend:string})=>r.backend==='CODEX');
  expect(run.status).toBe('PARTIAL');expect(run.tools.length).toBeGreaterThanOrEqual(2);
  expect(run.archives.some((a:{source_id:string})=>a.source_id==='sina-quote')).toBeTruthy();
  expect(run.runtime_audit.enabled_skills).toBe(0);expect(run.instruction_sources).toEqual([]);
  expect(run.process.remaining_pids).toEqual([]);expect(run.sdk_runtime_version['openai-codex']).toBe('0.161.0');
  const snapshot=await (await page.request.get('/api/data/snapshots/'+run.snapshot_id)).json();
  const directory='../backend/.roll-data/acceptance/codex-browser';mkdirSync(directory,{recursive:true});
  writeFileSync(directory+'/result.json',JSON.stringify({run,snapshot},null,2));
  for(const archive of [...snapshot.archives,snapshot.parquet]){
    const bytes=await (await page.request.get('/api/data/archives/'+archive.sha256)).body();
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(archive.sha256);
    writeFileSync(directory+'/'+archive.sha256+(archive===snapshot.parquet?'.parquet':'.raw'),bytes);
  }
  await page.getByRole('button',{name:'只读归档回放',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'网络调用 0 次'})).toBeVisible();
  await page.screenshot({path:'test-results/11-codex-live.png',fullPage:true});
  expect(await (await page.request.get('/api/account')).json()).toEqual(before);
  await page.getByRole('button',{name:'启动 Codex 取证',exact:true}).click();
  await expect(page.getByRole('button',{name:'取消本次取证',exact:true})).toBeVisible();
  // Wait for an actual SDK turn before testing the product cancellation button.
  await expect.poll(async()=>{
    const runs=await (await page.request.get('/api/data/runs')).json();
    return runs.find((r:{backend:string;status:string})=>r.backend==='CODEX'&&r.status==='RUNNING')?.runtime_turn_id;
  },{timeout:45000}).toBeTruthy();
  await page.getByRole('button',{name:'取消本次取证',exact:true}).click();
  await expect(page.getByText(/获取状态：CANCELLED/)).toBeVisible({timeout:12000});
  const cancelled=(await (await page.request.get('/api/data/runs')).json()).find((r:{backend:string})=>r.backend==='CODEX');
  expect(cancelled.status).toBe('CANCELLED');expect(cancelled.process.remaining_pids).toEqual([]);
  writeFileSync(directory+'/cancelled.json',JSON.stringify(cancelled,null,2));
  await page.screenshot({path:'test-results/11-codex-cancelled.png',fullPage:true});
});

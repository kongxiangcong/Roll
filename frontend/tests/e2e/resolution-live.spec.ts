import {createHash} from 'node:crypto';
import {mkdirSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';
import {expect,test} from '@playwright/test';

test.skip(process.env.ROLL_LIVE_FALLBACK!=='1','Explicit actual public-source switching acceptance');
test('archived Tencent unit gap automatically obtains comparable Sina quote, caches true time, and replays original run',async({page})=>{
  test.setTimeout(90000);
  const account=await (await page.request.get('/api/account')).json();
  if(!account.version){
    const draft=await (await page.request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{
      effective_at:'2026-10-07T00:00:00+08:00',source:'08 isolated synthetic account; not user broker facts',cash_balance:'1000000.00',
      broker_available:null,broker_frozen:null,withdrawable:null,permission_profile:[],
      positions:[{instrument:'SSE:600519',quantity:'100',sellable_quantity:null,reference_cost:null}]}}})).json();
    expect((await page.request.post('/api/account/confirm',{data:{draft_id:draft.draft_id,idempotency_key:'08-browser-baseline'}})).ok()).toBeTruthy();
  }else{
    const listing=await (await page.request.get('/api/market/list')).json();
    if(!listing.members.some((m:{instrument:string})=>m.instrument==='SSE:600519'))
      expect((await page.request.post('/api/market/watch',{data:{operation:'ADD',instrument:'SSE:600519',expected_list_version:listing.version}})).ok()).toBeTruthy();
  }
  expect((await page.request.post('/api/market/identities',{data:{instrument:'SSE:600519',exchange:'SSE',board:'MAIN',instrument_type:'STOCK',
    name:'贵州茅台',basis:'08 isolated acceptance explicitly confirmed SSE MAIN ordinary stock; not real account confirmation',effective_at:'2026-10-07T00:00:00+08:00'}})).ok()).toBeTruthy();
  const before=await (await page.request.get('/api/account')).json();
  const today=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Shanghai'}).format(new Date());
  const command=await (await page.request.post('/api/data/requests',{data:{instruments:['SSE:600519'],groups:['QUOTE'],purpose:'OBSERVATION',
    start_date:'2026-09-30',end_date:today,quote_source:'TENCENT',required_fields:['QUOTE.volume_shares'],max_calls:4,timeout_seconds:40}})).json();
  const primary=await (await page.request.post('/api/data/requests/'+command.request_id+'/retrieve')).json();
  expect(primary.evidence_kind).toBe('REAL_ACQUISITION');
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByRole('button',{name:'市场事实',exact:true}).click();
  await expect(page.getByRole('heading',{name:'用途与换源'})).toBeVisible();
  await page.getByLabel('本次读取用途').selectOption('HISTORICAL_RESEARCH');
  await page.getByRole('button',{name:'按用途检查并补查',exact:true}).click();
  await expect(page.getByRole('heading',{name:'用途与换源结果'})).toBeVisible({timeout:50000});
  await expect(page.getByText('本次用途：HEALTHY',{exact:true})).toBeVisible();
  await expect(page.getByText(/sina-quote ·.*股数 3833098/)).toBeVisible();
  const first=(await (await page.request.get('/api/data/resolutions')).json())[0];
  expect(first.source_checks[0].primary_source).toBe('tencent-quote');expect(first.source_checks[0].decision).toBe('ACCEPTED');
  expect(first.source_checks[0].unit_comparison).toBe('UNKNOWN_PRIMARY_VOLUME_NOT_EXTRAPOLATED');
  expect(first.network_calls).toBe(1);expect(first.attempts[0].cached).toBe(true);
  await page.getByRole('button',{name:'按用途检查并补查',exact:true}).click();
  await expect(page.getByText('沿用原采集时点，本次网络调用 0 次',{exact:true})).toBeVisible({timeout:10000});
  const cached=(await (await page.request.get('/api/data/resolutions')).json())[0];
  expect(cached.facts[0].available_at).toBe(first.facts[0].available_at);
  await page.getByRole('button',{name:'重新取数形成后继记录',exact:true}).click();
  await expect(page.getByText(/后继依据：NEW_RUN_NO_NORMALIZED_FACT_CHANGE/)).toBeVisible({timeout:50000});
  const revised=(await (await page.request.get('/api/data/resolutions')).json())[0];
  await page.getByLabel('选择用途记录').selectOption(first.resolution_id);
  await page.getByRole('button',{name:'重放原输入',exact:true}).click();
  await expect(page.getByText(/原用途状态 HEALTHY.*网络调用 0 次/)).toBeVisible();
  expect(await (await page.request.get('/api/account')).json()).toEqual(before);
  const exportDir='../backend/.roll-data/acceptance-08-browser';mkdirSync(exportDir,{recursive:true});
  const runs=[];
  for(const id of new Set([primary.run_id,...first.attempts.map((a:{run_id:string})=>a.run_id),...revised.attempts.map((a:{run_id:string})=>a.run_id)])){
    const run=await (await page.request.get('/api/data/runs/'+id)).json();const snapshot=await (await page.request.get('/api/data/snapshots/'+run.snapshot_id)).json();
    for(const archive of [...snapshot.archives,snapshot.parquet]){
      const response=await page.request.get('/api/data/archives/'+archive.sha256);const bytes=await response.body();
      expect(response.headers()['content-disposition']).toContain('attachment');expect(response.headers()['x-content-type-options']).toBe('nosniff');
      expect(createHash('sha256').update(bytes).digest('hex')).toBe(archive.sha256);
      writeFileSync(join(exportDir,archive.sha256+(archive===snapshot.parquet?'.parquet':'.raw')),bytes);
    }runs.push({run,snapshot});
  }
  writeFileSync(join(exportDir,'live-closure.json'),JSON.stringify({request:command,first,cached,revised,runs},null,2));
  await page.screenshot({path:'test-results/08-source-resolution.png',fullPage:true});
});

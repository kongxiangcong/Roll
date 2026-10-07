import {createHash} from 'node:crypto';
import {writeFileSync,mkdirSync} from 'node:fs';
import {join} from 'node:path';
import {expect,test} from '@playwright/test';

test.skip(process.env.ROLL_LIVE_MARKET!=='1','Explicit live public-source acceptance; not a deterministic suite fixture');
test('real finite-name market request archives all groups and page displays actual sources, gaps and offline replay',async({page})=>{
  test.setTimeout(90000);
  const account=await (await page.request.get('/api/account')).json();
  if(account.version===0){
    const draft=await (await page.request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{
      effective_at:'2026-10-07T00:00:00+08:00',source:'07 isolated acceptance account, not real user broker holdings',
      cash_balance:'10000.00',broker_available:null,broker_frozen:null,withdrawable:null,permission_profile:[],
      positions:[{instrument:'SSE:600519',quantity:'100',sellable_quantity:null,reference_cost:null}]}}})).json();
    expect((await page.request.post('/api/account/confirm',{data:{draft_id:draft.draft_id,idempotency_key:'07-browser-baseline'}})).ok()).toBeTruthy();
  }else{
    const listing=await (await page.request.get('/api/market/list')).json();
    if(!listing.members.some((m:{instrument:string})=>m.instrument==='SSE:600519'))
      expect((await page.request.post('/api/market/watch',{data:{operation:'ADD',instrument:'SSE:600519',expected_list_version:listing.version}})).ok()).toBeTruthy();
  }
  await page.request.post('/api/market/identities',{data:{instrument:'SSE:600519',exchange:'SSE',board:'MAIN',instrument_type:'STOCK',
    name:'贵州茅台',basis:'07隔离取证验收明确SSE主板普通股票；不代替用户真实账户确认',effective_at:'2026-10-07T00:00:00+08:00'}});
  const before=await (await page.request.get('/api/account')).json();
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByRole('button',{name:'市场事实',exact:true}).click();
  await expect(page.getByRole('heading',{name:'市场事实',exact:true})).toBeVisible();
  // Request one explicit stock, without accidentally expanding to other acceptance holdings.
  const checkboxes=page.getByRole('group',{name:/请求对象/}).getByRole('checkbox');
  for(let n=0;n<await checkboxes.count();n++){
    const box=checkboxes.nth(n);const label=await box.locator('..').textContent();
    await box.setChecked(label?.includes('SSE:600519')??false);
  }
  await page.getByLabel('开始日期（上海交易/披露日期）').fill('2026-01-01');
  await page.getByLabel('截止日期',{exact:true}).fill('2026-09-30');
  await page.getByLabel('日线来源').selectOption('TENCENT');
  await page.getByRole('button',{name:'取得并归档事实',exact:true}).click();
  await expect(page.getByRole('heading',{name:'归档事实与客观观察'})).toBeVisible({timeout:65000});
  const run=(await (await page.request.get('/api/data/runs')).json())[0];
  const snapshot=await (await page.request.get('/api/data/snapshots/'+run.snapshot_id)).json();
  const runtimeArchive='../backend/.roll-data/acceptance-07-browser';mkdirSync(runtimeArchive,{recursive:true});
  const publicRequest=await (await page.request.get('/api/data/requests/'+run.request_id)).json();
  writeFileSync(join(runtimeArchive,'browser-live.json'),JSON.stringify({request:publicRequest,run,snapshot},null,2));
  expect(run.evidence_kind).toBe('REAL_ACQUISITION');
  expect(new Set(snapshot.facts.map((f:{group:string})=>f.group))).toEqual(new Set(['DAILY','QUOTE','ADJUSTMENTS','ANNOUNCEMENTS','PERFORMANCE','MAJOR_EVENTS','STATUS']));
  expect(run.gaps.some((g:{code:string})=>g.code==='CURRENT_STATUS_UNKNOWN')).toBeTruthy();
  const quote=snapshot.facts.find((f:{group:string})=>f.group==='QUOTE');
  expect(quote.upstream_at.startsWith('2026-09-30')).toBeTruthy();expect(quote.received_at).not.toEqual(quote.upstream_at);
  expect(snapshot.facts.some((f:{group:string;volume_shares:string|null;amount_yuan:string|null})=>f.group==='DAILY'&&f.volume_shares&&f.amount_yuan)).toBeTruthy();
  for(const archive of [...snapshot.archives,snapshot.parquet]){
    const bytes=await (await page.request.get('/api/data/archives/'+archive.sha256)).body();
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(archive.sha256);
    writeFileSync(join(runtimeArchive,archive.sha256+(archive===snapshot.parquet?'.parquet':'.raw')),bytes);
  }
  await expect(page.getByText('SSE:600519 · 当前状态：CURRENT_STATUS_UNKNOWN')).toBeVisible();
  await page.getByRole('button',{name:'只读归档回放',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'网络调用 0 次'})).toBeVisible();
  expect(await (await page.request.get('/api/account')).json()).toEqual(before);
  await page.getByText(/^可得报价：/).click();
  await expect(page.getByText(/可得报价 .*上游/)).toBeVisible();
  await page.screenshot({path:'test-results/07-live-market-facts.png',fullPage:true});
});

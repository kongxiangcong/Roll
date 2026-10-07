import {expect,test} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';
import {join} from 'node:path';

test.skip(process.env.ROLL_BROWSER_METHOD!=='1','Explicit isolated source method factory required');
test('method source status gap keeps known quote, revision invalidates old basis and page replays original state',async({page})=>{
  const draft=await (await page.request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{
    effective_at:'2026-10-07T00:00:00+08:00',source:'08 METHOD_CASE synthetic account',cash_balance:'10000',
    broker_available:null,broker_frozen:null,withdrawable:null,permission_profile:[],positions:[{instrument:'SSE:600519',quantity:'100',sellable_quantity:null,reference_cost:null}]}}})).json();
  expect((await page.request.post('/api/account/confirm',{data:{draft_id:draft.draft_id,idempotency_key:'method08-baseline'}})).ok()).toBeTruthy();
  expect((await page.request.post('/api/market/identities',{data:{instrument:'SSE:600519',exchange:'SSE',board:'MAIN',instrument_type:'STOCK',
    name:'贵州茅台',basis:'Explicit method identity',effective_at:'2026-10-07T00:00:00+08:00'}})).ok()).toBeTruthy();
  const request=await (await page.request.post('/api/data/requests',{data:{instruments:['SSE:600519'],groups:['QUOTE','STATUS'],
    purpose:'OBSERVATION',start_date:'2026-09-30',end_date:'2026-09-30',quote_source:'SINA',required_fields:['QUOTE.last'],max_calls:2}})).json();
  const run=await (await page.request.post('/api/data/requests/'+request.request_id+'/retrieve')).json();
  expect(run.evidence_kind).toBe('METHOD_CASE');
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  await page.getByRole('button',{name:'市场事实',exact:true}).click();
  const resolution=page.getByRole('heading',{name:'用途与换源',exact:true}).locator('..');
  await page.getByLabel('本次读取用途').selectOption('HISTORICAL_RESEARCH');
  await page.getByRole('button',{name:'按用途检查并补查'}).click();
  await expect(page.getByText('本次用途：DEGRADED',{exact:true})).toBeVisible();
  await expect(page.getByText('固定方法样本，仅证明受控错误/修订/等待路径。')).toBeVisible();
  await expect(resolution.locator('.market-member').filter({hasText:'报价 1258.620'})).toBeVisible();
  const first=await page.getByLabel('选择用途记录').inputValue();
  expect((await page.request.post('/api/__method/price',{data:{value:'1259.620'}})).ok()).toBeTruthy();
  await page.getByRole('button',{name:'重新取数形成后继记录'}).click();
  await expect(page.getByText(/后继依据：FACT_VALUE_OR_SEMANTICS_REVISED/)).toBeVisible();
  await expect(resolution.locator('.market-member').filter({hasText:'报价 1259.620'})).toBeVisible();
  const revised=await page.getByLabel('选择用途记录').inputValue();
  await page.getByLabel('选择用途记录').selectOption(first);
  await expect(page.getByText('该旧派生依据已失效；原输入与当时状态继续保留。')).toBeVisible();
  await page.getByRole('button',{name:'重放原输入',exact:true}).click();
  await expect(page.getByText('原用途状态 DEGRADED，网络调用 0 次',{exact:true})).toBeVisible();
  await expect(resolution.locator('.market-member').filter({hasText:'报价 1258.620'})).toBeVisible();
  mkdirSync('test-results',{recursive:true});
  writeFileSync(join('test-results','08-method-revision.json'),JSON.stringify({evidence_kind:'METHOD_CASE',request,run,
    original:await (await page.request.get('/api/data/resolutions/'+first)).json(),
    revised:await (await page.request.get('/api/data/resolutions/'+revised)).json()},null,2));
  await page.screenshot({path:join('test-results','08-method-revision.png'),fullPage:true});
});

import {expect,test} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';

test.skip(process.env.ROLL_BROWSER_METHOD!=='1','Explicit METHOD_CASE originals factory required');
test('decisive originals verify once, source revision invalidates reuse and conflicting price keeps both values',async({page})=>{
  const listing=await (await page.request.get('/api/market/list')).json();
  expect((await page.request.post('/api/market/watch',{data:{operation:'ADD',instrument:'SSE:600519',expected_list_version:listing.version}})).ok()).toBeTruthy();
  async function acquire(){
    const request=await (await page.request.post('/api/data/requests',{data:{instruments:['SSE:600519'],groups:['QUOTE'],purpose:'OBSERVATION',start_date:'2026-09-30',end_date:'2026-09-30'}})).json();
    const run=await (await page.request.post('/api/data/requests/'+request.request_id+'/retrieve')).json();return {request,run};
  }
  const a=await acquire();
  await page.request.post('/api/__method/original',{data:{origin:'B:second',price:'100.000'}});
  const b=await acquire();
  async function resolve(data:unknown){const start=await (await page.request.post('/api/data/requests/'+b.request.request_id+'/resolve',{data})).json();
    let value:any;await expect.poll(async()=>{value=await(await page.request.get('/api/data/resolutions/'+start.resolution_id)).json();return value.status;}).not.toBe('RUNNING');return value;}
  const basis=await resolve({usage:'HISTORICAL_RESEARCH',allow_fallback:false,basis_run_id:b.run.run_id});
  await page.goto('/');await page.getByRole('button',{name:'历史记录',exact:true}).click();await page.getByRole('button',{name:'关键复盘',exact:true}).click();
  await page.getByLabel('疑点及其如何影响结论').fill('METHOD_CASE 收盘价格决定重大盈亏归因');
  await page.getByLabel(new RegExp(a.run.snapshot_id.slice(0,8))).check();await page.getByLabel(new RegExp(b.run.snapshot_id.slice(0,8))).check();
  await page.getByRole('button',{name:'核验决定性事实',exact:true}).click();
  await expect(page.getByRole('heading',{name:'当前核验：已核验',exact:true})).toBeVisible();
  await expect(page.getByText('固定方法核验：独立依据为合成测试材料，不表示真实市场多源核验通过。')).toBeVisible();
  const first=await page.getByLabel('选择已存核验').inputValue();
  await page.getByRole('button',{name:'核验决定性事实',exact:true}).click();await expect(page.getByText('复用同证据版本核验 '+first,{exact:true})).toBeVisible();
  await page.request.post('/api/__method/original',{data:{origin:'B:revised',price:'101.000'}});
  const revision=await resolve({usage:'HISTORICAL_RESEARCH',allow_fallback:false,use_cache:false,revision_of:basis.resolution_id});
  const newRun=await (await page.request.get('/api/data/runs/'+revision.attempts[0].run_id)).json();
  await page.getByRole('button',{name:'刷新证据与核验',exact:true}).click();await page.getByLabel('选择已存核验').selectOption(first);
  await expect(page.getByText(/该核验依据已失效或无法读取，相关归因暂缓/)).toBeVisible();
  await page.getByRole('button',{name:'重放原核验',exact:true}).click();await expect(page.getByText('原记录已核验，网络调用 0 次',{exact:true})).toBeVisible();
  await page.getByLabel(new RegExp(b.run.snapshot_id.slice(0,8))).uncheck();await page.getByLabel(new RegExp(newRun.snapshot_id.slice(0,8))).check();
  await page.getByRole('button',{name:'核验决定性事实',exact:true}).click();await expect(page.getByRole('heading',{name:'当前核验：存在冲突',exact:true})).toBeVisible();
  await expect(page.getByText(/原值 100.000 · 单位 CNY/)).toBeVisible();await expect(page.getByText(/原值 101.000 · 单位 CNY/)).toBeVisible();
  mkdirSync('test-results',{recursive:true});writeFileSync('test-results/14-method.json',JSON.stringify({evidence_kind:'METHOD_CASE',first,revision,records:await(await page.request.get('/api/data/verifications')).json()},null,2));
  await page.screenshot({path:'test-results/14-method.png',fullPage:true});
});

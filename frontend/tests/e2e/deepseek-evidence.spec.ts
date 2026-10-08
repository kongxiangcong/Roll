import {expect,test} from '@playwright/test';
import {writeFileSync} from 'node:fs';

test('DeepSeek missing credential record and linked retry survive reload',async({page})=>{
  test.skip(process.env.ROLL_BROWSER_DEEPSEEK_METHOD==='1','separate real SDK fixed-provider path');
  await establish(page);
  const selection=await (await page.request.get('/api/agents/settings')).json();
  await page.request.post('/api/agents/settings',{data:{expected_version:selection.version,backend:'DEEPSEEK'}});
  await page.getByLabel('取证方式').selectOption('DEEPSEEK');
  await page.getByLabel('需要补充核对的问题').fill('核对报价来源');
  await page.getByRole('button',{name:'启动 DeepSeek 取证',exact:true}).click();
  await expect(page.getByText(/获取状态：UNAVAILABLE/)).toBeVisible();
  await expect(page.getByRole('alert').filter({hasText:'DEEPSEEK_AUTH_NOT_CONFIGURED'})).toBeVisible();
  const first=await (await page.request.get('/api/data/runs')).json();
  await page.getByRole('button',{name:'重新尝试本次请求'}).click();
  await expect(page.getByText(/关联原运行/)).toBeVisible();
  const runs=await (await page.request.get('/api/data/runs')).json();
  expect(runs[0].retry_of).toBe(first[0].run_id);
  writeFileSync('test-results/deepseek-no-auth-runs.json',JSON.stringify(runs,null,2));
  await page.reload();await openEvidence(page);
  await expect(page.getByText(/获取状态：UNAVAILABLE/)).toBeVisible();
  await page.getByText('后端与运行配置').click();
  await expect(page.getByText(/DeepSeek · 模型 deepseek-flash/)).toBeVisible();
  await page.screenshot({path:'test-results/deepseek-no-auth.png',fullPage:true});
});

test('actual Agents SDK fixed Responses task displays evidence and cancels independent next run',async({page})=>{
  test.skip(process.env.ROLL_BROWSER_DEEPSEEK_METHOD!=='1','explicit fixed HTTP provider factory required');
  await establish(page);
  await page.getByLabel('取证方式').selectOption('DEEPSEEK');
  await page.getByLabel('报价来源').selectOption('SINA');
  await page.getByLabel('需要补充核对的问题').fill('三轮方法案例核对报价与官方补充');
  await page.getByRole('button',{name:'启动 DeepSeek 取证',exact:true}).click();
  await expect(page.getByText(/获取状态：PARTIAL/)).toBeVisible({timeout:30000});
  await expect(page.getByRole('heading',{name:'补充证据候选'})).toBeVisible();
  await expect(page.getByText('贵州茅台公开材料 METHOD_CASE',{exact:true})).toBeVisible();
  await expect(page.getByText(/固定方法样本/)).toBeVisible();
  await page.getByText('后端与运行配置').click();
  await expect(page.getByText(/openai-agents/)).toBeVisible();
  await page.getByText('来源与工具记录',{exact:true}).click();
  await expect(page.getByText(/roll_read_source · ARCHIVED/)).toBeVisible();
  const first=(await (await page.request.get('/api/data/runs')).json()).find((r:{backend:string})=>r.backend==='DEEPSEEK');
  expect(first.model_requests).toHaveLength(3);expect(first.process.remaining_pids).toEqual([]);
  writeFileSync('test-results/deepseek-method-run.json',JSON.stringify(first,null,2));
  expect((await page.request.get('/api/data/archives/'+first.candidates[0].raw_hash)).ok()).toBeTruthy();
  await page.screenshot({path:'test-results/deepseek-method-evidence.png',fullPage:true});
  await page.getByLabel('需要补充核对的问题').fill('WAIT_METHOD');
  await page.getByRole('button',{name:'启动 DeepSeek 取证',exact:true}).click();
  await expect(page.getByRole('button',{name:'取消本次取证'})).toBeVisible();
  await page.getByRole('button',{name:'取消本次取证'}).click();
  await expect(page.getByText(/获取状态：CANCELLED/)).toBeVisible({timeout:10000});
  await page.reload();await openEvidence(page);
  await expect(page.getByText(/获取状态：CANCELLED/)).toBeVisible();
});

async function openEvidence(page:import('@playwright/test').Page){
  await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  await page.getByRole('button',{name:'市场事实',exact:true}).click();
}

async function establish(page:import('@playwright/test').Page){
  const account=await (await page.request.get('/api/account')).json();
  if(account.version===0){
    const draft=await (await page.request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{
      effective_at:'2026-10-08T00:00:00+08:00',source:'12 isolated browser acceptance',cash_balance:'10000.00',
      broker_available:null,broker_frozen:null,withdrawable:null,permission_profile:[],
      positions:[{instrument:'SSE:600519',quantity:'100',sellable_quantity:null,reference_cost:null}]}}})).json();
    expect((await page.request.post('/api/account/confirm',{data:{draft_id:draft.draft_id,idempotency_key:'12-baseline'}})).ok()).toBeTruthy();
  }
  await page.goto('/');await openEvidence(page);
}

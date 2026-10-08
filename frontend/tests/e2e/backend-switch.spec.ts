import {expect,test} from '@playwright/test';

test('saved backend survives reload and creates a separate cross-backend retry',async({page})=>{
  test.skip(process.env.ROLL_LIVE_BACKEND_SWITCH==='1','separate actual runtime evidence view');
  const draft=await (await page.request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{effective_at:'2026-10-08T00:00:00+08:00',source:'13 isolated browser account',cash_balance:'10000.00',broker_available:null,broker_frozen:null,withdrawable:null,permission_profile:[],positions:[{instrument:'SSE:600519',quantity:'100',sellable_quantity:null,reference_cost:null}]}}})).json();
  expect((await page.request.post('/api/account/confirm',{data:{draft_id:draft.draft_id,idempotency_key:'13-browser-baseline'}})).ok()).toBeTruthy();
  await page.goto('/');await page.getByRole('button',{name:'设置',exact:true}).click();
  await page.getByLabel('取证后端',{exact:true}).selectOption('DEEPSEEK');await page.getByRole('button',{name:'保存取证后端',exact:true}).click();
  await expect(page.getByText('已保存：DeepSeek · 设置版本 1')).toBeVisible();
  await page.reload();await page.getByRole('button',{name:'设置',exact:true}).click();await expect(page.getByLabel('取证后端',{exact:true})).toHaveValue('DEEPSEEK');
  await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByRole('button',{name:'市场事实',exact:true}).click();
  await page.getByLabel('取证方式').selectOption('AGENT');await page.getByRole('button',{name:'启动设置后端取证',exact:true}).click();
  await expect(page.getByText(/获取状态：UNAVAILABLE/)).toBeVisible();await expect(page.getByRole('alert').filter({hasText:'DEEPSEEK_AUTH_NOT_CONFIGURED'})).toBeVisible();
  const original=(await (await page.request.get('/api/data/runs')).json())[0];
  await page.getByRole('button',{name:'设置',exact:true}).click();await page.getByLabel('取证后端',{exact:true}).selectOption('CODEX');await page.getByRole('button',{name:'保存取证后端',exact:true}).click();
  await expect(page.getByText('已保存：Codex · 设置版本 2')).toBeVisible();
  await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByRole('button',{name:'市场事实',exact:true}).click();
  await page.getByRole('button',{name:'重新尝试本次请求',exact:true}).click();await expect(page.getByText(/关联原运行/)).toBeVisible();
  await expect(page.getByRole('alert').filter({hasText:'CODEX_AUTH_NOT_CONFIGURED'})).toBeVisible();
  const retry=(await (await page.request.get('/api/data/runs')).json())[0];expect(retry.backend).toBe('CODEX');expect(retry.backend_settings.version).toBe(2);expect(retry.retry_of).toBe(original.run_id);
  expect(await (await page.request.get('/api/data/runs/'+original.run_id)).json()).toEqual(original);
  await page.screenshot({path:'test-results/13-backend-settings.png',fullPage:true});
});

test('actual archived switch identities and reused sources survive reopening',async({page})=>{
  test.skip(process.env.ROLL_LIVE_BACKEND_SWITCH!=='1','explicit actual runtime directory required');
  await page.goto('/');await page.getByRole('button',{name:'设置',exact:true}).click();await expect(page.getByLabel('取证后端',{exact:true})).toBeVisible();
  await page.screenshot({path:'test-results/13-live-settings.png',fullPage:true});
  await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByRole('button',{name:'市场事实',exact:true}).click();
  const runs=await (await page.request.get('/api/data/runs')).json();const retry=runs.find((r:{retry_of?:string})=>r.retry_of);expect(retry).toBeTruthy();
  await page.getByLabel('选择归档运行').selectOption(retry.run_id);await expect(page.getByText('关联原运行：'+retry.retry_of+'；原记录保留。')).toBeVisible();
  await page.getByText('后端与运行配置',{exact:true}).click();await expect(page.getByText(new RegExp('设置版本 '+retry.backend_settings.version))).toBeVisible();
  await page.getByText('来源与工具记录',{exact:true}).click();await expect(page.getByText(/REUSED_ARCHIVE/).first()).toBeVisible();
  await page.screenshot({path:'test-results/13-live-retry.png',fullPage:true});await page.getByLabel('选择归档运行').selectOption(retry.retry_of);
  await expect(page.getByText(/获取状态：CANCELLED/)).toBeVisible();await page.screenshot({path:'test-results/13-live-original.png',fullPage:true});
});

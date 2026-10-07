import {expect,test} from '@playwright/test';

test('Codex host configuration and missing login are visible without losing the run',async({page})=>{
  const account=await (await page.request.get('/api/account')).json();
  if(account.version===0){
    const draft=await (await page.request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{
      effective_at:'2026-10-08T00:00:00+08:00',source:'11 isolated browser method case',cash_balance:'10000.00',
      broker_available:null,broker_frozen:null,withdrawable:null,permission_profile:[],
      positions:[{instrument:'SSE:600519',quantity:'100',sellable_quantity:null,reference_cost:null}]}}})).json();
    expect((await page.request.post('/api/account/confirm',{data:{draft_id:draft.draft_id,idempotency_key:'11-baseline'}})).ok()).toBeTruthy();
  }
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  await page.getByRole('button',{name:'市场事实',exact:true}).click();
  await page.getByLabel('取证方式').selectOption('CODEX');
  await page.getByLabel('需要补充核对的问题').fill('报价来源和事项时间有什么缺口？');
  await page.getByRole('button',{name:'启动 Codex 取证',exact:true}).click();
  await expect(page.getByText(/获取状态：UNAVAILABLE/)).toBeVisible();
  await expect(page.getByRole('alert').filter({hasText:'CODEX_AUTH_NOT_CONFIGURED'})).toBeVisible();
  await page.getByText('后端与运行配置').click();
  await expect(page.getByText(/gpt-6.1-sol/)).toBeVisible();
  await page.reload();await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  await page.getByRole('button',{name:'市场事实',exact:true}).click();
  await expect(page.getByText(/获取状态：UNAVAILABLE/)).toBeVisible();
});

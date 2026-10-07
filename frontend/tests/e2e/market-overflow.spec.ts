import {expect,test} from '@playwright/test';

test('21 actual holdings remain visible while new watch admission is limited',async({page})=>{
  const draft=await (await page.request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{
    effective_at:'2026-10-07T00:00:00+08:00',source:'21-holding acceptance snapshot',cash_balance:'10000.00',
    broker_available:null,broker_frozen:null,withdrawable:null,permission_profile:[],
    positions:Array.from({length:21},(_,n)=>({instrument:`BSE:${920000+n}`,quantity:'100',sellable_quantity:null,reference_cost:null}))}}})).json();
  expect((await page.request.post('/api/account/confirm',{data:{draft_id:draft.draft_id,idempotency_key:'overflow-browser'}})).ok()).toBeTruthy();
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  await expect(page.getByRole('alert')).toHaveText('名单超过 20 只，全部真实资产继续展示；新增关注暂受限。');
  await expect(page.getByRole('article')).toHaveCount(21);
  await expect(page.getByRole('article',{name:'BSE:920020'}).getByText('实际持仓 100 股 · 可卖 未知')).toBeVisible();
  await page.getByLabel('关注代码').fill('600519');await page.getByRole('button',{name:'添加关注',exact:true}).click();
  await expect(page.getByRole('alert').filter({hasText:'WATCH_LIMIT'})).toBeVisible();
  await expect(page.getByRole('article')).toHaveCount(21);
  await page.screenshot({path:'test-results/market-21-holdings.png',fullPage:true});
});

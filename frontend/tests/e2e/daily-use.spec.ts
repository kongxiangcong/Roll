import {expect,test} from '@playwright/test';

test('daily use records Jiangxi buy and sell without model qualification',async({page,request})=>{
  const draft=await (await request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{
    effective_at:'2026-10-07T10:00:00+08:00',source:'隔离浏览器验收账户',cash_balance:'100000.00',
    broker_available:'100000.00',broker_frozen:'0.00',withdrawable:null,positions:[],permission_profile:[]
  }}})).json();
  expect((await request.post('/api/account/confirm',{data:{draft_id:draft.draft_id,idempotency_key:'daily-baseline'}})).ok()).toBeTruthy();
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'江西铜业 · 日常使用'})).toBeVisible();
  await expect(page.getByRole('region',{name:'日常观察状态'})).toBeVisible();
  for(const [direction,price,day] of [['BUY','10.00','08'],['SELL','11.00','09']]){
    await page.getByRole('button',{name:'记录实际买卖',exact:true}).click();
    await expect(page.getByLabel('成交证券代码')).toHaveValue('600362');
    await page.getByLabel('实际成交数量').fill('300');
    await page.getByLabel('原始成交价格（元）').fill(price);
    await page.getByLabel('成交方向').selectOption(direction);
    await page.getByLabel('实际发生时点').fill(`2026-10-${day}T10:00`);
    await page.getByLabel('实际费用（元）',{exact:true}).fill('5.00');
    await page.getByLabel('费用依据').fill('隔离验收成交回报');
    await page.getByRole('button',{name:'预览成交差异'}).click();
    await page.getByRole('button',{name:'确认实际成交'}).click();
    await expect(page.getByRole('heading',{name:'实际成交已确认，回执已保存'})).toBeVisible();
    await page.getByRole('button',{name:'回到今天'}).click();
  }
  await page.reload();
  await expect(page.getByRole('heading',{name:'江西铜业 · 日常使用'})).toBeVisible();
  const account=await (await request.get('/api/account')).json();
  expect(account.cash_balance).toBe('100290.00');
  expect(account.fills).toHaveLength(2);
  expect((await (await request.get('/api/today')).json()).technical_capability.state).toBe('UNGRANTED');
  await page.getByRole('button',{name:'查看成交与复盘记录'}).click();
  await expect(page.getByText('SSE:600362').first()).toBeVisible();
  await page.screenshot({path:'test-results/daily-use-history.png',fullPage:true});
});

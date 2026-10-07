import {expect,test} from '@playwright/test';

test('user confirms funds and sees independent funding, technical and runtime states', async ({page})=>{
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'资金授权',exact:true})).toBeVisible();
  await expect(page.getByText('资金边界尚未确认',{exact:true})).toBeVisible();
  const account = await (await page.request.get('/api/account')).json();
  if(account.version===0){
    const draft=await (await page.request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{effective_at:'2026-10-07T10:00:00+08:00',source:'合成浏览器验收',cash_balance:'100000.00',broker_available:'100000.00',broker_frozen:'0.00',withdrawable:null,positions:[],permission_profile:[]}}})).json();
    await page.request.post('/api/account/confirm',{data:{draft_id:draft.draft_id,idempotency_key:'funding-browser-baseline'}});
  }
  await page.getByRole('button',{name:'设置',exact:true}).click();
  await page.getByLabel('资金用途',{exact:true}).fill('本人普通账户');
  await page.getByLabel('资金金额（元）').fill('100000');
  await page.getByLabel('总暴露上限（元）').fill('60000');
  await page.getByLabel('单票暴露上限（元）').fill('20000');
  await page.getByLabel('现金保留额（元）').fill('40000');
  await page.getByLabel('损失暂停阈值（元）').fill('5000');
  await page.getByLabel('确认依据').fill('本人确认合成测试金额');
  await page.getByLabel('允许在此资金边界内使用').check();
  await page.getByRole('button',{name:'确认资金边界',exact:true}).click();
  await expect(page.getByText('资金授权版本 1',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'今天',exact:true}).click();
  await expect(page.getByText('资金边界已确认',{exact:true})).toBeVisible();
  await expect(page.getByText('技术资格未授予',{exact:true})).toBeVisible();
  await expect(page.getByText('账户服务在线',{exact:true})).toBeVisible();
  await expect(page.getByText('损失与剩余额度待核：实际估值及现金流尚未接入',{exact:true})).toBeVisible();
  await page.screenshot({path:'test-results/funding-three-states.png',fullPage:true});
  await page.getByRole('button',{name:'设置',exact:true}).click();
  await page.getByLabel('暂停此资金用途').check();
  await page.getByRole('button',{name:'确认资金边界',exact:true}).click();
  await expect(page.getByText('资金用途已暂停',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'查看资金授权版本 1'}).click();
  await expect(page.getByText('历史资金用途：本人普通账户 · 100000.00 元 · CONFIRMED')).toBeVisible();
  await page.getByRole('button',{name:'今天',exact:true}).click();
  await expect(page.getByText('账面现金')).toBeVisible();
  const rejected=await page.request.post('/api/formal/evaluate',{data:{action:'HOLD',mode:'FORMAL',llm_confidence:'0.99'}});
  expect(rejected.status()).toBe(403);
});

import {expect,test} from '@playwright/test';

test('actual fill with provisional fees can be confirmed and later adjusted without inventing an action',async({page,request})=>{
  const account=await (await request.get('/api/account')).json();
  if(account.version===0){
    const input={kind:'BASELINE',expected_account_version:0,payload:{effective_at:'2026-10-07T10:00:00+08:00',source:'浏览器脱敏账户',cash_balance:'100000.00',broker_available:'100000.00',broker_frozen:'0.00',withdrawable:null,positions:[],permission_profile:[]}};
    const draft=await (await request.post('/api/account/drafts',{data:input})).json();
    await request.post('/api/account/confirm',{data:{draft_id:draft.draft_id,idempotency_key:'fills-browser-baseline'}});
  }
  await page.goto('/');
  await page.getByRole('button',{name:'同步账户',exact:true}).click();
  await page.getByRole('button',{name:'同步实际成交',exact:true}).click();
  await page.getByLabel('成交证券代码').fill('600000');
  await page.getByLabel('实际成交数量').fill('300');
  await page.getByLabel('原始成交价格（元）').fill('10.00');
  await page.getByLabel('分笔成交标识').fill('browser-fill');
  await page.getByRole('combobox',{name:'费用状态',exact:true}).selectOption('PROVISIONAL');
  await page.getByLabel('保守预留费用（元）').fill('10.00');
  await page.getByLabel('费用依据').fill('按券商费率与最低费用保守估计');
  await page.getByRole('button',{name:'预览成交差异'}).click();
  await expect(page.getByText('费用暂估，实际费用仍未知')).toBeVisible();
  await page.getByRole('button',{name:'确认实际成交'}).click();
  await expect(page.getByRole('heading',{name:'实际成交已确认，回执已保存'})).toBeVisible();
  await page.getByRole('button',{name:'查询成交回执'}).click();
  await expect(page.getByText('回执查询成功')).toBeVisible();
  await page.getByRole('button',{name:'回到今天'}).click();
  await expect(page.getByText('账面现金含费用暂估，净收益仍待核')).toBeVisible();
  await page.screenshot({path:'test-results/fill-provisional.png',fullPage:true});
  await page.getByRole('button',{name:'同步账户',exact:true}).click();
  await page.getByRole('button',{name:'补充费用',exact:true}).click();
  await page.getByLabel('补充实际费用（元）').fill('5.00');
  await page.getByLabel('费用调整依据').fill('券商已结算费用回报');
  await page.getByRole('button',{name:'预览费用调整'}).click();
  await page.getByRole('button',{name:'确认费用调整'}).click();
  await expect(page.getByRole('heading',{name:'费用调整已确认，回执已保存'})).toBeVisible();
  await page.getByRole('button',{name:'回到今天'}).click();
  await expect(page.getByText('账面现金含费用暂估，净收益仍待核')).toHaveCount(0);
  await page.getByRole('button',{name:'历史记录',exact:true}).click();
  await expect(page.getByText('browser-fill',{exact:false}).first()).toBeVisible();
  await page.screenshot({path:'test-results/fill-history.png',fullPage:true});
});

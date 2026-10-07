import {expect,test} from '@playwright/test';

test('finite market page preserves holdings, distinct restrictions, membership versions and exchange calendar gaps',async({page})=>{
  const account=await (await page.request.get('/api/account')).json();
  if(account.version===0){
    const draft=await (await page.request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{
      effective_at:'2026-10-07T00:00:00+08:00',source:'browser acceptance snapshot',cash_balance:'10000.00',
      broker_available:null,broker_frozen:null,withdrawable:null,
      positions:[{instrument:'SSE:600000',quantity:'300',sellable_quantity:null,reference_cost:null}],
      permission_profile:[{market:'SSE',board:'MAIN',status:'NOT_OPEN',basis:'broker confirmation'}]}}})).json();
    expect((await page.request.post('/api/account/confirm',{data:{draft_id:draft.draft_id,idempotency_key:'market-browser'}})).ok()).toBeTruthy();
  }
  const quantity=account.positions.find((p:{instrument:string})=>p.instrument==='SSE:600000')?.quantity??'300';
  await page.goto('/');
  await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  const holding=page.getByRole('article',{name:'SSE:600000',exact:true});
  await expect(holding.getByText(`实际持仓 ${quantity} 股 · 可卖 未知`)).toBeVisible();
  await expect(holding.getByText('规则：未适配 · 账户权限：未知')).toBeVisible();
  await holding.getByText('核对证券身份与依据',{exact:true}).click();
  await holding.getByLabel('证券名称').fill('浦发银行');
  await holding.getByLabel('已核对板块').selectOption('MAIN');
  await holding.getByLabel('证券类型',{exact:true}).selectOption('STOCK');
  await holding.getByLabel('身份确认依据').fill('脱敏券商详情明确：上交所主板普通A股');
  await holding.getByRole('button',{name:'保存已核对身份'}).click();
  await expect(holding.getByText('规则：基本规则已适配 · 账户权限：未开通')).toBeVisible();
  await page.getByLabel('关注代码').fill('600519');
  await page.getByRole('button',{name:'添加关注',exact:true}).click();
  const watched=page.getByRole('article',{name:'SSE:600519',exact:true});
  await expect(watched.getByText('关注证券',{exact:true})).toBeVisible();
  const original=await (await page.request.get('/api/market/list')).json();
  const outside=await page.request.post('/api/market/scope/check',{data:{instruments:['SZSE:000001'],purpose:'RESEARCH'}});
  expect(outside.status()).toBe(403);
  await page.reload();await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  await expect(watched.getByText('关注证券',{exact:true})).toBeVisible();
  await watched.getByRole('button',{name:'取消关注'}).click();
  await expect(watched).toHaveCount(0);
  await holding.getByRole('button',{name:'加入关注'}).click();
  await holding.getByRole('button',{name:'取消关注'}).click();
  await expect(holding.getByText(`实际持仓 ${quantity} 股 · 可卖 未知`)).toBeVisible();
  await page.getByRole('button',{name:'查询名单历史'}).click();
  await page.getByRole('button',{name:`查看名单版本 ${original.version}`,exact:true}).click();
  await expect(page.getByRole('listitem').filter({hasText:'SSE:600519 · 关注 · 已关注'})).toBeVisible();
  await page.getByLabel('查询日期（上海时间）').fill('2026-10-07');
  await page.getByRole('button',{name:'查询交易日',exact:true}).click();
  await expect(page.getByText('2026-10-07 · SSE · 休市',{exact:true})).toBeVisible();
  await expect(page.getByText('下一个已知交易日：2026-10-08')).toBeVisible();
  await page.getByLabel('日历交易所').selectOption('BSE');
  await page.getByRole('button',{name:'查询交易日',exact:true}).click();
  await expect(page.getByText('2026-10-07 · BSE · 日历未取得，交易日未知',{exact:true})).toBeVisible();
  await page.screenshot({path:'test-results/market-watch-history-calendar.png',fullPage:true});
});

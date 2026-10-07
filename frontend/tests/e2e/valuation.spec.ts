import {test,expect} from '@playwright/test';

test('saved cash-flow valuation matches API, excludes transfers from profit and replays after reload',async({page,request})=>{
  test.skip(Boolean(process.env.ROLL_TEST_DATA_DIR),'isolated cash fixture only; real archive is a separate flow');
  let account=await(await request.get('/api/account')).json();
  if(account.version===0){
    const d=await(await request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{
      effective_at:'2026-10-07T10:00:00+08:00',source:'浏览器合成账户方法验收',cash_balance:'100000',
      broker_available:'90000',broker_frozen:'10000',withdrawable:null,positions:[],permission_profile:[]}}})).json();
    await request.post('/api/account/confirm',{data:{draft_id:d.draft_id,idempotency_key:'valuation-browser-baseline'}});
  }
  account=await(await request.get('/api/account')).json();
  for(const [kind,amount,record] of [['CASH_IN','10000','valuation-deposit'],['INTEREST','10','valuation-interest']]){
    const d=await(await request.post('/api/account/drafts',{data:{kind,expected_account_version:account.version,payload:{
      effective_at:'2026-10-07T12:00:00+08:00',source:'浏览器方法验收流水',record_id:record,amount,instrument:null,
      basis:'外部投入与利息分列',broker_available_after:null}}})).json();
    const response=await request.post('/api/account/confirm',{data:{draft_id:d.draft_id,idempotency_key:record}});
    expect(response.ok()).toBeTruthy();account=await(await request.get('/api/account')).json();
  }
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  await page.getByRole('button',{name:'账户估值与绩效',exact:true}).click();
  await page.getByLabel('估值截止（含时区）').fill('2026-10-07T16:00:00+08:00');
  await page.getByRole('button',{name:'计算并保存估值',exact:true}).click();
  await expect(page.getByText('估值版本已保存，可按原输入重放。')).toBeVisible();
  await expect(page.getByTestId('valuation-net')).toHaveText('110010.00 元');
  await expect(page.getByTestId('valuation-pnl')).toHaveText('10.00 元');
  const actual=await(await request.get('/api/account/valuations/current')).json();
  expect(actual.facts.external_in).toBe('10000.00');expect(actual.facts.income).toBe('10.00');
  await expect(page.getByText('冻结 10000.00 元',{exact:false})).toBeVisible();
  await expect(page.getByText('基线前历史不完整',{exact:false})).toBeVisible();
  await page.screenshot({path:'test-results/valuation-cash-flow.png',fullPage:true});
  await page.reload();await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  await page.getByRole('button',{name:'账户估值与绩效',exact:true}).click();
  await expect(page.getByTestId('valuation-pnl')).toHaveText('10.00 元');
  await page.getByText('查看计算与重放依据',{exact:true}).click();
  await page.getByRole('button',{name:'重放原输入',exact:true}).click();
  await expect(page.getByText('原账户与报价输入重放一致。')).toBeVisible();
});

test('preserved real September quote keeps original time, stale mark and unknown baseline in holdings UI',async({page,request})=>{
  test.skip(!process.env.ROLL_TEST_DATA_DIR,'requires explicitly copied preserved real 07 archive');
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  await page.getByRole('button',{name:'账户估值与绩效',exact:true}).click();
  await page.getByRole('button',{name:'计算并保存估值',exact:true}).click();
  await expect(page.getByText('估值版本已保存，可按原输入重放。')).toBeVisible();
  await expect(page.getByTestId('valuation-net')).toHaveText('135862.00 元');
  await expect(page.getByTestId('valuation-pnl')).toHaveText('未知');
  const holding=page.getByRole('article',{name:'估值 SSE:600519',exact:true});
  await expect(holding.getByText('2026-09-30T16:14:58+08:00',{exact:false})).toBeVisible();
  await expect(holding.getByText('陈旧／非同步估值',{exact:false})).toBeVisible();
  await expect(holding.getByText('1258.62 元',{exact:false})).toBeVisible();
  const v=await(await request.get('/api/account/valuations/current')).json();
  expect(v.positions[0].quote.evidence_kind).toBe('REAL_ACQUISITION');
  expect(v.positions[0].quote.available_at).not.toBe(v.created_at);
  expect(v.facts.baseline_assets).toBeNull();
  await page.screenshot({path:'test-results/valuation-real-stale.png',fullPage:true});
  await page.getByText('查看计算与重放依据',{exact:true}).click();
  await page.getByRole('button',{name:'重放原输入',exact:true}).click();
  await expect(page.getByText('原账户与报价输入重放一致。')).toBeVisible();
});

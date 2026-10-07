import {test,expect} from '@playwright/test';

test('five-entry no-trade declaration, on-demand facts, post-close gaps, history and maintenance in actual Chrome',async({page,request})=>{
  test.skip(process.env.ROLL_PLAYWRIGHT_FACTORY!=='review_method_app:factory','isolated15 method factory and empty account required');
  const baseline=await(await request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{
    effective_at:'2026-10-07T10:00:00+08:00',source:'合成浏览器基线',cash_balance:'10000',broker_available:'10000',broker_frozen:'0',withdrawable:null,
    positions:[{instrument:'SSE:600519',quantity:'100',sellable_quantity:'100',reference_cost:null}],permission_profile:[]}}})).json();
  expect((await request.post('/api/account/confirm',{data:{draft_id:baseline.draft_id,idempotency_key:'review-baseline'}})).ok()).toBeTruthy();
  await request.post('/api/market/identities',{data:{instrument:'SSE:600519',exchange:'SSE',board:'MAIN',instrument_type:'STOCK',name:'合成普通股',basis:'合成证券身份',effective_at:'2026-10-07T10:00:00+08:00'}});
  for(const [instruments,groups,purpose] of [[['SSE:600519'],['DAILY','STATUS','ADJUSTMENTS','ANNOUNCEMENTS','PERFORMANCE','MAJOR_EVENTS'],'OBSERVATION'],[['SSE:000001'],['DAILY'],'BACKGROUND']] as const){
    const response=await request.post('/api/data/requests',{data:{instruments,groups,purpose,start_date:'2026-01-01',end_date:'2026-10-08',max_calls:20}});
    expect(response.ok()).toBeTruthy();const data=await response.json();
    expect((await request.post('/api/data/requests/'+data.request_id+'/retrieve')).ok()).toBeTruthy();
  }
  await page.goto('/');expect(await page.getByRole('navigation',{name:'主导航'}).getByRole('button').count()).toBe(5);
  await page.getByRole('button',{name:'同步账户',exact:true}).click();await page.getByRole('button',{name:'账户核对与更正',exact:true}).click();
  await page.getByLabel('本次核对截至时点').fill('2026-10-07T14:00');await page.getByLabel('核对依据或更正原因').fill('逐项核对成交、委托、资金与权益，无未记录变化');
  await page.getByRole('button',{name:'预览账户核对'}).click();await page.getByRole('button',{name:'确认账户核对'}).click();
  await expect(page.getByRole('heading',{name:'账户核对已确认，回执已保存'})).toBeVisible();await page.getByRole('button',{name:'回到今天',exact:true}).click();
  const accountBefore=await(await request.get('/api/account')).json();
  await page.getByRole('button',{name:'按需观察',exact:true}).click();await expect(page.getByText('观察记录已保存。')).toBeVisible();
  await expect(page.getByText('合成停牌风险原时点案例；不代表实际当前状态',{exact:false}).first()).toBeVisible();
  await expect(page.getByText('已归档外部权益事实，个人到账仍待确认。',{exact:true})).toBeVisible();
  await expect(page.getByText('固定市场背景',{exact:true})).toBeVisible();await expect(page.getByText('上证指数',{exact:false})).toBeVisible();
  await expect(page.getByText('最近完整日线 2026-09-30',{exact:false}).first()).toBeVisible();
  const postCloseResponse=page.waitForResponse(r=>r.url().endsWith('/api/reviews/tasks')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'盘后复盘',exact:true}).click();const postClose=await(await postCloseResponse).json();await expect(page.locator(`[data-review-task="${postClose.task_id}"]`).getByText('观察记录已保存。')).toBeVisible();
  await expect(page.getByText('当日日线仍未齐，已有事实继续展示。',{exact:true})).toBeVisible();
  await page.getByText('运行审计与覆盖详情',{exact:true}).click();await expect(page.getByText('重复通知：尚未接入',{exact:true})).toBeVisible();
  await page.screenshot({path:'test-results/review-today.png',fullPage:true});
  await page.getByRole('button',{name:'历史记录',exact:true}).click();await expect(page.getByRole('heading',{name:'观察与复盘时间线',exact:true})).toBeVisible();
  await page.getByRole('button',{name:/查看观察/}).first().click();await expect(page.getByText('未观察到的触发顺序不重建；不补造盘中预测。').last()).toBeVisible();
  await page.getByRole('button',{name:'设置',exact:true}).click();await page.getByLabel('维护检查点（上海时间）').fill('2026-10-09T16:00');
  await page.getByRole('button',{name:'登记维护检查点',exact:true}).click();await expect(page.getByText('维护检查点已保存。')).toBeVisible();
  await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await expect(page.getByRole('heading',{name:'持仓与关注',exact:true})).toBeVisible();
  const account=await(await request.get('/api/account')).json();expect(account.version).toBe(2);expect(account.cash_balance).toBe('10000.00');
  expect(account.positions[0].quantity).toBe('100');expect(account).toEqual(accountBefore);
});

import {expect,test} from '@playwright/test';
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
test('three pause scopes, evidence-bound recovery and stale cards remain controlled',async({page})=>{
  test.setTimeout(90000);
  await page.goto('/');
  const at=new Date(Date.now()-1000).toISOString();
  const baseline=await(await page.request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{effective_at:'2026-10-07T10:00:00+08:00',source:'METHOD lifecycle browser',cash_balance:'100000.10',broker_available:'90000.10',broker_frozen:'10000.00',withdrawable:null,positions:[],permission_profile:[{market:'SSE',board:'MAIN',status:'OPEN',basis:'METHOD'}]}}})).json();
  expect((await page.request.post('/api/account/confirm',{data:{draft_id:baseline.draft_id,idempotency_key:'baseline'}})).status()).toBe(200);
  const declaration=await(await page.request.post('/api/account/drafts',{data:{kind:'ACCOUNT_DECLARATION',expected_account_version:1,payload:{effective_at:at,source:'METHOD',record_id:'declaration',scope:['TRADES','ORDERS','CASH','EQUITY'],changes:'NONE',basis:'METHOD'}}})).json();
  await page.request.post('/api/account/confirm',{data:{draft_id:declaration.draft_id,idempotency_key:'declaration'}});
  for(const instrument of ['SSE:600000','SSE:600001']){
    const listing=await(await page.request.get('/api/market/list')).json();
    expect((await page.request.post('/api/market/watch',{data:{instrument,operation:'ADD',expected_list_version:listing.version}})).status()).toBe(200);
  }
  await page.request.post('/api/funding/confirm',{data:{expected_version:0,idempotency_key:'funding',authorization:{scope_kind:'ACCOUNT',scope_id:'account-1',purpose:'METHOD',capital_amount:'100000.00',total_exposure:'60000.00',single_exposure:'40000.00',cash_reserve:'40000.00',loss_threshold:'5000.00',effective_at:'2026-10-07T10:00:00+08:00',basis:'METHOD',enabled:true}}});
  const proposal=await(await page.request.get('/api/capabilities/proposal?material_id=method-material&review_run_id=method-codex-review')).json();
  const grantResponse=await page.request.post('/api/capabilities/grants',{data:{...proposal,allowed_actions:['BUY'],idempotency_key:'grant',basis:'METHOD'}});
  expect(grantResponse.status()).toBe(201);
  const grant=await grantResponse.json(),history=await(await page.request.get('/api/capabilities/grants')).json();
  await page.reload();
  await page.getByRole('button',{name:'核验当前动作',exact:true}).click();
  await expect(page.getByText('SSE:600000 · 买入',{exact:true})).toBeVisible();
  const original=(await(await page.request.get('/api/actions/current')).json()).evaluation;
  const panel=page.getByRole('region',{name:'暂停与恢复',exact:true});
  await expect(panel).toBeVisible();
  for(const [scope,label] of [['NEW_RISK','新增风险'],['MODEL','模型建议'],['ALL_MONITOR','全部监控']]){
    await panel.getByLabel('暂停范围',{exact:true}).selectOption(scope);
    await panel.getByLabel('操作原因',{exact:true}).fill('METHOD 主动暂停 '+label);
    await panel.getByRole('button',{name:'暂停所选范围',exact:true}).click();
    await expect(panel.getByText(label+'：已暂停',{exact:true})).toBeVisible();
    await expect(page.getByText('当前没有有效正式动作',{exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'准备操作',exact:true})).toHaveCount(0);
    await panel.getByLabel('操作原因',{exact:true}).fill('已核对主动暂停原因 '+label);
    await panel.getByRole('button',{name:'核对原因并恢复所选范围',exact:true}).click();
    await expect(panel.getByText(label+'：运行中',{exact:true})).toBeVisible();
    expect((await(await page.request.get('/api/actions/current')).json()).decisions).toEqual([]);
  }
  expect(await(await page.request.get('/api/actions/evaluations/'+original.evaluation_id)).json()).toEqual(original);
  await page.getByRole('button',{name:'设置',exact:true}).click();
  const settings=page.getByRole('region',{name:'暂停与恢复',exact:true});
  await settings.getByLabel('资格范围',{exact:true}).selectOption(grant.grant_id);
  await settings.getByRole('button',{name:'核对冻结监测',exact:true}).click();
  await expect(settings.getByText('最近20次输入至少20%超出冻结开发参考范围',{exact:true})).toBeVisible();
  await settings.getByLabel('暂停范围',{exact:true}).selectOption('MODEL');
  await settings.getByLabel('操作原因',{exact:true}).fill('缺少健康监测依据不能恢复');
  await settings.getByRole('button',{name:'核对原因并恢复所选范围',exact:true}).click();
  await expect(settings.getByRole('alert')).toBeVisible();
  expect((await(await page.request.get('/api/capabilities/grants/'+grant.grant_id+'/status')).json()).allowed_actions).toEqual([]);
  // Monotone native METHOD clock, without changing the immutable source package
  // or introducing a production command/time endpoint.
  const clockFile=resolve(process.env.ROLL_LIFECYCLE_PROFILE!,'method-clock.json');
  const clock=JSON.parse(readFileSync(clockFile,'utf-8'));
  expect(clock.namespace).toBe('METHOD_ENGINEERING');
  expect(clock.system_usable).toBe(false);
  expect(Date.parse(clock.later)).toBeGreaterThan(Date.parse(clock.time));
  writeFileSync(clockFile,JSON.stringify({...clock,time:clock.later}));
  await settings.getByRole('button',{name:'核对冻结监测',exact:true}).click();
  await expect(settings.getByText(/已按冻结方法核对/)).toBeVisible();
  const healthy=(await(await page.request.get('/api/capabilities/monitoring')).json()).at(-1);
  expect(healthy.status).toBe('CHECKED');
  await settings.getByLabel('恢复监测依据',{exact:true}).selectOption(healthy.check_id);
  await settings.getByLabel('操作原因',{exact:true}).fill('较晚的同冻结输入已恢复支持，按原原因核对');
  await settings.getByRole('button',{name:'核对原因并恢复所选范围',exact:true}).click();
  await expect(settings.getByText('模型建议：运行中',{exact:true})).toBeVisible();
  expect((await(await page.request.get('/api/actions/current')).json()).decisions).toEqual([]);
  expect(await(await page.request.get('/api/actions/evaluations/'+original.evaluation_id)).json()).toEqual(original);
  await settings.getByLabel('操作原因',{exact:true}).fill('用户撤回本资格，原记录不可复活');
  await settings.getByRole('button',{name:'撤回所选资格',exact:true}).click();
  await expect(settings.getByText('模型建议：已撤回',{exact:true})).toBeVisible();
  expect(await(await page.request.get('/api/capabilities/grants')).json()).toEqual(history);
  expect((await page.request.post('/api/formal/evaluate')).status()).toBe(403);
  await page.screenshot({path:'test-results/lifecycle-controls.png',fullPage:true});
});

import {expect,test} from '@playwright/test';
const scenario=process.env.ROLL_ACTION_CASE;
test('current action retains explicit stale, permission or sellable refusal',async({page})=>{
  expect(['stale','permission','sellable']).toContain(scenario);
  await page.goto('/');
  const at=new Date(Date.now()-1000).toISOString();
  const permission=scenario==='permission'?'UNKNOWN':scenario==='sellable'?'NOT_OPEN':'OPEN';
  const positions=scenario==='sellable'?[{instrument:'SSE:600000',quantity:'300',sellable_quantity:'0',reference_cost:'100'}]:[];
  const b=await(await page.request.post('/api/account/drafts',{data:{kind:'BASELINE',expected_account_version:0,payload:{effective_at:'2026-10-07T10:00:00+08:00',source:'METHOD restricted browser',cash_balance:'100000.10',broker_available:'90000.10',broker_frozen:'10000.00',withdrawable:null,positions,permission_profile:[{market:'SSE',board:'MAIN',status:permission,basis:'METHOD'}]}}})).json();
  expect((await page.request.post('/api/account/confirm',{data:{draft_id:b.draft_id,idempotency_key:'baseline'}})).status()).toBe(200);
  const d=await(await page.request.post('/api/account/drafts',{data:{kind:'ACCOUNT_DECLARATION',expected_account_version:1,payload:{effective_at:at,source:'METHOD',record_id:'declaration',scope:['TRADES','ORDERS','CASH','EQUITY'],changes:'NONE',basis:'METHOD'}}})).json();
  expect((await page.request.post('/api/account/confirm',{data:{draft_id:d.draft_id,idempotency_key:'declaration'}})).status()).toBe(200);
  for(const instrument of scenario==='sellable'?['SSE:600000']:['SSE:600000','SSE:600001']){
    const listing=await(await page.request.get('/api/market/list')).json();
    if(!listing.members.some((m:{instrument:string})=>m.instrument===instrument))expect((await page.request.post('/api/market/watch',{data:{instrument,operation:'ADD',expected_list_version:listing.version}})).status()).toBe(200);
  }
  const authorization={scope_kind:'ACCOUNT',scope_id:'account-1',purpose:'本人普通账户',capital_amount:'100000.00',total_exposure:'60000.00',single_exposure:scenario==='sellable'?'20000.00':'40000.00',cash_reserve:'40000.00',loss_threshold:'5000.00',effective_at:'2026-10-07T10:00:00+08:00',basis:'本人确认',enabled:true};
  expect((await page.request.post('/api/funding/confirm',{data:{expected_version:0,idempotency_key:'funding',authorization}})).status()).toBe(200);
  if(scenario!=='permission'){
    const proposal=await(await page.request.get('/api/capabilities/proposal?material_id=method-material&review_run_id=method-codex-review')).json();
    const grant=await page.request.post('/api/capabilities/grants',{data:{...proposal,allowed_actions:scenario==='sellable'?['REDUCE','EXIT']:['BUY'],idempotency_key:'grant',basis:'METHOD'}});
    expect(grant.status(),await grant.text()).toBe(201);
  }
  await page.reload();
  await page.getByRole('button',{name:'核验当前动作',exact:true}).click();
  await expect(page.getByText('当前没有有效正式动作',{exact:true})).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
  if(scenario==='sellable'){
    await expect(page.getByText(/可卖 0.*NO_CONFIRMED_SELLABLE_LOT/)).toBeVisible();
    await expect(page.getByText('SSE:600000 · 减仓',{exact:true})).toHaveCount(0);
  }else{
    await page.getByText('查看机会限制',{exact:true}).click();
    await expect(page.getByText(scenario==='stale'?/SSE:600000：.*LOSS_BOUNDARY_UNAVAILABLE_OR_PAUSED/:/SSE:600000：.*MARKET_PERMISSION_NOT_OPEN/)).toBeVisible();
    if(scenario==='stale')await expect(page.getByText(/损失额度：未知，限制新增风险/)).toBeVisible();
  }
  await page.screenshot({path:`test-results/actions-${scenario}.png`,fullPage:true});
});

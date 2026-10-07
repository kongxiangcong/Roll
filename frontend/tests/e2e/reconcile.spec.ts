import {expect,test} from '@playwright/test';

test('scoped declaration, append correction, broker differences and immutable history in real Chrome',async({page,request})=>{
  const input={kind:'BASELINE',expected_account_version:0,payload:{effective_at:'2026-10-07T10:00:00+08:00',source:'合成浏览器券商基线',cash_balance:'100000.00',broker_available:'100000.00',broker_frozen:'0.00',withdrawable:null,positions:[],permission_profile:[]}};
  const d=await (await request.post('/api/account/drafts',{data:input})).json();
  const original=await (await request.post('/api/account/confirm',{data:{draft_id:d.draft_id,idempotency_key:'reconcile-browser-baseline'}})).json();
  const open=async()=>{await page.getByRole('button',{name:'同步账户',exact:true}).click();await page.getByRole('button',{name:'账户核对与更正',exact:true}).click();};
  await page.goto('/');await open();
  await page.getByLabel('本次核对截至时点').fill('2026-10-07T14:00');
  await page.getByLabel('核对依据或更正原因').fill('已逐项查看成交、委托、资金及权益记录，无未记录变化');
  await page.getByRole('button',{name:'检查本次账户事实'}).click();
  await expect(page.getByRole('status')).toContainText('本次用途的声明已过时');
  await page.getByRole('button',{name:'预览账户核对'}).click();
  await expect(page.getByText('声明范围 成交、委托、资金、权益；截至 2026-10-07T14:00；无未记录变化')).toBeVisible();
  await page.screenshot({path:'test-results/declaration-preview.png',fullPage:true});
  await page.getByRole('button',{name:'确认账户核对'}).click();
  await expect(page.getByRole('heading',{name:'账户核对已确认，回执已保存'})).toBeVisible();
  await page.getByRole('button',{name:'回到今天',exact:true}).click();
  await expect(page.getByText(/本次声明：成交、委托、资金、权益截至/)).toBeVisible();
  const check=await (await request.post('/api/account/use-check',{data:{purpose:'NEW_RISK',required_as_of:'2026-10-07T14:00:00+08:00'}})).json();expect(check.state).toBe('CONFIRMED_AS_OF');
  const interest={kind:'INTEREST',expected_account_version:2,payload:{effective_at:'2026-10-07T11:00:00+08:00',source:'实际利息流水',record_id:'browser-interest',amount:'10.00',instrument:null,basis:'到账记录',broker_available_after:null}};
  const material=await (await request.post('/api/account/drafts',{data:interest})).json();
  await request.post('/api/account/confirm',{data:{draft_id:material.draft_id,idempotency_key:'browser-interest'}});
  await open();await page.getByRole('button',{name:'追加更正或冲正',exact:true}).click();
  await page.getByLabel('本次核对截至时点').fill('2026-10-07T14:00');
  await page.getByLabel('核对依据或更正原因').fill('原利息凭证核实为20元，保留原10元记录');
  const candidate=await (await request.get('/api/account/correction-candidates')).json();
  await page.getByLabel('原事实或当前替代链').selectOption(candidate.find((c:{command:{payload:{record_id:string}}})=>c.command.payload.record_id==='browser-interest').target_event_id);
  await page.getByLabel('实际金额',{exact:true}).fill('20.00');
  await page.getByRole('button',{name:'预览账户核对'}).click();await page.getByRole('button',{name:'确认账户核对'}).click();
  await expect(page.getByRole('heading',{name:'账户核对已确认，回执已保存'})).toBeVisible();
  await page.getByRole('button',{name:'回到今天',exact:true}).click();
  const corrected=await (await request.get('/api/account')).json();expect(corrected.cash_balance).toBe('100020.00');expect(corrected.investment_income).toBe('20.00');
  await open();await page.getByRole('button',{name:'券商快照核对',exact:true}).click();
  await page.getByLabel('本次核对截至时点').fill('2026-10-07T14:00');
  await page.getByLabel('核对依据或更正原因').fill('券商持仓120股，可卖量尚未知；按已核对快照确认');
  await page.getByLabel('券商可用资金',{exact:true}).fill('100020.00');await page.getByLabel('冻结资金',{exact:true}).fill('0.00');
  await page.getByRole('button',{name:'添加核对持仓'}).click();await page.getByLabel('证券标识').fill('SSE:600000');await page.getByLabel('持仓数量',{exact:true}).fill('120');
  await page.getByRole('button',{name:'预览账户核对'}).click();
  await expect(page.getByRole('table')).toContainText('未知');await expect(page.getByRole('table')).toContainText('120');
  expect((await (await request.get('/api/account')).json()).positions.length).toBe(0);
  await page.screenshot({path:'test-results/reconcile-differences.png',fullPage:true});
  await page.getByRole('button',{name:'确认账户核对'}).click();await expect(page.getByRole('heading',{name:'账户核对已确认，回执已保存'})).toBeVisible();await page.getByRole('button',{name:'回到今天',exact:true}).click();
  await expect(page.getByText('账户核对状态：账户差异待核对')).toBeVisible();
  const account=await (await request.get('/api/account')).json();expect(account.positions[0].sellable_quantity).toBeNull();expect(account.positions[0].acquisition_cost).toBeNull();
  await page.screenshot({path:'test-results/reconcile-unknown-today.png',fullPage:true});
  await page.getByRole('button',{name:'历史记录',exact:true}).click();await page.getByRole('button',{name:'查看账户版本 2',exact:true}).click();
  await expect(page.getByText(/现金 100000.00 元 · 事实截至/)).toBeVisible();await expect(page.getByRole('heading',{name:'追加冲正与替代链'})).toBeVisible();
  const local=(value:string)=>{const date=new Date(new Date(value).getTime()+1000);return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,19);};
  await page.getByLabel('系统当时已知截至').fill(local(original.confirmed_at));await page.getByLabel('实际发生截至').fill('2026-10-07T14:00');await page.getByRole('button',{name:'查询双时间账户'}).click();
  await expect(page.getByRole('status')).toContainText('当时现金 100000.00 元');
  await page.screenshot({path:'test-results/reconcile-old-history.png',fullPage:true});
});

test('CSV v3 confirms replacement, broker snapshot and declaration with a single durable receipt',async({page,request})=>{
  const before=await (await request.get('/api/account')).json();
  const candidates=await (await request.get('/api/account/correction-candidates')).json();
  const prior=candidates.find((c:{command:{payload:{record_id:string}}})=>c.command.payload.record_id==='browser-interest');
  const snapshot={cash_balance:'100025.00',broker_available:'100025.00',broker_frozen:'0.00',withdrawable:null,
    investment_income:'25.00',investment_expenses:'0.00',positions:before.positions.map((p:{instrument:string;quantity:string;sellable_quantity:string|null})=>({instrument:p.instrument,quantity:p.quantity,sellable_quantity:p.sellable_quantity})),pending_items:[]};
  const rows=[{kind:'CORRECTION',record_id:'browser-csv-correction',target_event_id:prior.target_event_id,reason:'实际利息应为25元',replacement_kind:'INTEREST',replacement_payload:JSON.stringify({...prior.command.payload,amount:'25.00'})},
    {kind:'RECONCILIATION',record_id:'browser-csv-snapshot',reason:'逐项核对，未知可卖继续待核',snapshot:JSON.stringify(snapshot),resolved_draft_ids:'[]'},
    {kind:'ACCOUNT_DECLARATION',record_id:'browser-csv-declare',scope:JSON.stringify(['CASH']),changes:'NONE',basis:'资金流水全部核对'}];
  const template=await (await request.get('/api/account/csv/template')).text();const columns=template.replace(/^\uFEFF/,'').trim().split(',');
  const quote=(value:string)=>'"'+value.replaceAll('"','""')+'"';
  const body=template+rows.map(row=>{const fields:Record<string,string>={template_version:'ROLL-CSV-3',effective_at:'2026-10-07T14:00:00+08:00',source:'实际核对原件',...row};return columns.map(c=>quote(fields[c]??'')).join(',')+'\r\n';}).join('');
  await page.goto('/');await page.getByRole('button',{name:'同步账户',exact:true}).click();await page.getByRole('button',{name:'Roll CSV导入',exact:true}).click();
  await page.getByLabel('Roll CSV文件').setInputFiles({name:'补录更正核对.csv',mimeType:'text/csv',buffer:Buffer.from(body)});await page.getByRole('button',{name:'上传并预览整批'}).click();
  await expect(page.getByText('投资收益到账',{exact:true})).toBeVisible();expect((await (await request.get('/api/account')).json()).version).toBe(before.version);
  await page.screenshot({path:'test-results/reconcile-csv-v3-preview.png',fullPage:true});await page.getByRole('button',{name:'确认整批入账'}).click();
  await expect(page.getByRole('heading',{name:'CSV整批已确认，回执已保存'})).toBeVisible();await page.getByRole('button',{name:'查询CSV回执'}).click();await expect(page.getByText('CSV回执查询成功')).toBeVisible();
  const after=await (await request.get('/api/account')).json();expect(after.version).toBe(before.version+1);expect(after.cash_balance).toBe('100025.00');expect(after.investment_income).toBe('25.00');
  const receipt=after.corrections.at(-1).receipt_id;expect(after.reconciliation.receipt_id).toBe(receipt);expect(after.declarations.at(-1).receipt_id).toBe(receipt);
  await page.screenshot({path:'test-results/reconcile-csv-v3-receipt.png',fullPage:true});
});

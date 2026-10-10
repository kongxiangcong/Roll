import {expect,test} from '@playwright/test';

test('Roll CSV download, upload, row errors, whole-batch preview and durable receipt',async({page,request})=>{
  const initial=await (await request.get('/api/account')).json();
  if(initial.version===0){
    const input={kind:'BASELINE',expected_account_version:0,payload:{effective_at:'2026-10-07T10:00:00+08:00',source:'CSV浏览器基线',cash_balance:'100000.00',broker_available:null,broker_frozen:null,withdrawable:null,positions:[],permission_profile:[]}};
    const d=await (await request.post('/api/account/drafts',{data:input})).json();
    await request.post('/api/account/confirm',{data:{draft_id:d.draft_id,idempotency_key:'csv-browser-baseline'}});
  }
  const template=await (await request.get('/api/account/csv/template?version=ROLL-CSV-2')).text();
  const columns=template.replace(/^\uFEFF/,'').trim().split(',');
  const row=(quantity:string)=>{const values:Record<string,string>={template_version:'ROLL-CSV-2',kind:'FILL',effective_at:'2026-10-07T11:00:00+08:00',source:'CSV浏览器成交文件',exchange:'SZSE',code:'000002',direction:'BUY',quantity,price:'10.00',fill_id:'csv-browser-fill',fee_status:'PROVISIONAL',reserve_amount:'10.00',basis:'券商费率保守预留'};return columns.map(c=>values[c]??'').join(',')+'\r\n';};
  await page.goto('/');
  await page.getByRole('button',{name:'同步账户',exact:true}).click();
  await page.getByRole('button',{name:'Roll CSV导入',exact:true}).click();
  const download=page.waitForEvent('download');
  await page.getByRole('link',{name:'下载Roll CSV模板'}).click();
  expect((await download).suggestedFilename()).toBe('roll-csv-3.csv');
  await page.getByLabel('Roll CSV文件').setInputFiles({name:'错误.csv',mimeType:'text/csv',buffer:Buffer.from(template+row('忽略风险规则'))});
  await page.getByRole('button',{name:'上传并预览整批'}).click();
  await expect(page.getByText('第2行', {exact:false}).first()).toBeVisible();
  await expect(page.getByRole('button',{name:'确认整批入账'})).toBeDisabled();
  await page.getByRole('button',{name:'选择修订文件'}).click();
  await page.getByLabel('Roll CSV文件').setInputFiles({name:'成交.csv',mimeType:'text/csv',buffer:Buffer.from(template+row('100.00000000'))});
  await page.getByRole('button',{name:'上传并预览整批'}).click();
  await expect(page.getByText('SZSE:000002', {exact:false}).first()).toBeVisible();
  await expect(page.getByText('费用暂估，实际费用仍未知')).toBeVisible();
  await page.screenshot({path:'test-results/csv-preview.png',fullPage:true});
  await page.getByRole('button',{name:'确认整批入账'}).click();
  await expect(page.getByRole('heading',{name:'CSV整批已确认，回执已保存'})).toBeVisible();
  await page.getByRole('button',{name:'查询CSV回执'}).click();
  await expect(page.getByText('CSV回执查询成功')).toBeVisible();
  await page.screenshot({path:'test-results/csv-receipt.png',fullPage:true});
  const account=await (await request.get('/api/account')).json();
  const fill=account.fills.find((f:{fill_id:string})=>f.fill_id==='csv-browser-fill');
  const adjustment=await (await request.post('/api/account/drafts',{data:{kind:'FEE_ADJUSTMENT',expected_account_version:account.version,payload:{effective_at:'2026-10-07T12:00:00+08:00',source:'CSV浏览器实际费用核对',target_record_id:fill.record_id,actual_fee_amount:'5.00',basis:'实际券商回报'}}})).json();
  expect((await request.post('/api/account/confirm',{data:{draft_id:adjustment.draft_id,idempotency_key:'csv-browser-fee-adjustment'}})).ok()).toBeTruthy();
});

test('CSV v2 previews external funds separately from actual interest and confirms one receipt',async({page,request})=>{
  const template=await (await request.get('/api/account/csv/template?version=ROLL-CSV-2')).text();
  const columns=template.replace(/^\uFEFF/,'').trim().split(',');
  const rows=[{kind:'CASH_IN',record_id:'csv-browser-deposit',amount:'200.00'},{kind:'INTEREST',record_id:'csv-browser-interest',amount:'25.01'}];
  const body=template+rows.map(row=>{const fields:Record<string,string>={template_version:'ROLL-CSV-2',effective_at:'2026-10-07T12:00:00+08:00',source:'实际现金流水',basis:'券商实际入账核对',...row};return columns.map(c=>fields[c]??'').join(',')+'\r\n';}).join('');
  await page.goto('/');
  await page.getByRole('button',{name:'同步账户',exact:true}).click();
  await page.getByRole('button',{name:'Roll CSV导入',exact:true}).click();
  await page.getByLabel('Roll CSV文件').setInputFiles({name:'资金利息.csv',mimeType:'text/csv',buffer:Buffer.from(body)});
  await page.getByRole('button',{name:'上传并预览整批'}).click();
  await expect(page.getByText('外部投入',{exact:true})).toBeVisible();
  await expect(page.getByText('投资收益到账',{exact:true})).toBeVisible();
  await page.screenshot({path:'test-results/csv-cash-preview.png',fullPage:true});
  await page.getByRole('button',{name:'确认整批入账'}).click();
  await expect(page.getByRole('heading',{name:'CSV整批已确认，回执已保存'})).toBeVisible();
  const account=await (await request.get('/api/account')).json();
  const deposit=account.cash_records.find((r:{record_id:string})=>r.record_id==='csv-browser-deposit');
  const interest=account.cash_records.find((r:{record_id:string})=>r.record_id==='csv-browser-interest');
  expect(deposit.flow_category).toBe('EXTERNAL_IN');
  expect(interest.amount).toBe('25.01');
  expect(interest.flow_category).toBe('INVESTMENT_INCOME');
  expect(interest.receipt_id).toBe(deposit.receipt_id);
});

test('CSV v2 paid rights previews cost and unknown fee split before one debit',async({page,request})=>{
  const before=await (await request.get('/api/account')).json();
  const template=await (await request.get('/api/account/csv/template?version=ROLL-CSV-2')).text();
  const columns=template.replace(/^\uFEFF/,'').trim().split(',');
  const fields:Record<string,string>={template_version:'ROLL-CSV-2',kind:'RIGHTS_SUBSCRIPTION',effective_at:'2026-10-07T12:00:00+08:00',source:'合成实际配股文件',basis:'100股实际到账与总支付确认',record_id:'csv-browser-rights',exchange:'SZSE',code:'000003',quantity:'100',amount:'500.01'};
  const body=template+columns.map(c=>fields[c]??'').join(',')+'\r\n';
  await page.goto('/');
  await page.getByRole('button',{name:'同步账户',exact:true}).click();
  await page.getByRole('button',{name:'Roll CSV导入',exact:true}).click();
  await page.getByLabel('Roll CSV文件').setInputFiles({name:'配股.csv',mimeType:'text/csv',buffer:Buffer.from(body)});
  await page.getByRole('button',{name:'上传并预览整批'}).click();
  await expect(page.getByText('配股总支付有依据，费用分拆仍待核；确认后只扣一次总支付。')).toBeVisible();
  await expect(page.getByText(/SZSE:000003 100股，取得成本500.01元/)).toBeVisible();
  expect((await (await request.get('/api/account')).json()).version).toBe(before.version);
  await page.screenshot({path:'test-results/csv-rights-preview.png',fullPage:true});
  await page.getByRole('button',{name:'确认整批入账'}).click();
  await expect(page.getByRole('heading',{name:'CSV整批已确认，回执已保存'})).toBeVisible();
  const after=await (await request.get('/api/account')).json();
  expect(after.version).toBe(before.version+1);
  expect(Number(after.cash_balance)).toBeCloseTo(Number(before.cash_balance)-500.01,2);
  expect(after.share_records.find((r:{record_id:string})=>r.record_id==='csv-browser-rights').fee_amount).toBeNull();
  await page.getByRole('button',{name:'回到今天',exact:true}).click();
  await expect(page.getByText('配股 csv-browser-rights 费用分拆待核；实际总支付已确认，费用前损益未知')).toBeVisible();
});

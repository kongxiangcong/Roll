import {test,expect} from '@playwright/test';

test('linked successor design freezes before frames and preserves diagnostic prefix',async({page,request})=>{
  const api=`http://127.0.0.1:${process.env.ROLL_TEST_API_PORT??'8010'}/api`;
  const protocols=await (await request.get(api+'/research/protocols')).json();
  const parent=protocols.find((p:{predecessor_id:string|null})=>p.predecessor_id===null);
  const child=protocols.find((p:{predecessor_id:string|null})=>p.predecessor_id===parent.protocol_id);
  const previous=(await (await request.get(api+`/research/protocols/${parent.protocol_id}/complete-freezes`)).json())[0];
  const frozen=(await (await request.get(api+`/research/complete-freezes/${previous.freeze_id}/policy-successor-freezes`)).json())[0];
  await page.goto('/');await page.getByRole('button',{name:'历史记录',exact:true}).click();await page.getByRole('button',{name:'研究登记',exact:true}).click();
  await page.getByRole('button',{name:`查看协议 ${parent.protocol_id.slice(0,8)}`,exact:true}).click();
  await page.getByText('后继政策完整设计与验证',{exact:true}).click();
  await page.getByLabel('后继影子版本').selectOption(frozen.successor_freeze_id);
  await page.getByLabel('关联后继实验').selectOption(child.protocol_id);
  await page.getByRole('button',{name:'冻结后继完整设计',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'后继设计参数已冻结 · 完整实验未冻结'})).toBeVisible();
  for(let session=1;session<=3;session++){
    const saved=await request.post(api+`/research/policy-successor-freezes/${frozen.successor_freeze_id}/shadow/advance`,{data:{idempotency_key:`browser-${session}`,expected_revision:session-1,session,calendar_previous_session:session-1,
      source_snapshot_id:`METHOD-browser-${session}`,evidence_kind:'METHOD_CASE',bars:[{instrument:'SSE:600519',open_yuan:'10.00',high_yuan:'10.50',low_yuan:'9.50',close_yuan:'10.00',volume_shares:10000,reference_close_yuan:'10.00',completion:'COMPLETE',market_state:'NORMAL',company_actions:'NONE'}],signals:[{instrument:'SSE:600519',forecast_id:`browser-signal-${session}`,probability:'0.80'}]}});
    expect(saved.ok()).toBeTruthy();
  }
  await page.getByRole('button',{name:'验证已保存后继影子',exact:true}).click();
  await expect(page.getByText('METHOD前缀 3 · INCONCLUSIVE · 无正式能力',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'重放后继验证前缀 3',exact:true}).click();
  await expect(page.getByRole('status').filter({hasText:'前缀3重放一致'})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/05-protocol/mobile.png',fullPage:true});
});

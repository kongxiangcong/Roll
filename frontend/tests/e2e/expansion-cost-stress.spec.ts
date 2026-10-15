import {test,expect} from '@playwright/test';
test('successor saved prefix cost sensitivity stays METHOD and replays',async({page,request})=>{
  const api=`http://127.0.0.1:${process.env.ROLL_TEST_API_PORT??'8010'}/api`;
  const protocols=await(await request.get(api+'/research/protocols')).json();
  const parent=protocols.find((p:{predecessor_id:string|null})=>p.predecessor_id===null),child=protocols.find((p:{predecessor_id:string|null})=>p.predecessor_id===parent.protocol_id);
  const previous=(await(await request.get(api+`/research/protocols/${parent.protocol_id}/complete-freezes`)).json())[0];
  const frozen=(await(await request.get(api+`/research/complete-freezes/${previous.freeze_id}/policy-successor-freezes`)).json())[0];
  const base=api+`/research/policy-successor-freezes/${frozen.successor_freeze_id}`;
  expect((await request.post(base+'/complete-protocol',{data:{protocol_id:child.protocol_id,expected_protocol_fingerprint:child.protocol_fingerprint,expected_successor_fingerprint:frozen.successor_fingerprint,idempotency_key:'browser-parameters',basis:'METHOD cost grid before frames'}})).ok()).toBeTruthy();
  for(let session=1;session<=3;session++)expect((await request.post(base+'/shadow/advance',{data:{idempotency_key:`cost-${session}`,expected_revision:session-1,session,calendar_previous_session:session-1,source_snapshot_id:`METHOD-cost-${session}`,evidence_kind:'METHOD_CASE',
    bars:[{instrument:'SSE:600519',open_yuan:'10.00',high_yuan:'10.50',low_yuan:'9.50',close_yuan:'10.00',volume_shares:10000,reference_close_yuan:'10.00',completion:'COMPLETE',market_state:'NORMAL',company_actions:'NONE'}],signals:[{instrument:'SSE:600519',forecast_id:`METHOD-signal-${session}`,probability:'0.80'}]}})).ok()).toBeTruthy();
  await page.goto('/');await page.getByRole('button',{name:'历史记录',exact:true}).click();await page.getByRole('button',{name:'研究登记',exact:true}).click();
  await page.getByRole('button',{name:`查看协议 ${parent.protocol_id.slice(0,8)}`,exact:true}).click();
  await page.getByText('后继政策完整设计与验证',{exact:true}).click();await page.getByLabel('后继影子版本').selectOption(frozen.successor_freeze_id);
  await page.getByText('已登记费用压力诊断',{exact:true}).click();await page.getByRole('button',{name:'诊断保存前缀的费用压力',exact:true}).click();
  await expect(page.getByText('METHOD费用场景 6项 · 前缀3 · G5 INCONCLUSIVE · NOT_GRANTED',{exact:true})).toBeVisible({timeout:35000});
  await expect(page.getByRole('cell',{name:'commission_scenario_rate=0.003',exact:true})).toBeVisible();
  await page.getByText('同一轨迹的时间三段',{exact:true}).click();await page.getByRole('button',{name:'保存原轨迹的时间分段',exact:true}).click();
  await expect(page.getByText('METHOD时间三段 · G5 INCONCLUSIVE · NOT_GRANTED',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'重放保存的时间分段',exact:true}).click();await expect(page.getByText('时间分段原工件重放一致',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'重放保存的费用诊断',exact:true}).click();await expect(page.getByText('费用诊断原前缀重放一致',{exact:true})).toBeVisible({timeout:35000});
  await page.reload();await page.getByRole('button',{name:'历史记录',exact:true}).click();await page.getByRole('button',{name:'研究登记',exact:true}).click();await page.getByRole('button',{name:`查看协议 ${parent.protocol_id.slice(0,8)}`,exact:true}).click();
  await page.getByText('后继政策完整设计与验证',{exact:true}).click();await page.getByLabel('后继影子版本').selectOption(frozen.successor_freeze_id);
  await page.getByText('已登记费用压力诊断',{exact:true}).click();await page.getByRole('button',{name:'查看保存的费用诊断',exact:true}).click();
  await expect(page.getByText('METHOD费用场景 6项 · 前缀3 · G5 INCONCLUSIVE · NOT_GRANTED',{exact:true})).toBeVisible();
  await page.getByText('同一轨迹的时间三段',{exact:true}).click();await page.getByRole('button',{name:'查看保存的时间分段',exact:true}).click();await expect(page.getByText('METHOD时间三段 · G5 INCONCLUSIVE · NOT_GRANTED',{exact:true})).toBeVisible();
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/05-time-segments/mobile.png',fullPage:true});
});

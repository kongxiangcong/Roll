import {test,expect} from '@playwright/test';
const freeze='76286d80-4c5d-4262-b97d-ecb856f181f4';
test('successor binds archived same-cutoff CAL support without independent validation claim',async({page,request})=>{
  const api=`http://127.0.0.1:${process.env.ROLL_TEST_API_PORT??'8010'}/api`;
  const previous=await(await request.get(api+'/research/complete-freezes/'+freeze)).json();
  const probability=await(await request.post(api+`/research/complete-freezes/${freeze}/probability-reference`,{data:{expected_complete_protocol_fingerprint:previous.complete_protocol_fingerprint,idempotency_key:'browser-probability',basis:'METHOD saved CAL'}})).json();
  expect((await request.post(api+`/research/probability-references/${probability.reference_id}/block-reference`,{data:{idempotency_key:'browser-block',basis:'METHOD same original calendar'}})).ok()).toBeTruthy();
  const proposal=await(await request.post(api+'/research/policy-successors',{data:{predecessor_freeze_id:freeze,predecessor_policy_fingerprint:previous.fingerprints.policy,version:'METHOD-binding-v2',idempotency_key:'browser-successor',basis:'Same frozen model'}})).json();
  const successor=await(await request.post(api+`/research/policy-successors/${proposal.proposal_id}/freezes`,{data:{policy_fingerprint:proposal.policy_fingerprint,idempotency_key:'browser-freeze',starting_session:0,cash_yuan:'10000.00',positions:[],basis:'METHOD baseline'}})).json();
  const parent=await(await request.get(api+'/research/protocols/'+previous.protocol_id)).json();
  const child=await(await request.post(api+'/research/protocols',{data:{dataset_id:parent.dataset_id,predecessor_id:parent.protocol_id,basis:'No new fitting'}})).json();
  expect((await request.post(api+`/research/policy-successor-freezes/${successor.successor_freeze_id}/complete-protocol`,{data:{protocol_id:child.protocol_id,expected_protocol_fingerprint:child.protocol_fingerprint,expected_successor_fingerprint:successor.successor_fingerprint,idempotency_key:'browser-parameters',basis:'Frozen inherited design'}})).ok()).toBeTruthy();
  async function open(){await page.goto('/');await page.getByRole('button',{name:'历史记录',exact:true}).click();await page.getByRole('button',{name:'研究登记',exact:true}).click();await page.getByRole('button',{name:`查看协议 ${parent.protocol_id.slice(0,8)}`,exact:true}).click();await page.getByText('后继政策完整设计与验证',{exact:true}).click();await page.getByLabel('后继影子版本').selectOption(successor.successor_freeze_id);await page.getByText('后继概率证据绑定',{exact:true}).click();}
  await open();await page.getByRole('button',{name:'读取可关联的概率与区块参照',exact:true}).click();
  await expect(page.getByRole('button',{name:'保存后继概率证据绑定',exact:true})).toBeEnabled();await page.getByRole('button',{name:'保存后继概率证据绑定',exact:true}).click();
  await expect(page.getByText('G3 INCONCLUSIVE · 独立校准未验证 · NOT_GRANTED',{exact:true})).toBeVisible();
  await expect(page.getByText(/^成熟唯一 20 · 已选成熟 \d+ · 缺失或未知日历 20$/)).toHaveCount(2);
  await page.getByRole('button',{name:'校验后继概率绑定工件',exact:true}).click();await expect(page.getByText('概率绑定原工件校验一致 · 未重新评分',{exact:true})).toBeVisible();
  await page.reload();await open();await page.getByRole('button',{name:'查看保存的概率绑定',exact:true}).click();await expect(page.getByText('G3 INCONCLUSIVE · 独立校准未验证 · NOT_GRANTED',{exact:true})).toBeVisible();
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/05-probability-binding/mobile.png',fullPage:true});
});

import {expect,test} from '@playwright/test';
import {resolve} from 'node:path';
test.skip(process.env.ROLL_RISK_LIVE!=='1','Requires preserved ticket22 real/METHOD public HTTP datasets');
test('independent policy keeps actual gaps and immutable scoped quantities visible without a grant',async({page})=>{
  const method=process.env.ROLL_RISK_METHOD==='1';
  const protocols=await (await page.request.get('/api/research/protocols')).json();
  let protocol,policy;
  for(const p of protocols){const policies=await (await page.request.get(`/api/research/protocols/${p.protocol_id}/risk-policies`)).json();if(policies.length){protocol=p;policy=policies[0];break;}}
  expect(policy).toBeTruthy();
  const original=await (await page.request.get('/api/account')).json();
  await page.goto('/');await page.getByRole('button',{name:'历史记录',exact:true}).click();await page.getByRole('button',{name:'研究登记',exact:true}).click();
  await page.getByRole('button',{name:`查看协议 ${protocol.protocol_id.slice(0,8)}`,exact:true}).click();
  const panel=page.getByRole('region',{name:'独立风险政策'});
  await panel.getByRole('button',{name:`查看风险政策 ${policy.policy_id.slice(0,8)}`,exact:true}).click();
  await expect(panel.getByText(/实际验证 INCONCLUSIVE/)).toBeVisible();
  if(method){
    await expect(panel.getByRole('cell',{name:'暂不能计算',exact:true})).toBeVisible();
    const evaluations=await (await page.request.get(`/api/research/risk-policies/${policy.policy_id}/evaluations`)).json();
    const known=evaluations.find((e:{positions:{executable_quantity:string}[]})=>e.positions[0]?.executable_quantity==='400');
    await panel.getByText('全部风险检查',{exact:true}).click();
    await panel.getByRole('button',{name:`查看风险检查 ${known.evaluation_id.slice(0,8)}`,exact:true}).click();
    await expect(panel.getByRole('cell',{name:'400',exact:true})).toBeVisible();
    await expect(panel.getByRole('cell',{name:'650',exact:true})).toBeVisible();
    await panel.getByText('压力、所需事实与门槛',{exact:true}).click();await expect(panel.getByText(/跌停\/停牌或部分成交仍可留下风险/)).toBeVisible();
  }else await expect(panel.getByText('FUNDING_AUTHORIZATION_MISSING',{exact:true})).toHaveCount(2);
  await panel.getByRole('button',{name:'原输入风险重放',exact:true}).click();await expect(panel.getByRole('status')).toContainText('与原风险检查一致 · 联网 0 次');
  expect((await page.request.post('/api/formal/evaluate',{data:{basis_type:'RISK_POLICY',policy_id:policy.policy_id,action:'EXIT'}})).status()).toBe(403);
  expect(await (await page.request.get('/api/account')).json()).toEqual(original);
  expect((await (await page.request.get('/api/capabilities')).json()).state).toBe('UNGRANTED');
  await expect(page.getByRole('navigation',{name:'主导航'}).getByRole('button')).toHaveCount(5);
  await panel.screenshot({path:resolve(`../.scratch/roll-p0/evidence/22/22-${method?'method-quantity':'real-gap'}.png`)});
});

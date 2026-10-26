import {test,expect} from '@playwright/test';

test('action versions retain truncated inventory and unknown fulfillment through original links',async({page,request})=>{
  const api=`http://127.0.0.1:${process.env.ROLL_TEST_API_PORT??'8010'}/api`;
  const plan=await (await request.post(api+'/research/collections',{data:{instrument:'SSE:600362',basis:'Isolated browser action source'}})).json();
  const receipt=await (await request.post(api+`/research/collections/${plan.plan_id}/sse-company-actions`,{data:{basis:'METHOD saved action originals'}})).json();
  const assessed=await request.post(api+`/research/collections/${plan.plan_id}/sse-action-assessments`,{data:{source_receipt_id:receipt.receipt_id,basis:'Explicit observed original schema'}});
  expect(assessed.ok()).toBeTruthy();
  const listing=await (await request.get(api+'/market/list')).json();
  expect((await request.post(api+'/market/watch',{data:{operation:'ADD',instrument:'SSE:600362',expected_list_version:listing.version}})).ok()).toBeTruthy();
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  const stock=page.getByRole('article',{name:'SSE:600362',exact:true});
  await stock.getByText('查看公司行动与旧义务',{exact:true}).click();
  await stock.getByRole('button',{name:'查询保存的行动依据'}).click();
  await stock.getByText('行动观察版本',{exact:false}).click();
  await expect(stock.getByText('现金分派：返回5/6条，缺1条',{exact:false})).toBeVisible();
  await expect(stock.getByText('单位未验证',{exact:false}).first()).toBeVisible();
  const link=stock.getByRole('link',{name:'行动原件'}).first();
  expect((await request.get((await link.getAttribute('href'))!)).ok()).toBeTruthy();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/04-actions/mobile.png',fullPage:true});
  await stock.getByLabel('行动系统已知截至（留空查询当前）').fill('2026-10-14T17:59');
  await stock.getByRole('button',{name:'查询保存的行动依据'}).click();
  await expect(stock.getByText('尚无已解析行动版本',{exact:true})).toBeVisible();
  expect((await (await request.get(api+'/account')).json()).version).toBe(0);
});

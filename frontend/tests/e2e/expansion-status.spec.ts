import {test,expect} from '@playwright/test';

test('single stock status exposes reported listing and cutoff while keeping full status unknown',async({page,request})=>{
  const api=`http://127.0.0.1:${process.env.ROLL_TEST_API_PORT??'8010'}/api`;
  const plan=await (await request.post(api+'/research/collections',{data:{instrument:'SSE:600362',basis:'Isolated browser state source'}})).json();
  const captured=await request.post(api+`/research/collections/${plan.plan_id}/sse-company-contract`,{data:{basis:'METHOD pinned company contract source'}});
  expect(captured.ok()).toBeTruthy();
  const listing=await (await request.get(api+'/market/list')).json();
  expect((await request.post(api+'/market/watch',{data:{operation:'ADD',instrument:'SSE:600362',expected_list_version:listing.version}})).ok()).toBeTruthy();
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  const stock=page.getByRole('article',{name:'SSE:600362',exact:true});
  await stock.getByText('查看证券状态来源',{exact:true}).click();
  await page.clock.setFixedTime(new Date(Date.now()+300000));
  await stock.getByRole('button',{name:'查询保存的状态依据'}).click();
  await expect(stock.getByText('来源报告：上市',{exact:false})).toBeVisible();
  await expect(stock.getByRole('status').filter({hasText:'完整交易状态未知'})).toBeVisible();
  const raw=stock.getByRole('link',{name:'公司信息原件'});
  expect((await request.get((await raw.getAttribute('href'))!)).ok()).toBeTruthy();
  await stock.getByLabel('系统已知截至（留空查询当前）').fill('2026-10-14T17:59');
  await stock.getByRole('button',{name:'查询保存的状态依据'}).click();
  await expect(stock.getByText('来源报告：上市',{exact:false})).not.toBeVisible();
  await expect(stock.getByRole('status').filter({hasText:'完整交易状态未知'})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/03-status/mobile.png',fullPage:true});
});

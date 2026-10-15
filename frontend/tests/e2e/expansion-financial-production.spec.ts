import {test,expect} from '@playwright/test';

test('reads the closed one-shot production income archive without acquisition',async({page,request})=>{
  let acquisitions=0;
  await page.route('**/income/collect',async route=>{acquisitions++;await route.abort();});
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('查看利润表',{exact:true}).click();
  await page.getByRole('button',{name:'查询保存的利润表',exact:true}).click();
  await expect(page.getByText('2026-06-30 · 合并 · 年初累计 · CNY 元 · 版本1',{exact:true})).toBeVisible();
  await expect(page.getByText('307154938743',{exact:true})).toBeVisible();
  await expect(page.getByText('当前收到的来源观察 · 非历史PIT',{exact:true})).toHaveCount(5);
  const links=page.getByRole('link',{name:'利润表原响应',exact:true});await expect(links).toHaveCount(5);
  expect((await request.get((await links.first().getAttribute('href'))!)).status()).toBe(200);
  expect((await request.get((await page.getByRole('link',{name:'口径PDF第62页',exact:true}).first().getAttribute('href'))!)).status()).toBe(200);
  await page.reload();await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('查看利润表',{exact:true}).click();await page.getByRole('button',{name:'查询保存的利润表',exact:true}).click();
  await expect(page.getByText('2026-06-30 · 合并 · 年初累计 · CNY 元 · 版本1',{exact:true})).toBeVisible();
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  expect(acquisitions).toBe(0);
  await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/09-financial/integration-mobile.png',fullPage:true});
});

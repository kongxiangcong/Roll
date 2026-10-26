import {test,expect} from '@playwright/test';

test('single stock reads versioned income originals without granting capability',async({page,request})=>{
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  await page.getByText('查看利润表',{exact:true}).click();
  await page.getByRole('button',{name:'查询保存的利润表',exact:true}).click();
  await expect(page.getByText('尚无已保存利润表',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'有限采集利润表',exact:true}).click();
  await expect(page.getByText('2026-06-30 · 合并 · 年初累计 · CNY 元 · 版本1',{exact:true})).toBeVisible();
  await expect(page.getByText('307154938743',{exact:true})).toBeVisible();
  await expect(page.getByText('METHOD工程证据 · 非历史PIT',{exact:true}).first()).toBeVisible();
  const original=page.getByRole('link',{name:'利润表原响应',exact:true}).first();
  expect((await request.get((await original.getAttribute('href'))!)).status()).toBe(200);
  expect((await request.get((await page.getByRole('link',{name:'口径PDF第62页',exact:true}).first().getAttribute('href'))!)).status()).toBe(200);
  await page.reload();await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('查看利润表',{exact:true}).click();
  await page.getByRole('button',{name:'查询保存的利润表',exact:true}).click();
  await expect(page.getByText('2026-06-30 · 合并 · 年初累计 · CNY 元 · 版本1',{exact:true})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/09-financial/mobile.png',fullPage:true});
});

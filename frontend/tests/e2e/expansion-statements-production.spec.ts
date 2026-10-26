import {test,expect} from '@playwright/test';

test('closed actual three statements read without new acquisition',async({page,request})=>{
  let acquisitions=0;await page.route('**/collect',async route=>{acquisitions++;await route.abort();});
  await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('三表联读',{exact:true}).click();
  await page.getByRole('button',{name:'查询保存的三表',exact:true}).click();
  const matched=page.getByRole('region',{name:'三表 2026-06-30 MATCHED',exact:true});
  await expect(matched.getByText('三表口径匹配',{exact:true})).toBeVisible();
  await expect(matched.getByText('资产−负债−权益：0；来源舍入容差：1.5；差异在来源舍入范围内',{exact:true})).toBeVisible();
  await matched.getByText('资产负债表 · 版本1 · 报告期末时点',{exact:true}).click();
  await matched.getByText('现金流量表 · 版本1 · 年初累计',{exact:true}).click();
  await expect(matched.getByText('293265142356',{exact:true})).toBeVisible();
  await expect(matched.getByText('-23434970323',{exact:true})).toBeVisible();
  for(const label of ['资产负债表原响应','现金流量表原响应','口径PDF第59页','口径PDF第66页'])expect((await request.get((await matched.getByRole('link',{name:label,exact:true}).getAttribute('href'))!)).status()).toBe(200);
  await page.reload();await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('三表联读',{exact:true}).click();await page.getByRole('button',{name:'查询保存的三表',exact:true}).click();
  await expect(page.getByRole('region',{name:'三表 2026-06-30 MATCHED',exact:true})).toBeVisible();
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  expect(acquisitions).toBe(0);
  await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/10-statements/production-mobile.png',fullPage:true});
});

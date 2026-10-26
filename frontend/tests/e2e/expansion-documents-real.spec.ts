import {test,expect} from '@playwright/test';
test('actual Docling parse keeps archived PDF page, table cells and original link',async({page,request})=>{
 await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('查看利润表',{exact:true}).click();
 await page.getByRole('button',{name:'查询保存的利润表',exact:true}).click();
 const fact=page.getByRole('region',{name:/利润表 2025-09-30/}).first();await fact.getByText('PDF表格与页码解析',{exact:true}).click();
 await fact.getByRole('button',{name:'查询文档解析记录',exact:true}).click();
 await fact.getByRole('button',{name:'查看本次表格与文本',exact:true}).first().click();
 await expect(fact.getByText(/本地文档派生 · 10—10页 · COMPLETE/).first()).toBeVisible();
 await expect(fact.getByRole('cell',{name:'7,089,672,734',exact:true}).first()).toBeVisible();
 const link=fact.getByRole('link',{name:'原PDF第10页',exact:true}).first();
 expect((await request.get((await link.getAttribute('href'))!)).status()).toBe(200);
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/12-docling/real-mobile.png',fullPage:true});
});

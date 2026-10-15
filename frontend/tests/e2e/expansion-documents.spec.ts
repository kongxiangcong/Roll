import {test,expect} from '@playwright/test';

test('METHOD document derivation preserves page references and raw bracketed amount',async({page,request})=>{
 await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('查看利润表',{exact:true}).click();await page.getByRole('button',{name:'查询保存的利润表',exact:true}).click();
 const fact=page.getByRole('region',{name:'利润表 2026-06-30 版本1',exact:true});await fact.getByText('PDF表格与页码解析',{exact:true}).click();
 await fact.getByLabel('解析起页',{exact:true}).fill('66');await fact.getByLabel('解析末页',{exact:true}).fill('67');
 await fact.getByRole('button',{name:'解析已存PDF选定页',exact:true}).click();await fact.getByRole('button',{name:'查看本次表格与文本',exact:true}).click();
 await expect(fact.getByText('METHOD工程派生 · 66—67页 · COMPLETE',{exact:false})).toBeVisible();
 await expect(fact.getByRole('cell',{name:'(23,434,970,323)',exact:true})).toBeVisible();
 await expect(fact.getByText('METHOD 合并现金流量表（续） 人民币元 附注68',{exact:true})).toBeVisible();
 const link=fact.getByRole('link',{name:'原PDF第67页',exact:true}).first();expect((await request.get((await link.getAttribute('href'))!)).status()).toBe(200);
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/12-docling/mobile.png',fullPage:true});
 await page.reload();await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('查看利润表',{exact:true}).click();await page.getByRole('button',{name:'查询保存的利润表',exact:true}).click();await fact.getByText('PDF表格与页码解析',{exact:true}).click();await fact.getByRole('button',{name:'查询文档解析记录',exact:true}).click();await expect(fact.getByRole('button',{name:'查看本次表格与文本',exact:true})).toBeVisible();
});

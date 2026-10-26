import {test,expect} from '@playwright/test';
test('METHOD news keeps excerpt separate from archived body and persists headline gaps',async({page,request})=>{
 await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('查看近期新闻',{exact:true}).click();
 await page.getByRole('button',{name:'有限采集近期新闻',exact:true}).click();
 const body=page.getByRole('region',{name:'新闻 METHOD 江西铜业公告',exact:true});await expect(body.getByText('METHOD工程证据',{exact:true})).toBeVisible();
 await expect(body.getByText('METHOD archived full article.',{exact:true})).toBeVisible();await body.getByText('列表摘要（非全文）',{exact:true}).click();await expect(body.getByText('列表摘要不是正文',{exact:true})).toBeVisible();
 const gap=page.getByRole('region',{name:'新闻 METHOD 标题保留',exact:true});await expect(gap.getByText('正文缺口：NOT_FETCHED_BODY_BUDGET',{exact:true})).toBeVisible();
 const raw=body.getByRole('link',{name:'正文HTML原件',exact:true});expect((await request.get((await raw.getAttribute('href'))!)).status()).toBe(200);
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/14-news/mobile.png',fullPage:true});
 await page.reload();await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('查看近期新闻',{exact:true}).click();await page.getByRole('button',{name:'查询保存的新闻',exact:true}).click();await expect(body.getByText('METHOD archived full article.',{exact:true})).toBeVisible();
});

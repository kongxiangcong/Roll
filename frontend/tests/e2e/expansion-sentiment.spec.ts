import {test,expect} from '@playwright/test';
test('limited sentiment shows saved labels, reject reasons and evaluation limits',async({page,request})=>{
 let classifications=0;page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/classify'))classifications++;});
 await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
 await page.getByText('受限情绪研究',{exact:true}).click();await page.getByRole('button',{name:'查询已保存分类',exact:true}).click();
 await expect(page.getByText(/覆盖 20%/)).toBeVisible();
 await expect(page.getByText(/能力 RESEARCH_LIMITED/)).toBeVisible();
 await expect(page.getByText(/负向召回 0.200/)).toBeVisible();
 await expect(page.getByText(/拒判计入该真实类别的漏判/)).toBeVisible();
 await expect(page.getByText(/冻结门槛未通过/)).toBeVisible();
 await expect(page.getByText(/江西铜业600362.SH\)：2026年中报净利润.*正向/)).toBeVisible();
 await expect(page.getByText(/有色金属行业资金流出榜.*拒判：资金流汇总类/)).toBeVisible();
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:process.env.ROLL_SENTIMENT_SCREENSHOT_PATH??'../.scratch/roll-capability-expansion/evidence/16-sentiment/mobile.png',fullPage:true});
 expect(classifications).toBe(0);
});

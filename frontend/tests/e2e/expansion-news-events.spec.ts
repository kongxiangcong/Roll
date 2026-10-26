import {test,expect} from '@playwright/test';
test('actual saved news is grouped by unique event with registered-identity association',async({page,request})=>{
 let collections=0;page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/collect'))collections++;});
 await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('查看近期新闻',{exact:true}).click();
 await page.getByRole('button',{name:'查询保存的新闻',exact:true}).click();
 const response=await request.get('/api/market/news/SSE:600362');expect(response.status()).toBe(200);const value=await response.json();
 expect(value.facts.length).toBe(10);expect(value.unique_event_count).toBe(10);expect(value.network_calls).toBe(0);
 await expect(page.getByText(/共 10 条新闻，归并为 10 个唯一事件/)).toBeVisible();
 await expect(page.getByRole('region',{name:/^事件 /})).toHaveCount(10);
 const subject=page.getByRole('region',{name:'新闻 江西铜业：拟与控股股东签订2027-2029年度日常关联交易合同',exact:true});
 await expect(subject.getByText(/证券关联 明确公司主体/)).toBeVisible();
 const pcb=page.getByRole('region',{name:'新闻 PCB概念上涨1.92%，7股主力资金净流入超亿元',exact:true});
 await expect(pcb.getByText(/证券关联 不相关/)).toBeVisible();
 const industry=page.getByRole('region',{name:'新闻 8.96亿元资金今日流入有色金属股',exact:true});
 await expect(industry.getByText(/证券关联 行业背景/)).toBeVisible();
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/15-events/mobile.png',fullPage:true});expect(collections).toBe(0);
});

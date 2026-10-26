import {test,expect} from '@playwright/test';
test('actual saved news list and HTML originals remain readable without acquisition',async({page,request})=>{
 let collections=0;page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/collect'))collections++;});
 await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('查看近期新闻',{exact:true}).click();await page.getByRole('button',{name:'查询保存的新闻',exact:true}).click();
 const response=await request.get('/api/market/news/SSE:600362');expect(response.status()).toBe(200);const value=await response.json();expect(value.facts.length).toBe(10);expect(value.network_calls).toBe(0);
 const first=value.facts.find((f:{body_sha256:string|null})=>!!f.body_sha256);expect(first).toBeTruthy();const item=page.getByRole('region',{name:`新闻 ${first.title}`,exact:true});
 await expect(item.getByText('实际收到的近期观察',{exact:true})).toBeVisible();await expect(item.getByText('正文缺口：ARCHIVED_PENDING_EXTRACTION',{exact:true})).toBeVisible();
 const original=item.getByRole('link',{name:'正文HTML原件',exact:true});const body=await request.get((await original.getAttribute('href'))!);expect(body.status()).toBe(200);expect((await body.body()).length).toBeGreaterThan(100);
 await expect(page.getByText('上游文档最多近期100条，当前锁定SDK只取默认排序的第一页10条；最多取其中3篇正文。不代表完整历史或已核实证券关联。来源默认关闭，请在来源配置显式启用。',{exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/14-news/production-mobile.png',fullPage:true});expect(collections).toBe(0);
});

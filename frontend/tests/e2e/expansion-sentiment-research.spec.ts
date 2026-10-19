import {test,expect} from '@playwright/test';

test('saved real Chinese FinBERT research run exposes three labels, frozen limits and version trace',async({page,request})=>{
 let classifications=0;page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/classify'))classifications++;});
 const api=await request.get('/api/market/sentiment/SSE:600362');expect(api.ok()).toBeTruthy();const saved=await api.json();
 expect(saved.run.profile).toBe('finbert-adaptation-01');expect(saved.run.evidence_kind).toBe('REAL_LOCAL_CLASSIFICATION');expect(saved.counts).toEqual({NEGATIVE:1,POSITIVE:2,ABSTAIN_NO_COMPANY_OBJECT:7,NEUTRAL:2});
 await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
 await page.getByText('受限情绪研究',{exact:true}).click();await expect(page.getByRole('button',{name:'运行中文FinBERT研究候选',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'查询已保存分类',exact:true}).click();
 await expect(page.getByText(/实际支持标签：中性、正向、负向/)).toBeVisible();
 await expect(page.getByText(/覆盖 42%/)).toBeVisible();await expect(page.getByText(/实际本地分类.*能力 RESEARCH_LIMITED/)).toBeVisible();
 await expect(page.getByText(/冻结主留出集120条：二类 macro-F1 1.000、三类 macro-F1 1.000/)).toBeVisible();
 await expect(page.getByText(/非独立标注的有限挑战集通过/)).toBeVisible();
 await expect(page.getByText(/评测 中性：支持 30 条 \/ 21 事件；召回 1.000/)).toBeVisible();
 await expect(page.getByText(/董事会会议考虑及批准第三季度业绩.*中性/)).toBeVisible();
 await expect(page.getByText(/美迪西：关于2026年第一次临时股东会通知的更正公告.*拒判：无明确公司对象/)).toBeVisible();
 await page.getByText('查看对象输入与版本',{exact:true}).first().click();await expect(page.getByText(/输入版本 sentiment-object-v2.1-shared-predicate/).first()).toBeVisible();
 await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/16-sentiment/trained-candidate-01/desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
 await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/16-sentiment/trained-candidate-01/mobile.png',fullPage:true});
 expect(classifications).toBe(0);expect((await request.get('/api/account')).ok()).toBeTruthy();
});

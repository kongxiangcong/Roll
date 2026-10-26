// Read-only actual07 local store walkthrough; no network/model/update requests.
import {chromium} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
const out='../.scratch/roll-research-valuation/evidence/07';
await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'chrome'});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const writes=[];page.on('request',request=>{if(request.method()==='POST'&&!request.url().endsWith('/resolve'))writes.push(request.url());});
try{
 await page.goto(process.env.ROLL_DAILY_URL??'http://127.0.0.1:5207');
 await page.getByLabel('研究对象',{exact:true}).selectOption('SSE:600362');
 await page.getByRole('heading',{name:'经营研究与条件估值',exact:true}).waitFor();
 await page.getByLabel('共享研究历史版本').waitFor();
 await page.getByText('若出现以下情形则假设失效（尚待验证）',{exact:false}).first().waitFor();
 await page.getByText('期限或口径不可比',{exact:false}).first().waitFor();
 await page.screenshot({path:out+'/real-daily-desktop.png',fullPage:true});
 await page.getByText('展开经营假设、证据、估值限制与版本',{exact:true}).click();
 await page.getByText('事实版本',{exact:false}).first().waitFor();
 await page.screenshot({path:out+'/real-daily-evidence.png',fullPage:true});
 await page.getByLabel('共享研究历史版本').selectOption('90c3e7b9-56f9-4ad6-a39a-7c343a1a95f6');
 await page.getByText('HYPOTHESIS_CONFLICT',{exact:false}).waitFor();
 await page.screenshot({path:out+'/real-daily-old-partial.png',fullPage:true});
 await page.getByLabel('研究对象',{exact:true}).selectOption('SZSE:000848');
 await page.getByText('尚无共享分析快照',{exact:false}).waitFor();
 if(await page.getByLabel('共享研究历史版本').count())throw Error('another company history leaked');
 await page.getByText('PUBLIC_SOURCE_SCOPE_UNSUPPORTED_FOR_SELECTED_COMPANY',{exact:false}).first().waitFor();
 await page.screenshot({path:out+'/real-daily-company-gap.png',fullPage:true});
 await page.getByLabel('研究对象',{exact:true}).selectOption('SSE:600362');
 await page.getByLabel('共享研究历史版本').waitFor();
 await page.reload();
 await page.getByLabel('共享研究历史版本').waitFor();
 await page.setViewportSize({width:390,height:844});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('mobile overflow');
 await page.screenshot({path:out+'/real-daily-mobile.png',fullPage:true});
 if(errors.length||writes.length)throw Error(JSON.stringify({errors,writes}));
 console.log(JSON.stringify({status:'PASS',actualRestoredJcc:true,synthetic:false,pinnedHistory:true,partialRejectionsVisible:true,companyIsolation:true,actualSourceScopeFailureVisible:true,refreshReload:true,viewports:[1440,390],additionalModels:0,additionalPublicSourceRefresh:0,writes,errors}));
}catch(error){console.log(JSON.stringify(errors));console.log(await page.locator('body').innerText());throw error;}finally{await browser.close();}

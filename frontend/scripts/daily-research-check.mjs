// Synthetic public webpage flow. No fixtures are presented as real research.
import {chromium} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
const out='../.scratch/roll-research-valuation/evidence/07';
await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'chrome'});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const issuer=(id,name,instrument)=>({company_id:id,legal_name:name,listings:[{listing_id:instrument}]});
const companies={a:issuer('a','METHOD甲公司','SSE:600362'),b:issuer('b','METHOD乙公司','SZSE:000848')};
const snapshot=id=>({snapshot_id:id+'-snapshot',company_id:id,content_sha256:id.repeat(64),core_sha256:id.repeat(64),as_of:'2026-10-26T08:00:00Z',generated_at:'2026-10-26T08:02:00Z',core:{attention_reasons:[{text:id==='a'?'METHOD甲关注理由':'METHOD乙关注理由',fact_version_ids:['f']}],hypotheses:[],counterevidence:[],limitations:['仅工程样例'],valuation_unavailable_reason:'缺少权益桥接'}});
const view=id=>({company:companies[id],snapshot:snapshot(id),attention_reasons:snapshot(id).core.attention_reasons,catalysts:[],risks:[{text:'METHOD下行风险'}],valuation:{status:'blocked',usable_range:false,scenarios:[],current_pricing_gaps:['缺少权益桥接']},changes:{OPERATING_EVIDENCE:{evidence_changed:false},PRICE:{status:'NOT_COMPARABLE',reason:'报价缺口'},VALUATION_ASSUMPTION_OR_METHOD:{status:'NOT_COMPARABLE',reason:'方法缺口'}},information_state:{research_as_of:'2026-10-26T08:00:00Z',knowledge_as_of:'2026-10-26T08:00:00Z',research_basis_generated_at:'2026-10-26T08:02:00Z',material_dates:[],checks:[],research_verification_refreshed:false},latest_checks:[],evidence:[],conflicts:[],gap:'缺少权益桥接',conflict_note:'期限或依据不一致时并列解释'});
let fail=false,updates=0;
await page.route('**/api/**',async route=>{
 const url=new URL(route.request().url()),p=url.pathname;
 if(p==='/api/market/list')return route.fulfill({json:{members:Object.values(companies).map(c=>({instrument:c.listings[0].listing_id,identity:{name:c.legal_name},watched:true,holding:null}))}});
 if(p==='/api/company-research/resolve'){const c=Object.values(companies).find(c=>c.listings[0].listing_id===route.request().postDataJSON().query);return route.fulfill({json:{status:'RESOLVED',company:c,listings:c.listings}});}
 if(p.endsWith('/daily'))return route.fulfill({json:view(p.includes('/a/')?'a':'b')});
 if(p.endsWith('/snapshots')){const id=p.includes('/a/')?'a':'b';return route.fulfill({json:{snapshots:[snapshot(id)],total:1}});}
 if(p.endsWith('/requests')){updates++;return route.fulfill(fail?{status:503,json:{detail:'METHOD archive unavailable; explicit retry'}}:{status:201,json:{job_id:'queued',status:'QUEUED'}});}
 if(p.startsWith('/api/observation-updates/'))return route.fulfill({json:{settings:{revision:1,enabled:true,research_postclose:false,news_refresh:false},jobs:[],observations:[],sources:[],health:{},worker:{worker_state:'RUNNING'},offline_coverage:{sessions:[],gaps:[]}}});
 if(p==='/api/account')return route.fulfill({json:{version:0,positions:[],permission_profile:[],cash_balance:null,confirmed_at:null}});
 if(p==='/api/intents')return route.fulfill({json:{intents:[]}});
 if(p==='/api/reviews/summary')return route.fulfill({json:{calendar:{phase:'AFTER_CLOSE'},latest:null,health:{worker_state:'RUNNING',backlog:0},coverage_gap:null}});
 if(p==='/api/assistance/runs')return route.fulfill({json:[]});
 return route.fulfill({json:{}});
});
try{
 await page.goto(process.env.ROLL_DAILY_URL??'http://127.0.0.1:5189');
 await page.getByLabel('研究对象',{exact:true}).waitFor();
 await page.getByText('METHOD甲关注理由',{exact:true}).waitFor();
 await page.getByText('当前估值：blocked',{exact:false}).waitFor();
 await page.getByLabel('研究对象',{exact:true}).selectOption('SZSE:000848');
 await page.getByText('METHOD乙关注理由',{exact:true}).waitFor();
 if(await page.getByText('METHOD甲关注理由',{exact:true}).count())throw Error('cross-company research leaked');
 await page.getByLabel('共享研究历史版本').selectOption('b-snapshot');
 await page.getByRole('button',{name:'检查已归档材料并更新研究',exact:true}).click();
 await page.getByText('已提交研究更新任务',{exact:false}).waitFor();
 fail=true;
 await page.getByRole('button',{name:'检查已归档材料并更新研究',exact:true}).click();
 await page.getByRole('alert').filter({hasText:'METHOD archive unavailable'}).waitFor();
 fail=false;
 await page.getByRole('button',{name:'检查已归档材料并更新研究',exact:true}).click();
 await page.getByText('METHOD乙关注理由',{exact:true}).waitFor();
 await page.reload();
 await page.getByText('METHOD甲关注理由',{exact:true}).waitFor();
 await page.screenshot({path:out+'/synthetic-daily-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('mobile overflow');
 await page.screenshot({path:out+'/synthetic-daily-mobile.png',fullPage:true});
 if(errors.length)throw Error(errors.join('\n'));
 console.log(JSON.stringify({status:'PASS',synthetic:true,companySwitch:true,pinnedHistory:true,refreshFailureRetry:true,reload:true,updates,errors}));
}catch(error){console.log(JSON.stringify(errors));console.log(await page.locator('body').innerText());throw error;}finally{await browser.close();}

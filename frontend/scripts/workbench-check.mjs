import {chromium} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
const out='../.scratch/workbench-redesign/evidence';
await mkdir(out,{recursive:true});
const before=process.argv.includes('--before');
const account={version:2,cash_balance:'82340.50',broker_available:'80000',broker_frozen:'2340.50',positions:[{instrument:'SSE:600362',quantity:'1200',sellable_quantity:'1000',reference_cost:'26.80'}],permission_profile:[],confirmed_at:'2026-10-23T08:00:00+08:00',effective_at:'2026-10-23T08:00:00+08:00',state:'CONFIRMED'};
const result={return_pct:2.34,max_drawdown_pct:-4.52,trades:[],nav:[],open_quantity:0};
const run={run_id:'fixture-run',status:'COMPLETE',phase:'COMPLETE',as_of:'2026-10-22',started_at:'2026-10-23',sources:[{source_id:'sh.600362',provider:'Fixture / 验收数据',first_date:'2026-07-01',last_date:'2026-10-22',row_count:80,price_unit:'CNY',adjustment:'原价',received_at:'2026-10-23T08:00:00Z',sha256:'a'.repeat(64)}],gaps:[],assessment:{bias:'中性',summary:'验收示例：价格变化与成交量尚未形成一致证据。需要结合行业变化、财务事实与后续完整日线继续观察。',valid_until:'2026-10-24T08:00:00Z',basis_as_of:'2026-10-22',evidence:[{source_id:'sh.600362',reason:'近期完整日线可用于观察量价关系。'}],counterevidence:['短期价格变化不等于趋势已经确认。'],change_conditions:['新增日线或公司公告改变当前证据。'],limitations:['仅供界面验收，非真实研究结论。']},backtest:{start:'2026-08-01',end:'2026-10-22',data_start:'2026-07-01',assumptions:['费用与执行假设仅作界面测试。'],strategy:result,buy_hold:{...result,return_pct:1.2},excluded_before_action_free_tail:[]},reflections:[]};
const observation={settings:{revision:1,enabled:true,news_postclose:true,financial_postclose:false,market_postclose:true,news_refresh:false,classify:false,profile:'legacy'},jobs:[],observations:[],sources:[],health:{},worker:{worker_state:'RUNNING',worker_limit:45},offline_coverage:{sessions:[],gaps:[]}};
const browser=await chromium.launch({channel:'chrome'});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
let mode='complete',posts=0,startAttempts=0;
await page.route('**/api/**',async route=>{
 const path=new URL(route.request().url()).pathname;
 if(route.request().method()==='POST'){posts++;if(path==='/api/assistance/runs'&&++startAttempts>1){mode='running';return route.fulfill({json:{...run,status:'RUNNING'}});}return route.fulfill({status:503,json:{detail:'验收模拟：服务暂不可用，请重试'}});}
 let data=path==='/api/intents'?{intents:[]}:path==='/api/account'?account:path==='/api/assistance/runs'?(mode==='empty'?[]:[{...run,status:mode==='running'?'RUNNING':mode==='failed'?'FAILED':'COMPLETE'}]):path==='/api/assistance/runs/fixture-run'?{...run,status:mode==='running'?'RUNNING':mode==='failed'?'FAILED':'COMPLETE',error:mode==='failed'?{code:'SOURCE_UNAVAILABLE'}:undefined}:path.startsWith('/api/observation-updates/')?observation:path==='/api/reviews/summary'?{calendar:{phase:'AFTER_CLOSE'},latest:null,health:{worker_state:'RUNNING',backlog:0},coverage_gap:null}:{};
 await route.fulfill({json:data});
});
try{
 await page.goto(process.env.WORKBENCH_URL??'http://127.0.0.1:5188');
 await page.getByText(run.assessment.summary,{exact:true}).waitFor();
 await page.screenshot({path:`${out}/${before?'before':'after'}-desktop.png`,fullPage:true});
 if(before){await page.setViewportSize({width:390,height:844});await page.screenshot({path:`${out}/before-mobile.png`,fullPage:true});}
 else{
  const assert=(v,m)=>{if(!v)throw Error(m);};
  await page.getByLabel('复盘内容',{exact:true}).fill('尚未保存的复盘草稿');
  await page.getByRole('tab',{name:'事实与来源'}).click();
  await page.getByRole('region',{name:'日常观察状态',exact:true}).waitFor();
  await page.getByRole('tab',{name:'事实与来源'}).press('ArrowRight');
  await page.getByRole('heading',{name:'今天的事实观察',exact:true}).waitFor();
  await page.getByRole('tab',{name:'观察复盘'}).press('Home');
  assert(await page.getByLabel('复盘内容',{exact:true}).inputValue()==='尚未保存的复盘草稿','draft lost');
  await page.getByRole('button',{name:'保存这次复盘',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'验收模拟'}).waitFor();
  assert(await page.getByLabel('复盘内容',{exact:true}).inputValue()==='尚未保存的复盘草稿','error lost draft');
  await page.getByRole('button',{name:'记录实际买卖',exact:true}).click();
  await page.getByLabel('成交证券代码').waitFor();
  await page.getByRole('button',{name:'收起成交录入',exact:true}).click();
  await page.reload();
  await page.getByText(run.assessment.summary,{exact:true}).waitFor();
  for(const width of [1440,1024,390,320]){
   await page.setViewportSize({width,height:844});
   for(const name of ['研究判断','事实与来源','观察复盘']){
    await page.getByRole('tab',{name}).click();
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow ${width} ${name}`);
   }
   await page.getByRole('tab',{name:'研究判断'}).click();
   await page.screenshot({path:`${out}/after-${width}.png`,fullPage:true});
  }
  await page.emulateMedia({reducedMotion:'reduce'});
  for(const state of ['empty','running','failed']){mode=state;await page.reload();await page.getByRole('heading',{name:'研究辅助与探索回测',exact:true}).waitFor();if(state==='empty')await page.getByText('开始这次研究',{exact:true}).waitFor();else await page.getByText(run.assessment.summary,{exact:true}).waitFor();await page.screenshot({path:`${out}/${state}.png`,fullPage:true});}
  mode='empty';await page.reload();await page.getByText('开始这次研究',{exact:true}).waitFor();
  await page.getByRole('button',{name:'开始研究与回测',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'验收模拟'}).waitFor();
  await page.getByRole('button',{name:'开始研究与回测',exact:true}).click();
  await page.getByRole('button',{name:'研究进行中',exact:true}).waitFor();
  assert(await page.getByRole('button',{name:'研究进行中',exact:true}).isDisabled(),'duplicate run enabled');
  assert(posts===3,'unexpected writes');assert(errors.length===0,errors.join('\n'));
  console.log(JSON.stringify({status:'PASS',browser:browser.version(),viewports:[1440,1024,390,320],mainActionRetry:true,draftRetention:true,keyboardTabs:true,errorRecovery:true,states:['empty','running','failed'],posts,errors}));
 }
}finally{await browser.close();}

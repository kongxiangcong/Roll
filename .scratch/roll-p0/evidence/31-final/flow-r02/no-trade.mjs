import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdirSync,writeFileSync} from 'node:fs';
import {resolve,join} from 'node:path';
const tree=resolve(import.meta.dirname,'../../../../..');
const require=createRequire(join(tree,'frontend/package.json'));
const {chromium,expect}=require('@playwright/test');
assert.equal(process.env.ROLL_FINAL31_BEHAVIOR_RELEASE,'1');
const api=process.env.ROLL_FINAL31_API,ui=process.env.ROLL_FINAL31_UI,out=process.env.ROLL_FINAL31_UI_OUTPUT;
assert.ok(api.startsWith('http://127.0.0.1:')&&ui.startsWith('http://127.0.0.1:'));
mkdirSync(out,{recursive:true});
const raw=[],receipt={namespace:'METHOD_ENGINEERING',system_usable:false,clock_modified:false,checks:{},errors:[],observations:[]};
const localMinute=()=>new Date(Date.now()-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16);
const shanghaiDate=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Shanghai',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
async function request(path,body){const response=await fetch(api+path,body===undefined?{}:{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});const text=await response.text();raw.push({at:new Date().toISOString(),path,body,status:response.status,text});assert.ok(response.ok,`${path}: ${text}`);return JSON.parse(text);}
const browser=await chromium.launch({headless:true,channel:'chrome'});
try{
 const page=await browser.newPage();
 const responses=[];
 page.on('pageerror',e=>receipt.errors.push(String(e)));
 page.on('response',r=>{if(r.url().includes('/api/'))responses.push((async()=>{const text=await r.text();raw.push({at:new Date().toISOString(),url:r.url(),method:r.request().method(),body:r.request().postData(),status:r.status(),text});if(r.status()>=500)receipt.errors.push(`${r.status()} ${r.url()}`);})().catch(e=>receipt.errors.push(String(e))));});
 const nav=name=>page.getByRole('navigation',{name:'主导航'}).getByRole('button',{name,exact:true}).click();
 await page.goto(ui);await expect(page.getByRole('navigation',{name:'主导航'}).getByRole('button')).toHaveCount(5);
 receipt.actual_started_at=new Date().toISOString();receipt.actual_shanghai_date=shanghaiDate();
 await nav('同步账户');receipt.baseline_effective_minute=localMinute();
 await page.getByLabel('事实截至时点').fill(receipt.baseline_effective_minute);
 await page.getByLabel('依据与来源').fill('METHOD engineering current-minute cash-only account');
 await page.getByLabel('账面现金（元）').fill('10000.00');await page.getByLabel('券商可用资金（元）').fill('10000.00');await page.getByLabel('冻结资金（元）').fill('0.00');
 await page.getByRole('button',{name:'预览差异',exact:true}).click();await page.getByRole('button',{name:'确认入账',exact:true}).click();
 await expect(page.getByRole('heading',{name:'已确认，回执已保存'})).toBeVisible();
 await page.getByRole('button',{name:'查询回执',exact:true}).click();await expect(page.getByText('回执查询成功',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'回到今天',exact:true}).click();receipt.before_declaration=await request('/api/account');
 await nav('同步账户');await page.getByRole('button',{name:'账户核对与更正',exact:true}).click();
 receipt.declaration_effective_minute=localMinute();assert.equal(receipt.declaration_effective_minute.slice(0,10),shanghaiDate());
 await page.getByLabel('本次核对截至时点').fill(receipt.declaration_effective_minute);
 await page.getByLabel('核对来源').fill('METHOD engineering current-day scoped no-change');
 await page.getByLabel('核对依据或更正原因').fill('METHOD literal: no trades orders cash or equity changes in this fresh account through displayed minute');
 await page.getByRole('combobox',{name:/^本次用途/}).selectOption('ACCOUNT_ANALYSIS');
 await expect(page.getByRole('combobox',{name:/^账户变化/})).toHaveValue('NONE');
 for(const label of ['成交','委托','资金','权益'])await expect(page.getByLabel(label,{exact:true})).toBeChecked();
 await page.getByRole('button',{name:'预览账户核对',exact:true}).click();await page.screenshot({path:join(out,'current-day-declaration-preview.png'),fullPage:true});
 await page.getByRole('button',{name:'确认账户核对',exact:true}).click();await expect(page.getByRole('heading',{name:'账户核对已确认，回执已保存'})).toBeVisible();
 await page.getByRole('button',{name:'回到今天',exact:true}).click();receipt.after_declaration=await request('/api/account');
 assert.equal(receipt.after_declaration.version,receipt.before_declaration.version+1);
 for(const key of ['cash_balance','broker_available','broker_frozen','positions'])assert.deepEqual(receipt.after_declaration[key],receipt.before_declaration[key]);
 receipt.use_check_at_declared_minute=await request('/api/account/use-check',{purpose:'ACCOUNT_ANALYSIS',required_as_of:new Date(receipt.declaration_effective_minute).toISOString()});
 assert.equal(receipt.use_check_at_declared_minute.allowed,true);
 receipt.checks.current_day_four_scope_no_change=true;
 const panel=page.locator('section').filter({has:page.getByRole('heading',{name:'今天的事实观察',exact:true})}).first();
 await expect(panel.getByLabel('补查缺失事实')).not.toBeChecked();
 async function observe(mode,label){
  const pending=page.waitForResponse(r=>r.url().endsWith('/api/reviews/tasks')&&r.request().method()==='POST');
  await panel.getByRole('button',{name:label,exact:true}).click();const submitted=await(await pending).json();
  const card=page.locator(`[data-review-task="${submitted.task_id}"]`);await expect(card.getByText('观察记录已保存。',{exact:true})).toBeVisible({timeout:30000});
  const task=await request(`/api/reviews/tasks/${submitted.task_id}`);const audit=await request(`/api/reviews/audits/${task.audit_id}`);
  assert.equal(task.inputs.mode,mode);assert.equal(task.refresh_missing,false);assert.equal(task.result.forward_sample_created,false);assert.equal(task.result.forecast,null);assert.equal(task.result.formal_judgment,'DISABLED');
  assert.equal(task.result.calendar.date,shanghaiDate());assert.equal(task.result.account_version,receipt.after_declaration.version);assert.equal(task.retrieval_runs.length,0);assert.deepEqual(task.module_errors,[]);
  assert.ok(new Date(task.result.cutoff)<=new Date(task.result.observed_at));assert.equal(task.result.knowledge_cutoff,task.result.cutoff);
  await expect(card.getByText('事实待补：QUOTE、DAILY。缺口不转换为交易判断。',{exact:true})).toBeVisible();
  await card.getByText('运行审计与覆盖详情',{exact:true}).click();await expect(card.getByText(/重复通知：/)).toBeVisible();
  await page.screenshot({path:join(out,mode.toLowerCase()+'.png'),fullPage:true});
  const repeat=await request('/api/reviews/tasks',{mode,refresh_missing:false,cutoff:task.result.cutoff});assert.equal(repeat.task_id,task.task_id);
  const replay=await request(`/api/reviews/tasks/${task.task_id}/replay`,{});assert.equal(replay.network_calls,0);assert.deepEqual(replay.result,task.result);
  receipt.observations.push({task,audit,repeat_task_id:repeat.task_id,replay});return task;
 }
 const onDemand=await observe('ON_DEMAND','按需观察');receipt.checks.on_demand_current_clock=true;
 receipt.calendar_before_post_close=await request('/api/reviews/summary');
 if(['AFTER_CLOSE','CLOSED'].includes(receipt.calendar_before_post_close.calendar.phase)){
  const postClose=await observe('POST_CLOSE','盘后复盘');assert.equal(postClose.result.previous_snapshot_id,onDemand.result.snapshot_id);assert.equal(postClose.result.change,'NO_SUBSTANTIAL_CHANGE');receipt.checks.post_close_current_permitted_phase=true;
 }else{await expect(panel.getByRole('button',{name:'盘后复盘',exact:true})).toBeDisabled();receipt.post_close_partial='Actual calendar gate forbids POST_CLOSE; no clock override';}
 receipt.after_observations=await request('/api/account');assert.deepEqual(receipt.after_observations,receipt.after_declaration);
 receipt.notifications=await request('/api/notifications');receipt.notification_audit=await request('/api/notifications/audit');assert.equal(receipt.notification_audit.transmission_attempts,0);
 receipt.capability=await request('/api/capabilities');assert.equal(receipt.capability.formal_judgment,'DISABLED');assert.deepEqual(receipt.capability.formal_capabilities,[]);
 receipt.grants=await request('/api/capabilities/grants');assert.deepEqual(receipt.grants,[]);
 const observations=await request('/api/reviews/history');assert.equal(observations.length,receipt.observations.length);
 await nav('历史记录');await expect(page.getByRole('heading',{name:'观察与复盘时间线',exact:true})).toBeVisible();await expect(page.getByRole('button',{name:/^查看观察 /})).toHaveCount(receipt.observations.length);await page.screenshot({path:join(out,'current-day-history.png'),fullPage:true});
 receipt.checks.timeline_no_duplicate_tasks_no_account_mutation=true;
 receipt.no_report_or_model_selection=true;receipt.actual_finished_at=new Date().toISOString();
 receipt.limitations={account_declaration_precision:'minute; covers only displayed cutoff, not later request seconds',source:'No acquisition requested; missing quote/daily retained',post_close:'CLOSED is permitted ordinary non-trading-day review; not completed trading-day daily, scheduled checkpoint, or forward sample',independent_research_samples:0,external_delivery:'Not configured or attempted'};
 await Promise.all(responses);assert.deepEqual(receipt.errors,[]);receipt.status=receipt.post_close_partial?'PARTIAL':'PASS';
}catch(error){receipt.status='FAIL';receipt.failure=String(error);throw error;}
finally{await browser.close();receipt.browser_closed=true;writeFileSync(join(out,'browser-receipt.json'),JSON.stringify(receipt,null,2)+'\n');writeFileSync(join(out,'raw-api-responses.json'),JSON.stringify(raw,null,2)+'\n');}

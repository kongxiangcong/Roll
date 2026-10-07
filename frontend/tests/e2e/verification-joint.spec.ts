import {expect,test} from '@playwright/test';
import {mkdirSync,writeFileSync} from 'node:fs';

test.skip(process.env.ROLL_BROWSER_METHOD!=='1','Explicit METHOD_CASE originals factory required');
test('a saved observation explicitly links decisive verification and audit without ordinary upgrade',async({page})=>{
  const listing=await(await page.request.get('/api/market/list')).json();
  expect((await page.request.post('/api/market/watch',{data:{operation:'ADD',instrument:'SSE:600519',expected_list_version:listing.version}})).ok()).toBeTruthy();
  async function acquire(){
    const request=await(await page.request.post('/api/data/requests',{data:{instruments:['SSE:600519'],groups:['QUOTE'],purpose:'OBSERVATION',start_date:'2026-09-30',end_date:'2026-09-30'}})).json();
    return await(await page.request.post('/api/data/requests/'+request.request_id+'/retrieve')).json();
  }
  const a=await acquire();await page.request.post('/api/__method/original',{data:{origin:'B:second',price:'100.000'}});const b=await acquire();
  const pending=await(await page.request.post('/api/reviews/tasks',{data:{mode:'ON_DEMAND'}})).json();let task:any;
  await expect.poll(async()=>{task=await(await page.request.get('/api/reviews/tasks/'+pending.task_id)).json();return !!task.result;}).toBeTruthy();
  expect((await(await page.request.get('/api/reviews/audits/'+task.audit_id)).json()).critical_review.status).toBe('NOT_REQUIRED');
  expect(await(await page.request.get('/api/data/verifications')).json()).toEqual([]);
  await page.goto('/');await page.getByRole('button',{name:'重点复盘当前观察',exact:true}).click();
  await page.getByLabel('疑点及其如何影响结论').fill('METHOD_CASE 原观察价格影响重大盈亏归因，仅核实际保存版本');
  await page.getByLabel(new RegExp(a.snapshot_id.slice(0,8))).check();await page.getByLabel(new RegExp(b.snapshot_id.slice(0,8))).check();
  await page.getByRole('button',{name:'核验决定性事实',exact:true}).click();
  await expect(page.getByRole('heading',{name:'当前核验：已核验',exact:true})).toBeVisible();
  await expect(page.getByText(new RegExp('已关联原观察 '+task.task_id))).toBeVisible();
  const first=await page.getByLabel('选择已存核验').inputValue();
  await page.getByRole('button',{name:'核验决定性事实',exact:true}).click();
  await expect(page.getByLabel('选择已存核验')).toHaveValue(first);
  const audit=await(await page.request.get('/api/reviews/audits/'+task.audit_id)).json();
  expect(audit.critical_review.verification_id).toBe(first);expect(audit.verification_links).toHaveLength(1);
  const request=await(await page.request.get('/api/reviews/verification-requests/'+audit.critical_review.request_id)).json();
  expect(request.status).toBe('CONSUMED');expect(request.verification_id).toBe(first);expect(request.request.knowledge_cutoff).toBe(task.result.knowledge_cutoff);
  expect((await(await page.request.get('/api/reviews/tasks/'+task.task_id)).json()).result).toEqual(task.result);
  mkdirSync('test-results',{recursive:true});writeFileSync('test-results/14-joint.json',JSON.stringify({evidence_kind:'METHOD_CASE',task,request,audit},null,2));
  await page.screenshot({path:'test-results/14-joint.png',fullPage:true});
});

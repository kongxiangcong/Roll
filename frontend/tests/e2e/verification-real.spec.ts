import {expect,test} from '@playwright/test';
import {mkdirSync,readFileSync,writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';

test.skip(process.env.ROLL_REAL_VERIFICATION!=='1','Explicit SHA-verified07 plus actual Sina own14 dataDir required');
test('real archived supplier chain remains insufficient and issuer PDF is single original basis',async({page})=>{
  const report=JSON.parse(readFileSync('../.scratch/roll-p0/evidence/14/raw/real-run.json','utf8'));
  const before=await (await page.request.get('/api/data/verifications')).json();
  await page.goto('/');await page.getByRole('button',{name:'历史记录',exact:true}).click();
  expect((await(await page.request.get('/api/data/verifications')).json()).length).toBe(before.length);
  await page.getByRole('button',{name:'关键复盘',exact:true}).click();
  await page.getByLabel('选择已存核验').selectOption(report.quote_verification.verification_id);
  await expect(page.getByRole('heading',{name:'当前核验：证据不足',exact:true})).toBeVisible();
  await expect(page.getByText('原始依据独立性未证明',{exact:true})).toBeVisible();
  expect(await page.getByText(/固定方法核验/).count()).toBe(0);
  await page.getByRole('button',{name:'重放原核验',exact:true}).click();await expect(page.getByText('原记录证据不足，网络调用 0 次',{exact:true})).toBeVisible();
  await page.getByLabel('选择已存核验').selectOption(report.issuer_verification.verification_id);
  await expect(page.getByRole('listitem').filter({hasText:'同一原始依据只计一次'})).toBeVisible();
  await expect(page.getByText(/可证明的独立原始依据 1 条/)).toBeVisible();
  const originalLinks=page.getByRole('link',{name:'原始文件',exact:true});expect(await originalLinks.count()).toBe(2);
  const response=await page.request.get((await originalLinks.first().getAttribute('href'))!);expect(response.ok()).toBeTruthy();
  expect(createHash('sha256').update(await response.body()).digest('hex')).toBe(report.issuer_verification.facts[0].evidence[0].document_hash);
  mkdirSync('test-results',{recursive:true});writeFileSync('test-results/14-real.json',JSON.stringify({evidence_kind:'REAL_ARCHIVED_EVIDENCE',network_calls_during_verification:0,
    quote:await(await page.request.get('/api/data/verifications/'+report.quote_verification.verification_id)).json(),
    issuer:await(await page.request.get('/api/data/verifications/'+report.issuer_verification.verification_id)).json()},null,2));
  await page.screenshot({path:'test-results/14-real.png',fullPage:true});
});

test('real saved observation explicitly consumes the original supplier doubt with audit linkage',async({page})=>{
  const report=JSON.parse(readFileSync('../.scratch/roll-p0/evidence/14/raw/real-run.json','utf8'));
  const refs=report.quote_verification.facts[0].evidence.map((e:any)=>e.reference);
  const pending=await(await page.request.post('/api/reviews/tasks',{data:{mode:'ON_DEMAND'}})).json();let task:any;
  await expect.poll(async()=>{task=await(await page.request.get('/api/reviews/tasks/'+pending.task_id)).json();return !!task.result;}).toBeTruthy();
  expect((await(await page.request.get('/api/reviews/audits/'+task.audit_id)).json()).critical_review.status).toBe('NOT_REQUIRED');
  const account=await(await page.request.get('/api/account')).json();
  await page.goto('/');await page.getByRole('button',{name:'重点复盘当前观察',exact:true}).click();
  await page.getByLabel('疑点及其如何影响结论').fill('实际Sina/Tencent旧收盘材料决定复盘归因；只查当时保存版本和原始独立性');
  for(const ref of refs)await page.getByLabel(new RegExp(ref.snapshot_id.slice(0,8)+' #'+ref.fact_index+'(?: ·|$)')).check();
  await page.getByRole('button',{name:'核验决定性事实',exact:true}).click();
  await expect(page.getByRole('heading',{name:'当前核验：证据不足',exact:true})).toBeVisible();
  await expect(page.getByText('原始依据独立性未证明',{exact:true})).toBeVisible();
  await expect(page.getByText(new RegExp('已关联原观察 '+task.task_id))).toBeVisible();
  expect(await page.getByText(/固定方法核验/).count()).toBe(0);
  const vid=await page.getByLabel('选择已存核验').inputValue();
  const audit=await(await page.request.get('/api/reviews/audits/'+task.audit_id)).json();
  const request=await(await page.request.get('/api/reviews/verification-requests/'+audit.critical_review.request_id)).json();
  expect(audit.critical_review.verification_id).toBe(vid);expect(request.verification_id).toBe(vid);
  expect(request.verification.evidence_kind).toBe('REAL_ARCHIVED_EVIDENCE');expect(request.verification.result).toBe('INSUFFICIENT');
  expect(request.request.knowledge_cutoff).toBe(task.result.knowledge_cutoff);
  expect((await(await page.request.get('/api/reviews/tasks/'+task.task_id)).json()).result).toEqual(task.result);
  expect(await(await page.request.get('/api/account')).json()).toEqual(account);
  mkdirSync('test-results',{recursive:true});writeFileSync('test-results/14-real-joint.json',JSON.stringify({evidence_kind:'REAL_ARCHIVED_EVIDENCE',task,request,audit,account_unchanged:true,actual_model_requests:0,external_acquisition_during_review:0},null,2));
  await page.screenshot({path:'test-results/14-real-joint.png',fullPage:true});
});

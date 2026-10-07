import {test,expect} from '@playwright/test';
import {writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
test('actual preserved provider archives retain original times and cached twenty-member homepage p95',async({page,request,browserName})=>{
  test.skip(process.env.ROLL_REVIEW_REAL_CACHE!=='1','requires isolated copied original runtime prepared by acceptance_15.py');
  test.setTimeout(90000);
  const before=await(await request.get('/api/account')).json();
  const listing=await(await request.get('/api/market/list')).json();expect(listing.members).toHaveLength(20);
  const summary=await(await request.get('/api/reviews/summary')).json();const task=summary.latest;
  const item=task.result.instruments.find((i:{instrument:string})=>i.instrument==='SSE:600519');
  expect(item.quote.evidence_kind).toBe('REAL_ACQUISITION');expect(item.quote.upstream_at).toContain('2026-09-30');expect(item.quote.available_at).toContain('2026-10-07');
  const samples:number[]=[];
  for(let index=0;index<50;index++){
    const started=performance.now();await page.goto('/');
    await expect(page.getByRole('heading',{name:'今天',exact:true})).toBeVisible();
    await expect(page.locator(`[data-review-task="${task.task_id}"]`).getByText('观察记录已保存。')).toBeVisible();
    samples.push(performance.now()-started);
  }
  const p95=[...samples].sort((a,b)=>a-b)[47];expect(p95).toBeLessThanOrEqual(2000);
  await page.screenshot({path:'test-results/review-real-cache.png',fullPage:true});
  const replay=await(await request.post('/api/reviews/tasks/'+task.task_id+'/replay')).json();expect(replay.network_calls).toBe(0);expect(replay.result).toEqual(task.result);
  expect(await(await request.get('/api/account')).json()).toEqual(before);
  writeFileSync(resolve('../.scratch/roll-p0/evidence/15/chrome-cache-performance.json'),JSON.stringify({checked_at:new Date().toISOString(),browserName,channel:process.env.ROLL_BROWSER_CHANNEL,user_agent:await page.evaluate(()=>navigator.userAgent),runtime:process.env.ROLL_TEST_DATA_DIR,list_members:20,backgrounds:3,samples_ms:samples,p95_ms:p95,scope:'actual Chrome navigation and complete today/review snapshot render; preserved actual public provider bytes; no new network acquisition; synthetic engineering account and watch list'},null,2)+'\n');
});

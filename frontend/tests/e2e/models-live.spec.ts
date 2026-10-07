import {expect,test} from '@playwright/test';
import {resolve} from 'node:path';
test.skip(process.env.ROLL_MODEL_LIVE!=='1','Requires preserved real18 support and separately tagged METHOD19 model artifacts');
test('actual support failure stays visible with zero probabilities and no formal account changes',async({page})=>{
  const protocols=await (await page.request.get('/api/research/protocols')).json();
  const datasets=await (await page.request.get('/api/research/datasets')).json();
  const actual=datasets.find((d:{source_evidence_kind:string})=>d.source_evidence_kind==='REAL_ACQUISITION');
  const protocol=protocols.find((p:{dataset_id:string})=>p.dataset_id===actual.dataset_id);
  await page.goto('/');await page.getByRole('button',{name:'历史记录',exact:true}).click();await page.getByRole('button',{name:'研究登记',exact:true}).click();
  await page.getByRole('button',{name:`查看协议 ${protocol.protocol_id.slice(0,8)}`,exact:true}).click();
  const panel=page.getByRole('region',{name:'透明模型与研究预测'});
  await expect(panel.getByText('FAILED · RESEARCH',{exact:true})).toBeVisible();
  await expect(panel.getByText(/开发可评分 0 · 校准可评分 0/)).toBeVisible();
  await expect(panel.getByText('INSUFFICIENT_SCORABLE_SUPPORT',{exact:true})).toBeVisible();
  await expect(panel.getByRole('button',{name:'保存方法研究预测'})).toHaveCount(0);
  await expect(page.getByRole('navigation',{name:'主导航'}).getByRole('button')).toHaveCount(5);
  expect((await (await page.request.get('/api/account')).json()).version).toBe(0);
  await panel.screenshot({path:resolve('../.scratch/roll-p0/evidence/19/19-real-failed.png')});
});
test('METHOD research shows insufficient calibration, baselines and frozen-input forecast replay',async({page})=>{
  const protocols=await (await page.request.get('/api/research/protocols')).json();
  let protocol;
  for(const p of protocols){const models=await (await page.request.get(`/api/research/protocols/${p.protocol_id}/models`)).json();if(models.some((m:{status:string})=>m.status==='METHOD_ARTIFACT_ONLY')){protocol=p;break;}}
  expect(protocol).toBeTruthy();
  await page.goto('/');await page.getByRole('button',{name:'历史记录',exact:true}).click();await page.getByRole('button',{name:'研究登记',exact:true}).click();
  await page.getByRole('button',{name:`查看协议 ${protocol.protocol_id.slice(0,8)}`,exact:true}).click();
  const panel=page.getByRole('region',{name:'透明模型与研究预测'});
  await expect(panel.getByText('METHOD_ARTIFACT_ONLY · METHOD_VALIDATION',{exact:true})).toBeVisible();
  await expect(panel.getByText(/校准可评分 20 · 每类要求 20/)).toBeVisible();
  await expect(panel.getByText('CALIBRATION_PER_CLASS_SUPPORT_BELOW_20',{exact:true})).toBeVisible();
  await panel.getByText('可靠性与支持度',{exact:true}).click();await expect(panel.getByText(/Brier、ROC或胜率改善不能宣称PASS/)).toBeVisible();
  await panel.getByLabel('方法观察日').fill('2026-06-22');await panel.getByRole('button',{name:'保存方法研究预测',exact:true}).click();
  await expect(panel.getByText('METHOD ForecastBundle',{exact:true})).toBeVisible();
  await panel.getByRole('button',{name:'原输入预测重放',exact:true}).click();await expect(panel.getByRole('status')).toContainText('与原预测一致 · 联网 0 次');
  expect((await (await page.request.get(`/api/research/protocols/${protocol.protocol_id}`)).json()).forward_started_at).toBeNull();
  expect((await (await page.request.get('/api/account')).json()).version).toBe(0);
  await panel.screenshot({path:resolve('../.scratch/roll-p0/evidence/19/19-method-model.png')});
});

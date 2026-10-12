import {expect,test} from '@playwright/test';
import {resolve} from 'node:path';
test.skip(process.env.ROLL_RECONSTRUCTED19_LIVE!=='1','Requires the separately preserved actual non-METHOD fit');
test('real reconstructed model exposes support, separate freeze states and historical replay',async({page})=>{
  const protocols=await (await page.request.get('/api/research/protocols')).json();
  let protocol:any,model:any;
  for(const p of protocols){const models=await (await page.request.get(`/api/research/protocols/${p.protocol_id}/models`)).json();const fitted=models.find((m:any)=>m.status==='RESEARCH_ARTIFACT_FROZEN');if(fitted){protocol=p;model=fitted;break;}}
  expect(model.evidence_kind).toBe('REAL_ACQUISITION');expect(model.calibrator_fit_status).toBe('FITTED_UNVALIDATED');
  const account=await (await page.request.get('/api/account')).json();
  await page.goto('/');await page.getByRole('button',{name:'历史记录',exact:true}).click();await page.getByRole('button',{name:'研究登记',exact:true}).click();
  await page.getByRole('button',{name:`查看协议 ${protocol.protocol_id.slice(0,8)}`,exact:true}).click();
  const panel=page.getByRole('region',{name:'透明模型与研究预测'});
  await expect(panel.getByText('RESEARCH_ARTIFACT_FROZEN · RESEARCH',{exact:true})).toBeVisible();
  await expect(panel.getByText(/校准拟合 FITTED_UNVALIDATED/)).toBeVisible();
  await expect(panel.getByText(new RegExp(`开发可评分 ${model.statistical_support.development_total} · 校准可评分 ${model.statistical_support.calibration_total}`))).toBeVisible();
  await panel.getByText('可靠性与支持度',{exact:true}).click();await expect(panel.getByText(/校准后统计使用同一校准窗，尚无独立验证/)).toBeVisible();
  await panel.getByText('必要基线与经济比较边界',{exact:true}).click();await expect(panel.getByText(/不能拼成连续NAV/)).toBeVisible();
  await panel.getByLabel('获准历史CAL观察日').fill(model.calibration_predictions[0].observation_date);
  await panel.getByRole('button',{name:'保存历史重建研究预测',exact:true}).click();
  await expect(panel.getByText('历史重建研究 ForecastBundle',{exact:true})).toBeVisible();
  await panel.getByRole('button',{name:'原输入预测重放',exact:true}).click();await expect(panel.getByRole('status')).toContainText('与原预测一致 · 联网 0 次');
  expect((await (await page.request.get('/api/account')).json())).toEqual(account);
  expect((await (await page.request.get(`/api/research/protocols/${protocol.protocol_id}`)).json()).forward_started_at).toBeNull();
  await panel.getByText('可靠性与支持度',{exact:true}).click();await panel.getByText('必要基线与经济比较边界',{exact:true}).click();
  await page.screenshot({path:resolve('../.scratch/roll-p0/evidence/19-reconstruction-2026-10-10/research-view.png'),fullPage:true});
});

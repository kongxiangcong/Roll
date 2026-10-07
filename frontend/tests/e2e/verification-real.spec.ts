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

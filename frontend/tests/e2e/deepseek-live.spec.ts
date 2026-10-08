import {expect, test} from '@playwright/test';
import {readFileSync} from 'node:fs';

test('actual DeepSeek archived results and failures survive page reload', async ({page}) => {
  test.skip(process.env.ROLL_BROWSER_DEEPSEEK_LIVE !== '1', 'explicit real-provider archived acceptance data required');
  const read = (mode: string) => JSON.parse(readFileSync(`../.scratch/roll-p0/evidence/12/live/${mode}-run.json`, 'utf8'));
  const open = async () => {
    await page.goto('/');
    await page.getByRole('button', {name: '持仓与关注', exact: true}).click();
    await page.getByRole('button', {name: '市场事实', exact: true}).click();
  };
  await open();
  const successful = read('retry');
  await page.getByLabel('选择归档运行').selectOption(successful.run_id);
  await expect(page.getByText(/获取状态：PARTIAL/)).toBeVisible();
  await expect(page.getByRole('heading', {name: '补充证据候选'})).toBeVisible();
  await expect(page.getByText(successful.candidates[0].evidence_quote, {exact: true})).toBeVisible();
  await page.getByText('后端与运行配置', {exact: true}).click();
  await expect(page.getByText(/DeepSeek · 模型 deepseek-flash/)).toBeVisible();
  await page.getByText('来源与工具记录', {exact: true}).click();
  await expect(page.getByText(/roll_read_source · ARCHIVED/)).toBeVisible();
  await page.screenshot({path: 'test-results/deepseek-real-evidence.png', fullPage: true});
  await page.getByRole('button', {name: '只读归档回放', exact: true}).click();
  await expect(page.getByText('同版本归档回放完成，网络调用 0 次', {exact: true})).toBeVisible();
  for (const [mode, status] of [['cancel', 'CANCELLED'], ['auth-error', 'UNAVAILABLE'], ['crash', 'INTERRUPTED']]) {
    await page.reload();
    await page.getByRole('button', {name: '持仓与关注', exact: true}).click();
    await page.getByRole('button', {name: '市场事实', exact: true}).click();
    await page.getByLabel('选择归档运行').selectOption(read(mode).run_id);
    await expect(page.getByText(new RegExp(`获取状态：${status}`))).toBeVisible();
    if (mode === 'auth-error') await expect(page.getByRole('alert').filter({hasText: 'DEEPSEEK_AUTH_REJECTED'})).toBeVisible();
    await page.screenshot({path: `test-results/deepseek-real-${mode}.png`, fullPage: true});
  }
});

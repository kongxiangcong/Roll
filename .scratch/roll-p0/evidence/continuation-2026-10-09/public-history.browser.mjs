import {expect,test} from '../../../../frontend/node_modules/@playwright/test/index.mjs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {readFileSync,writeFileSync} from 'node:fs';
const evidence=dirname(fileURLToPath(import.meta.url));

test('actual archived SOHU input and corrected SSE calendar remain visibly restricted',async({page})=>{
  test.setTimeout(90000);
  const receipt=JSON.parse(readFileSync(resolve(evidence,'public-host-live-v3.json'),'utf8'));
  expect(receipt.passed).toBe(true);
  const account=await (await page.request.get('/api/account')).json();
  expect(account.version).toBe(0);
  const datasets=await (await page.request.get('/api/research/datasets')).json();
  expect(datasets).toHaveLength(1);
  expect(datasets[0].training_readiness.state).toBe('BLOCKED');
  expect(datasets[0].partitions.DEVELOPMENT.state).toBe('NOT_PREREGISTERED');
  await page.goto('/');
  await page.getByRole('button',{name:'持仓与关注',exact:true}).click();
  await expect(page.getByRole('article',{name:'SSE:600362',exact:true})).toBeVisible();
  await page.getByLabel('查询日期（上海时间）').fill('2019-05-02');
  await page.getByRole('button',{name:'查询交易日',exact:true}).click();
  await expect(page.getByText('2019-05-02 · SSE · 休市',{exact:true})).toBeVisible();
  await expect(page.getByText('下一个已知交易日：2019-05-06',{exact:true})).toBeVisible();
  const historical=await (await page.request.get('/api/market/calendar?exchange=SSE&date=2019-05-06')).json();
  expect(historical.is_trading_day).toBe(true);
  expect(historical.phase).toBe('UNKNOWN');
  await page.screenshot({path:resolve(evidence,'browser-calendar.png'),fullPage:true});
  await page.getByRole('button',{name:'市场事实',exact:true}).click();
  await page.getByRole('combobox',{name:'日线来源',exact:true}).selectOption('SOHU');
  await expect(page.getByRole('combobox',{name:'日线来源',exact:true})).toHaveValue('SOHU');
  await expect(page.getByText(/历史取得时间为实际本次时间/)).toBeVisible();
  await expect(page.getByRole('heading',{name:'归档事实与客观观察',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'只读归档回放',exact:true}).click();
  await expect(page.getByText('同版本归档回放完成，网络调用 0 次',{exact:true})).toBeVisible();
  await page.screenshot({path:resolve(evidence,'browser-sohu.png'),fullPage:true});
  await page.getByRole('button',{name:'历史记录',exact:true}).click();
  await page.getByRole('button',{name:'研究登记',exact:true}).click();
  await expect(page.getByRole('heading',{name:/已归档覆盖/})).toBeVisible();
  await expect(page.getByText('登记保留事先设计和全部尝试。当前未授模型资格，未启动真实前向使用。',{exact:true})).toBeVisible();
  await page.getByText('数据限制',{exact:true}).click();
  await expect(page.getByText('RESEARCH_WINDOWS_NOT_PREREGISTERED',{exact:true})).toBeVisible();
  await page.screenshot({path:resolve(evidence,'browser-research.png'),fullPage:true});
  expect(await (await page.request.get('/api/account')).json()).toEqual(account);
  expect((await (await page.request.get('/api/capabilities')).json()).state).toBe('UNGRANTED');
  writeFileSync(resolve(evidence,'browser-actual.json'),JSON.stringify({passed:true,profile:'ACTUAL_ARCHIVED_SO_HU_READ_ONLY',
    account_unchanged:true,capability:'UNGRANTED',dataset_id:datasets[0].dataset_id,rows:receipt.daily_summary.rows,
    historical_calendar:historical,sealed_read:false,model_fit:false,paid_backend_call:false},null,2)+'\n');
});

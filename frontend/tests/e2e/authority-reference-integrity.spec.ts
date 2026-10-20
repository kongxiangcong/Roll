import {test, expect} from '@playwright/test';

test('saved session assessment and originals remain readable without new acquisition', async ({page, request}) => {
  const account = await (await request.get('/api/account')).json();
  const writes: string[] = [];
  page.on('request', r => { if (r.method() === 'POST') writes.push(r.url()); });
  await page.goto('/');
  await page.getByRole('button', {name: '持仓与关注', exact: true}).click();
  await page.getByText('来源契约与新补充原件', {exact: true}).click();
  await page.getByRole('button', {name: '查询来源契约补充', exact: true}).click();
  const region = page.getByRole('region', {name: '日线会话量额对照'});
  await expect(region.getByText(/不生成完整日K或授予评分用途/)).toBeVisible();
  await expect(region.getByText(/来源失败，不能当零笔/)).toBeVisible();
  await region.getByText('原件与契约', {exact: true}).click();
  const originals = region.getByRole('link', {name: '保存原件', exact: true});
  expect(await originals.count()).toBe(16);
  expect((await request.get((await originals.first().getAttribute('href'))!)).ok()).toBeTruthy();
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({path: '../.scratch/roll-capability-expansion/evidence/02-daily/contract-20261020/mobile.png', fullPage: true});
  expect(writes).toEqual([]);
  expect(await (await request.get('/api/account')).json()).toEqual(account);
});

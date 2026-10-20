import {test, expect} from '@playwright/test';

test('older issuer action keeps distribution and diluted reference distinct', async ({page, request}) => {
  const account = await (await request.get('/api/account')).json();
  const posts: string[] = [];
  page.on('request', r => { if (r.method() === 'POST') posts.push(r.url()); });
  await page.goto('/');
  await page.getByRole('button', {name: '持仓与关注', exact: true}).click();
  await page.getByText('来源契约与新补充原件', {exact: true}).click();
  await page.getByRole('button', {name: '查询来源契约补充', exact: true}).click();
  const all = page.getByRole('region', {name: '公司行动公告链'});
  await expect(all).toHaveCount(2);
  const latest = all.filter({hasText: '2025-026'});
  await expect(latest.getByText(/每股0.70元.*每股0.6965元/)).toBeVisible();
  await expect(latest.getByText(/更正\/取消及全部旧义务仍未知/)).toBeVisible();
  await latest.getByText('原件与契约', {exact: true}).click();
  const original = latest.getByText(/2024年度实施公告及差异化分红说明/);
  expect((await request.get((await original.getByRole('link', {name: '保存原件'}).getAttribute('href'))!)).ok()).toBeTruthy();
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  await page.screenshot({path: '../.scratch/roll-capability-expansion/evidence/04-actions/older-20261020/mobile.png', fullPage: true});
  expect(posts).toEqual([]);
  expect(await (await request.get('/api/account')).json()).toEqual(account);
});

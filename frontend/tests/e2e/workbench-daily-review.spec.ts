import {expect, test, type APIRequestContext} from '@playwright/test';

async function post(request: APIRequestContext, path: string, data: object) {
  const response = await request.post(path, {data});
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}

test('workbench reviews a frozen report and links the existing judgment and fill', async ({page, request}) => {
  const instrument = 'SSE:600362';
  const baseline = await post(request, '/api/account/drafts', {
    kind: 'BASELINE', expected_account_version: 0,
    payload: {
      effective_at: '2026-10-07T10:00:00+08:00', source: '隔离验收账户',
      cash_balance: '100000.00', broker_available: '100000.00', broker_frozen: '0.00',
      withdrawable: null, positions: [], permission_profile: [],
    },
  });
  await post(request, '/api/account/confirm', {draft_id: baseline.draft_id, idempotency_key: 'review-baseline'});
  const listing = await (await request.get('/api/market/list')).json();
  await post(request, '/api/market/watch', {operation: 'ADD', instrument, expected_list_version: listing.version});
  await post(request, '/api/market/identities', {
    instrument, exchange: 'SSE', board: '主板', instrument_type: 'STOCK', name: '江西铜业',
    basis: '隔离验收证券', effective_at: '2026-01-01T00:00:00+08:00',
  });
  const fill = await post(request, '/api/account/drafts', {
    kind: 'FILL', expected_account_version: 1,
    payload: {
      instrument, effective_at: '2026-10-07T11:00:00+08:00', source: '隔离验收成交',
      direction: 'BUY', quantity: '300', price: '10.00', record_id: 'review-fill',
      fill_id: 'review-fill', order_id: 'review-order',
      behavior_context: 'NO_RECOMMENDATION', broker_available_after: null,
      fee: {status: 'KNOWN', amount: '5.00', reserve_amount: null, basis: '隔离验收费用'},
    },
  });
  await post(request, '/api/account/confirm', {draft_id: fill.draft_id, idempotency_key: 'review-buy'});
  const initial = await post(request, '/api/daily-reports', {});
  const original = await post(request, '/api/daily-reports/notes', {
    idempotency_key: 'review-original', report_id: initial.report_id, instrument,
    thesis: '复查经营现金流能否支持原持仓理由', invalidation: '现金流恶化时重新判断',
    due_date: '2026-10-08',
  });
  const current = await post(request, '/api/daily-reports', {});

  const writes: string[] = [];
  page.on('request', req => {
    if (req.method() === 'POST' && new URL(req.url()).pathname.startsWith('/api/')) {
      writes.push(new URL(req.url()).pathname);
    }
  });
  await page.goto('/#workbench');
  await page.getByRole('tab', {name: '日常复查'}).click();
  const versions = page.getByRole('combobox', {name: '报告版本'});
  await expect(versions).toHaveValue(current.report_id);
  for (const question of ['发生了什么变化', '变化是否影响原持仓理由', '哪些持仓需要复查', '何时重新判断']) {
    await expect(page.getByRole('heading', {name: question})).toBeVisible();
  }
  await expect(page.getByText('原持仓理由 · 复查经营现金流能否支持原持仓理由', {exact: true})).toBeVisible();
  await expect(page.getByText(/已到复查日期/).first()).toBeVisible();
  await expect(page.getByText('2026-10-08', {exact: false}).first()).toBeVisible();
  await versions.selectOption(initial.report_id);
  await expect(page.getByText('这份报告暂无比较基准。', {exact: true})).toBeVisible();
  await expect(page.getByText('原持仓理由 · 复查经营现金流能否支持原持仓理由', {exact: true})).toHaveCount(0);
  await versions.selectOption(current.report_id);
  expect(writes).toEqual([]);

  await page.getByRole('button', {name: '记录本条复查'}).click();
  await page.getByLabel('判断 / 本次复查结论').fill('已复查并关联真实成交');
  await page.getByLabel('哪些事实会推翻判断 / 未行动原因').fill('后续公告与现金流仍待核对');
  await page.getByLabel('记录类型').selectOption('ACTED');
  await page.getByLabel('关联已确认成交').selectOption('review-fill');
  await page.getByRole('button', {name: '保存判断记录'}).click();
  await expect(page.getByText('判断记录已保存', {exact: false})).toBeVisible();
  expect(writes).toEqual(['/api/daily-reports/notes']);
  const latest = await post(request, '/api/daily-reports', {});
  expect(latest.inputs.notes).toContainEqual(expect.objectContaining({
    report_id: current.report_id, parent_note_id: original.note_id,
    fill_record_id: 'review-fill', outcome: 'ACTED',
  }));
  await page.getByRole('button', {name: '重新读取报告列表'}).click();
  await expect(versions.locator(`option[value="${latest.report_id}"]`)).toHaveCount(1);
  await expect(versions).toHaveValue(current.report_id);
  await page.reload();
  await page.getByRole('tab', {name: '日常复查'}).click();
  await expect(versions).toHaveValue(latest.report_id);
  await expect(page.getByText('原持仓理由 · 已复查并关联真实成交', {exact: true})).toBeVisible();
  await page.getByRole('tab', {name: '研究', exact: true}).click();
  await expect(page.getByRole('button', {name: '开始研究'})).toBeVisible();
  await page.getByRole('tab', {name: '历史表现'}).click();
  await expect(page.getByRole('heading', {name: '规则在过去表现如何'})).toBeVisible();
});

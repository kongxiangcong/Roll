import {test,expect} from '@playwright/test';
test('actual restart applies selected point before observers and shows recovery lock across today and settings',async({page,request})=>{
  const state=await(await request.get('/api/runtime/backups/status')).json();
  expect(state.pending_restore).toBeNull();expect(state.recovery.state).toBe('RECOVERY_LOCK');
  expect(state.recovery.old_active_records).toBe('HISTORY_ONLY');expect(state.recovery.old_notifications_allowed).toBe(false);
  const account=await(await request.get('/api/account')).json();expect(account.version).toBe(1);expect(account.cash_balance).toBe('10000.10');
  expect((await request.post('/api/formal/evaluate')).status()).toBe(403);
  await page.goto('/');await expect(page.getByRole('status').filter({hasText:'恢复锁生效：恢复到账户版本 1'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'今天',exact:true})).toBeVisible();
  await page.screenshot({path:'test-results/backups-restored-today.png',fullPage:true});
  await page.getByRole('button',{name:'设置',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'旧授权仅作为历史'})).toBeVisible();
  await page.screenshot({path:'test-results/backups-restored-settings.png',fullPage:true});
  expect(await(await request.get('/api/account')).json()).toEqual(account);
});

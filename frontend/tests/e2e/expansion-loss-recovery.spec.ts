import {test,expect} from '@playwright/test';

test('LOSS recovery keeps peak and revoked predecessor after explicit confirmation',async({page,request})=>{
  const api=`http://127.0.0.1:${process.env.ROLL_TEST_API_PORT}/api`;
  const grants=await(await request.get(api+'/capabilities/grants')).json();
  const successor=grants.find((g:{predecessor_grant_id:string|null})=>g.predecessor_grant_id);
  await page.goto('/');await page.getByRole('button',{name:'设置',exact:true}).click();await page.getByText('LOSS原因绑定恢复',{exact:true}).click();
  await page.getByRole('button',{name:'读取LOSS恢复条件',exact:true}).click();
  await page.getByLabel('LOSS后继资格',{exact:true}).selectOption(successor.grant_id);
  await page.getByLabel('LOSS恢复依据',{exact:true}).fill('METHOD显式后继资格恢复，保留6000峰值和全部暂停历史');
  await page.getByRole('button',{name:'核验当前LOSS恢复条件',exact:true}).click();
  await expect(page.getByText('LOSS恢复核验 · READY · 保留峰值6000.00元',{exact:true})).toBeVisible();
  await page.getByLabel('确认保留原损失起点、峰值和暂停历史',{exact:true}).check();
  await page.route('**/loss-recovery/checks/*/activate',async route=>{
    await route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:{code:'LOSS_RECOVERY_CURRENT_CONDITIONS_CHANGED',gaps:[]}})});
  },{times:1});
  await page.getByRole('button',{name:'确认按后继资格恢复LOSS限制',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('本次确认未提交');
  await expect(page.getByRole('button',{name:'核验当前LOSS恢复条件',exact:true})).toBeEnabled();
  await page.reload();await page.getByRole('button',{name:'设置',exact:true}).click();await page.getByText('LOSS原因绑定恢复',{exact:true}).click();
  await page.getByRole('button',{name:'读取LOSS恢复条件',exact:true}).click();
  await page.getByLabel('LOSS后继资格',{exact:true}).selectOption(successor.grant_id);
  await page.getByLabel('LOSS恢复依据',{exact:true}).fill('条件变化后重新核验，保留原峰值和历史');
  await page.getByRole('button',{name:'核验当前LOSS恢复条件',exact:true}).click();
  await expect(page.getByText('LOSS恢复核验 · READY · 保留峰值6000.00元',{exact:true})).toBeVisible();
  await page.getByLabel('确认保留原损失起点、峰值和暂停历史',{exact:true}).check();
  await page.getByRole('button',{name:'确认按后继资格恢复LOSS限制',exact:true}).click();
  await expect(page.getByText('METHOD恢复回执 · 保留峰值6000.00元 · 旧资格未复活',{exact:true})).toBeVisible();
  expect((await(await request.get(api+'/capabilities/grants/'+successor.predecessor_grant_id+'/status')).json()).state).toBe('REVOKED');
  await page.reload();await page.getByRole('button',{name:'设置',exact:true}).click();await page.getByText('LOSS原因绑定恢复',{exact:true}).click();await page.getByRole('button',{name:'读取LOSS恢复条件',exact:true}).click();
  await expect(page.getByText('METHOD恢复回执 · 保留峰值6000.00元 · 旧资格未复活',{exact:true})).toBeVisible();
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/07-loss-recovery/mobile.png',fullPage:true});
});

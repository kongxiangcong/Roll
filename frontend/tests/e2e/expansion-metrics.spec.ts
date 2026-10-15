import {test,expect} from '@playwright/test';

test('saved actual financial metrics expose formulas and versions without acquisition',async({page,request})=>{
 let acquisitions=0;await page.route('**/collect',async route=>{acquisitions++;await route.abort();});
 await page.goto('/');await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('确定性财务指标',{exact:true}).click();
 await page.getByRole('button',{name:'查询财务指标',exact:true}).click();
 await page.getByText('指标 2026-06-30 · 营收307154938743 · 归母净利8631822608',{exact:true}).click();
 await expect(page.getByText('单季营业总收入：168030866946元',{exact:true})).toBeVisible();
 await expect(page.getByText('TTM 营业总收入：594819535918元',{exact:true})).toBeVisible();
 await page.getByText('营收同比：19.534663%',{exact:true}).click();
 await expect(page.getByText('绝对变化：50196051858元',{exact:true})).toBeVisible();
 const link=page.getByRole('link',{name:'指标输入原件',exact:true}).first();expect((await request.get((await link.getAttribute('href'))!)).status()).toBe(200);
 await page.getByText('集团经营现金／集团净利：0.611974倍',{exact:true}).click();
 await expect(page.getByText('集团经营现金／集团净利：0.611974倍',{exact:true}).locator('..').getByText('公式：operating_cash_flow / consolidated_net_profit',{exact:true})).toBeVisible();
 await page.reload();await page.getByRole('button',{name:'持仓与关注',exact:true}).click();await page.getByText('确定性财务指标',{exact:true}).click();await page.getByRole('button',{name:'查询财务指标',exact:true}).click();
 await expect(page.getByText('指标 2026-06-30 · 营收307154938743 · 归母净利8631822608',{exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();expect(acquisitions).toBe(0);
 await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/11-metrics/mobile.png',fullPage:true});
});

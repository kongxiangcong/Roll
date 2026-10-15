import {test,expect} from '@playwright/test';
const freeze='76286d80-4c5d-4262-b97d-ecb856f181f4';

test('research report compares saved CAL scores without new fitting',async({page})=>{
  await page.goto('/#research='+freeze);
  const report=page.getByRole('region',{name:'保存的研究报告',exact:true});
  await expect(report).toBeVisible();
  await report.getByText('概率计算独立库核验',{exact:true}).click();
  await report.getByRole('button',{name:'核对已保存CAL概率',exact:true}).click();
  await expect(report.getByText('scikit-learn 1.9.1 · NOT_GRANTED',{exact:true})).toBeVisible({timeout:30000});
  await expect(report.getByText('校准前 · 数值一致',{exact:true})).toBeVisible();
  await expect(report.getByText('校准后 · 数值一致',{exact:true})).toBeVisible();
  await expect(report.getByText('CAL原窗口诊断 · 未验证独立校准有效性',{exact:true})).toBeVisible();
  await report.getByRole('button',{name:'校验保存的概率核验工件',exact:true}).click();
  await expect(report.getByText('原工件校验一致 · 未重新评分',{exact:true})).toBeVisible();
  await page.reload();await report.getByText('概率计算独立库核验',{exact:true}).click();
  await report.getByRole('button',{name:'查看保存的概率核验',exact:true}).click();
  await expect(report.getByText('校准后 · 数值一致',{exact:true})).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:'../.scratch/roll-capability-expansion/evidence/20-probability/mobile.png',fullPage:true});
});

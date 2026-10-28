import {test,expect} from '@playwright/test';

test('finite selection, immutable reports, and judgment record',async({page,request})=>{
  for(const instrument of ['SSE:600362','SZSE:000001','SSE:600000']){
    const list=await (await request.get('/api/market/list')).json();
    expect((await request.post('/api/market/watch',{data:{operation:'ADD',instrument,expected_list_version:list.version}})).ok()).toBeTruthy();
  }
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'持仓与自选 · 日常使用'})).toBeVisible();
  await expect(page.getByLabel('观察证券').locator('option')).toHaveCount(3);
  await page.getByLabel('观察证券').selectOption('SZSE:000001');
  await expect(page.getByRole('region',{name:'持仓与自选日常使用'})).toContainText('SZSE:000001');
  await page.getByRole('button',{name:'生成 / 更新合并报告'}).click();
  await expect(page.getByLabel('报告版本').locator('option')).toHaveCount(1);
  await expect(page.getByRole('region',{name:'每日合并报告'})).toContainText('自选池不能代替市场广度');
  await page.getByText('记录判断、未行动原因与后续复查',{exact:true}).click();
  await page.getByLabel('判断 / 本次复查结论',{exact:true}).fill('检查经营现金是否改善');
  await page.getByLabel('哪些事实会推翻判断 / 未行动原因',{exact:true}).fill('下一期经营现金转负则复查');
  await page.getByRole('button',{name:'保存判断记录'}).click();
  await expect(page.getByLabel('报告版本').locator('option')).toHaveCount(2);
  await expect(page.getByRole('region',{name:'每日合并报告'})).toContainText('检查经营现金是否改善');
  const options=await page.getByLabel('报告版本').locator('option').evaluateAll(nodes=>nodes.map(n=>(n as HTMLOptionElement).value));
  await page.getByLabel('报告版本').selectOption(options[1]);
  await expect(page.getByRole('region',{name:'每日合并报告'})).toContainText('还没有持续追踪的判断');
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await page.screenshot({path:'test-results/daily-production-mobile.png',fullPage:true});
});

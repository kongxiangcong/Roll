import {chromium} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
const output=new URL('../../.scratch/roll-daily-use/',import.meta.url).pathname.replace(/^\/([A-Za-z]:)/,'$1');
await mkdir(output,{recursive:true});
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  await page.goto('http://127.0.0.1:5173');
  await page.getByRole('heading',{name:'江西铜业 · 日常使用'}).waitFor();
  await page.getByRole('region',{name:'日常观察状态'}).waitFor();
  await page.screenshot({path:output+'/live-desktop.png'});
  await page.getByText('财务观察',{exact:true}).first().click();
  await page.getByRole('button',{name:'查看财务观察',exact:true}).click();
  await page.getByRole('region',{name:'财务观察内容'}).waitFor();
  await page.getByRole('region',{name:'财务观察内容'}).screenshot({path:output+'/live-financial.png'});
  await page.setViewportSize({width:390,height:844});
  await page.evaluate(()=>window.scrollTo(0,0));
  await page.screenshot({path:output+'/live-mobile.png'});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
  if(overflow)throw new Error('MOBILE_HORIZONTAL_OVERFLOW');
  console.log(JSON.stringify({desktop:true,mobile:true,financial:true,horizontalOverflow:false}));
}finally{await browser.close();}

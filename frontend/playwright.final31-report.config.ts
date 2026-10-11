import {defineConfig} from '@playwright/test';
if(process.env.ROLL_FINAL31_BEHAVIOR_RELEASE!=='1'||!process.env.ROLL_FINAL31_REPORT_UI||!process.env.ROLL_FINAL31_REPORT_OUTPUT)throw new Error('FINAL31_ACCEPTED_RELEASE_REQUIRED');
export default defineConfig({testDir:'tests/e2e',testMatch:'reports.spec.ts',workers:1,retries:0,
 use:{baseURL:process.env.ROLL_FINAL31_REPORT_UI,headless:true,channel:'chrome'},
 outputDir:process.env.ROLL_FINAL31_REPORT_OUTPUT+'/artifacts',
 reporter:[['list'],['json',{outputFile:process.env.ROLL_FINAL31_REPORT_OUTPUT+'/results.json'}]]});

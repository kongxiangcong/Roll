import {defineConfig} from '@playwright/test';
import {join} from 'node:path';
import config from './playwright.config';

// Each canonical invocation runs exactly one file, preserving its within-file history.
export const defaultFiles=['baseline','cash-equity','codex-evidence','csv','deepseek-evidence',
  'fills','funding','market','market-overflow','reconcile','valuation'];
const reportDir=process.env.ROLL_E2E_REPORT_DIR??'test-results/default';
export default defineConfig({...config,testIgnore:[],testMatch:defaultFiles.map(file=>`${file}.spec.ts`),
  outputDir:join(reportDir,'artifacts'),
  reporter:[['list'],['json',{outputFile:join(reportDir,'results.json')}]]});

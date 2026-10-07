import {defineConfig} from '@playwright/test';
import config from './playwright.config';
// An immutable initial account needs a separate real process/data directory.
export default defineConfig({...config,testIgnore:[],testMatch:'market-overflow.spec.ts',
  reporter:[['list'],['json',{outputFile:'test-results/overflow-results.json'}]]});

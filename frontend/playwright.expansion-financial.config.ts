import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-financial.spec.ts',
  outputDir:'../.scratch/roll-capability-expansion/evidence/09-financial/browser-results',
  reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/09-financial/browser-results.json'}]],timeout:60000});

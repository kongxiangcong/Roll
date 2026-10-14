import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-daily.spec.ts',
  outputDir:'../.scratch/roll-capability-expansion/evidence/02-daily/browser-results',
  reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/02-daily/browser-results.json'}]],timeout:60000});

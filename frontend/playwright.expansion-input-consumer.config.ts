import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-cost-stress.spec.ts',
  outputDir:'../.scratch/roll-capability-expansion/evidence/05-input-consumer/browser-results',
  reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/05-input-consumer/browser-results.json'}]],timeout:120000});

import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-probability.spec.ts',
  outputDir:'../.scratch/roll-capability-expansion/evidence/20-probability/browser-results',
  reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/20-probability/browser-results.json'}]],timeout:60000});

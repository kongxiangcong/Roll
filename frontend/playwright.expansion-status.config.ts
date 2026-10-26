import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-status.spec.ts',
  outputDir:'../.scratch/roll-capability-expansion/evidence/03-status/browser-results',
  reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/03-status/browser-results.json'}]],timeout:60000});

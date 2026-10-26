import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-performance.spec.ts',
  outputDir:'../.scratch/roll-capability-expansion/evidence/19-performance/browser-results',
  reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/19-performance/browser-results.json'}]],timeout:90000});

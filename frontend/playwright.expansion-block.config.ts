import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-block.spec.ts',
  outputDir:'../.scratch/roll-capability-expansion/evidence/21-block/browser-results',
  reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/21-block/browser-results.json'}]],timeout:90000});

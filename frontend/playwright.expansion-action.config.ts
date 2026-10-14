import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-action.spec.ts',
  outputDir:'../.scratch/roll-capability-expansion/evidence/04-actions/browser-results',
  reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/04-actions/browser-results.json'}]],timeout:60000});

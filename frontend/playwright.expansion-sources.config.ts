import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:['expansion-status.spec.ts','expansion-action.spec.ts'],
  outputDir:'../.scratch/roll-capability-expansion/evidence/05-protocol/source-helper-results',
  reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/05-protocol/source-helper-results.json'}]],timeout:60000});

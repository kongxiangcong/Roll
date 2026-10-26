import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-protocol.spec.ts',
  outputDir:'../.scratch/roll-capability-expansion/evidence/05-protocol/browser-results',
  reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/05-protocol/browser-results.json'}]],timeout:90000});

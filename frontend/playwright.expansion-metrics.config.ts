import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-metrics.spec.ts',outputDir:'../.scratch/roll-capability-expansion/evidence/11-metrics/browser-results',reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/11-metrics/browser-results.json'}]],timeout:90000});

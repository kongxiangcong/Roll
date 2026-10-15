import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-statements.spec.ts',outputDir:'../.scratch/roll-capability-expansion/evidence/10-statements/browser-results',reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/10-statements/browser-results.json'}]],timeout:90000});

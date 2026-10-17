import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-sentiment.spec.ts',outputDir:'../.scratch/roll-capability-expansion/evidence/16-sentiment/browser-results',reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/16-sentiment/browser-results.json'}]],timeout:90000});

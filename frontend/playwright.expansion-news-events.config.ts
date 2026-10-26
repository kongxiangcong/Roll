import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-news-events.spec.ts',outputDir:'../.scratch/roll-capability-expansion/evidence/15-events/browser-results',reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/15-events/browser-results.json'}]],timeout:90000});

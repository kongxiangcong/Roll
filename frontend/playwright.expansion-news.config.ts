import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-news.spec.ts',outputDir:'../.scratch/roll-capability-expansion/evidence/14-news/browser-results',reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/14-news/browser-results.json'}]],timeout:90000});

import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-financial-observation.spec.ts',outputDir:'../.scratch/roll-capability-expansion/evidence/13-observation/browser-results',reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/13-observation/browser-results.json'}]],timeout:90000});

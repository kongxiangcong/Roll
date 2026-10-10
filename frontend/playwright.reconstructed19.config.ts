import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'reconstructed-model-live.spec.ts',outputDir:'../.scratch/roll-p0/evidence/19-reconstruction-2026-10-10/browser-results',reporter:[['list'],['json',{outputFile:'../.scratch/roll-p0/evidence/19-reconstruction-2026-10-10/browser-results.json'}]],timeout:90000});

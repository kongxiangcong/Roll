import base from './playwright.config';
import {defineConfig} from '@playwright/test';
export default defineConfig({...base,testMatch:'expansion-loss-recovery.spec.ts',outputDir:'../.scratch/roll-capability-expansion/evidence/07-loss-recovery/browser-results',reporter:[['list'],['json',{outputFile:'../.scratch/roll-capability-expansion/evidence/07-loss-recovery/browser-results.json'}]],timeout:90000});

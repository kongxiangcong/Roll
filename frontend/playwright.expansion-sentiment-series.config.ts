import base from './playwright.config';
import {defineConfig} from '@playwright/test';
const method=process.env.ROLL_SERIES_METHOD==='1';
export default defineConfig({...base,testMatch:method?'expansion-sentiment-series-method.spec.ts':'expansion-sentiment-series.spec.ts',outputDir:`../.scratch/roll-capability-expansion/evidence/17-series/${method?'method-':''}browser-results`,reporter:[['list'],['json',{outputFile:`../.scratch/roll-capability-expansion/evidence/17-series/${method?'method-':''}browser-results.json`}]],timeout:90000});
